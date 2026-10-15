"""Browser test for write-only credentials, using isolated state and a fake model provider."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'shared')]
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright
import uvicorn
from apps.helios.console import demo


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--chromium',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    secret='test-only-browser-credential'
    received=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length','0')))
            received.append(self.headers.get('Authorization')=='Bearer '+secret)
            body=json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
    provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    threading.Thread(target=provider.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='helios-key-ui-') as state:
        os.environ['HELIOS_DEMO_STATE']=state
        os.environ['HELIOS_DEMO_DATASET']='power'
        demo.llm_from_env=lambda:None
        app=FastAPI();app.include_router(demo.demo_router);demo.configure_demo(app)
        app.mount('/static',StaticFiles(directory=ROOT/'apps/helios/console/static'))
        sock=socket.socket();sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.05)
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.chromium)
                page=browser.new_page(viewport={'width':1440,'height':1100})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{port}/demo/llm')
                page.locator('#query-mode').select_option('openai-compatible')
                assert page.locator('#query-credential-mode').input_value()=='api_key'
                assert page.locator('#query-credential_ref').is_hidden()
                page.locator('#query-model').fill('test-model')
                page.locator('#query-base_url').fill(f'http://127.0.0.1:{provider.server_port}/v1')
                assert page.locator('#query-api-key').get_attribute('type')=='password'
                page.locator('#query-api-key').fill(secret)
                with page.expect_response(lambda r:r.url.endswith('/demo/api/llm') and r.request.method=='POST') as saved:
                    page.locator('#query-save').click()
                assert saved.value.status==200
                assert secret not in saved.value.text()
                page.locator('#query-api-key[placeholder="Key saved. Leave blank to keep it."]').wait_for()
                assert page.locator('#query-api-key').input_value()==''
                page.locator('#query-test').click()
                page.locator('#query-test-result').filter(has_text='responded successfully').wait_for()
                assert received==[True]
                page.reload()
                page.locator('#query-api-key[placeholder="Key saved. Leave blank to keep it."]').wait_for()
                assert page.locator('#query-api-key').input_value()==''
                page.locator('#profile-query').screenshot(path=str(args.output.with_suffix('.png')))
                page.locator('#query-model').fill('changed-test-model')
                with page.expect_response(lambda r:r.url.endswith('/demo/api/llm') and r.request.method=='POST') as kept:
                    page.locator('#query-save').click()
                assert kept.value.json()['profiles']['query']['ready']
                page.locator('#query-clear-api-key').check()
                with page.expect_response(lambda r:r.url.endswith('/demo/api/llm') and r.request.method=='POST') as removed:
                    page.locator('#query-save').click()
                assert not removed.value.json()['profiles']['query']['has_saved_api_key']
                assert not removed.value.json()['profiles']['query']['ready']
                assert not errors
                browser.close()
        finally:
            server.should_exit=True;thread.join(timeout=10);sock.close()
            provider.shutdown();provider.server_close()
    report={'ok':True,'isolated_workspace':True,'provider':'local test double','masked_input':True,
            'save_reload_keep_remove':True,'saved_connection_test':True,'secret_in_response':False,
            'browser_errors':0,'user_settings_changed':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
