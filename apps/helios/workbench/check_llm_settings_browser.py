"""Check LLM settings and result explanations with an isolated mock provider."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'shared'))


class Provider(BaseHTTPRequestHandler):
    models = []
    def log_message(self, *args):
        pass
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.models.append(payload['model'])
        content = 'The synthetic sample reports 8547.282 kWh.' if 'Explain' in payload['messages'][0]['content'] else 'OK'
        data = json.dumps({'choices':[{'message':{'content':content}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(data)


def check(page, base, width, output, preview_only):
    def shot(name):
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / f'{width}-{name}.png'), full_page=True)
    page.goto(base + '/demo', wait_until='networkidle')
    expect(page.locator('nav').get_by_role('link',name='Data sources',exact=True)).to_have_count(0)
    expect(page.get_by_role('button',name='Configure data sources')).to_be_visible()
    page.get_by_role('link',name='LLM configuration',exact=True).click()
    expect(page.locator('#profile-draft')).to_be_visible()
    expect(page.locator('#profile-query')).to_be_visible()
    shot('llm-settings')
    if preview_only:
        return
    page.locator('#query-mode').select_option('openai-compatible')
    page.locator('#query-model').fill('unsaved-query-choice')
    page.locator('#draft-mode').select_option('disabled')
    page.locator('#draft-save').click()
    expect(page.locator('#llm-notice')).to_contain_text('Semantic draft generation settings saved')
    expect(page.locator('#draft-test')).to_be_disabled()
    expect(page.locator('#query-model')).to_have_value('unsaved-query-choice')
    page.locator('#query-mode').select_option('inherited')
    expect(page.locator('#query-test')).to_be_enabled()
    assert not page.request.get(base + '/demo/api/context/proposals').json()['llm_available']
    page.locator('#draft-mode').select_option('inherited')
    page.locator('#draft-save').click()
    expect(page.locator('#draft-test')).to_be_enabled()
    page.locator('#query-mode').select_option('openai-compatible')
    page.locator('#query-model').fill('browser-query-model')
    page.locator('#query-save').click()
    expect(page.locator('#llm-notice')).to_contain_text('Data query explanations settings saved')
    page.locator('#query-test').click()
    expect(page.locator('#query-test-result')).to_contain_text('responded successfully', timeout=30000)
    page.reload(wait_until='networkidle')
    expect(page.locator('#query-model')).to_have_value('browser-query-model')
    shot('llm-custom')
    page.goto(base + '/demo/query?source=power', wait_until='networkidle')
    page.locator('#run').click()
    expect(page.locator('#result')).to_be_visible()
    page.locator('#explain-result').click()
    expect(page.locator('#explanation-text')).to_contain_text('8547.282', timeout=30000)
    expect(page.locator('#explanation-model')).to_contain_text('browser-query-model')
    expect(page.locator('#value')).to_have_text('8,547.282')
    shot('query-explanation')
    page.locator('nav').get_by_role('link',name='LLM configuration',exact=True).click()
    page.locator('#query-mode').select_option('disabled')
    page.locator('#query-save').click()
    expect(page.locator('#query-test')).to_be_disabled()
    assert page.request.get(base + '/demo/api/context/proposals').json()['llm_available']
    page.goto(base + '/demo/query?source=power', wait_until='networkidle')
    page.locator('#run').click()
    expect(page.locator('#result')).to_be_visible()
    expect(page.locator('#explain-result')).to_be_disabled()
    # Reset for the second viewport without modifying draft definitions.
    response = page.request.get(base + '/demo/api/llm').json()['profiles']['query']
    assert page.request.post(base + '/demo/api/llm', data={'purpose':'query','mode':'inherited','revision':response['revision']}).ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--preview-only',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('/tmp/helios-llm-browser'))
    args = parser.parse_args()
    if args.base and not args.preview_only:
        parser.error('Existing instances support --preview-only; mutable tests create isolated state.')
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='helios-llm-browser-') as temp:
        process = provider = log = None
        try:
            base = args.base
            if not base:
                from helios_core.demo.registry import PackRegistry
                from helios_core.demo.runtime import review_pack
                state = Path(temp)
                pack = PackRegistry(ROOT/'apps/helios/demo-packs.json', ROOT/'apps/helios-ds-generation/fixtures/sectors/v1').load('power')
                review_pack(pack,state,'automated-browser-test-only')
                provider = ThreadingHTTPServer(('127.0.0.1',0),Provider)
                threading.Thread(target=provider.serve_forever,daemon=True).start()
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
                base = f'http://127.0.0.1:{port}'
                log = (args.output/'server.log').open('w')
                env = {**os.environ,'LLM_PROVIDER':'openai','INFERENCE_TOKEN':'browser-test-only','INFERENCE_BASE_URL':f'http://127.0.0.1:{provider.server_port}/v1','INFERENCE_MODEL':'browser-draft-model','PYSTOW_HOME':str(state/'pystow')}
                process = subprocess.Popen([sys.executable,str(ROOT/'start_demo.py'),'--dataset','power','--state-dir',str(state),'--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                for attempt in range(150):
                    try:
                        urllib.request.urlopen(base+'/demo/api/llm',timeout=1).close(); break
                    except OSError:
                        if process.poll() is not None or attempt==149:
                            raise RuntimeError('Test server did not start; inspect server.log')
                        time.sleep(.2)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                outcomes = []
                for width,height in [(1440,1000),(390,844)]:
                    page = browser.new_page(viewport={'width':width,'height':height})
                    errors = []
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    check(page,base,width,args.output,args.preview_only)
                    assert not errors, errors
                    outcomes.append({'width':width,'passed':True,'javascript_errors':errors,'preview_only':args.preview_only})
                    page.close()
                browser.close()
                (args.output/'results.json').write_text(json.dumps(outcomes,indent=2)+'\n')
                print(json.dumps(outcomes,indent=2))
        finally:
            if process:
                process.terminate(); process.wait(timeout=15)
            if provider:
                provider.shutdown(); provider.server_close()
            if log:
                log.close()


if __name__=='__main__':
    main()
