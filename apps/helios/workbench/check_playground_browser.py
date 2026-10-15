"""Isolated published playground journeys for all four local datasets."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'shared')]
from playwright.sync_api import sync_playwright,expect
from apps.helios.tests.test_demo_playground import released
from helios_core.demo.llm_settings import LLMSettings,LLMSettingsSave


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('/tmp/helios-playground-browser'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    outcomes=[]
    with tempfile.TemporaryDirectory(prefix='helios-playground-') as temp:
        state=Path(temp)
        for sector in ['finance','manufacturing','pharma','power']:
            runtime=released(state,sector);runtime.close()
        LLMSettings(state).save(LLMSettingsSave(purpose='query',mode='disabled',revision=0))
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        with (args.output/'server.log').open('w') as log:
            process=subprocess.Popen([sys.executable,str(ROOT/'start_demo.py'),'--dataset','power','--state-dir',temp,'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,env={**os.environ,'PYSTOW_HOME':str(state/'pystow')})
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(base+'/demo/api/config',timeout=1);break
                    except Exception:
                        if process.poll() is not None:raise RuntimeError('Preview exited')
                        time.sleep(.2)
                with sync_playwright() as p:
                    browser=p.chromium.launch()
                    for sector in ['finance','manufacturing','pharma','power']:
                        for width in [1440,390]:
                            page=browser.new_page(viewport={'width':width,'height':1000});errors=[]
                            page.on('pageerror',lambda e:errors.append(str(e)))
                            before=page.request.get(base+f'/demo/api/context?source={sector}').json()
                            page.goto(base+f'/demo/query?source={sector}',wait_until='networkidle')
                            expect(page.locator('#playground-version')).to_have_value('v1')
                            page.locator('#playground-question').fill('What is the total?')
                            page.locator('#playground-ask').click()
                            expect(page.locator('#playground-clarification')).to_be_visible()
                            expect(page.locator('#playground-answer')).not_to_be_visible()
                            page.locator('#playground-examples').evaluate('el => el.closest("details").open=true')
                            page.locator('#playground-examples button').first.click()
                            expect(page.locator('#playground-interpretation')).to_be_visible(timeout=30000)
                            expect(page.locator('#playground-canvas .canvas-node').first).to_be_visible()
                            assert page.locator('#playground-canvas').get_by_role('button',name='Edit',exact=True).count()==0
                            expect(page.locator('#playground-answer')).not_to_be_visible()
                            page.locator('#playground-run').click()
                            expect(page.locator('#playground-answer')).to_be_visible(timeout=30000)
                            expected={'finance':'686,572.96','manufacturing':'312','pharma':'98.275','power':'8,547.282'}[sector]
                            expect(page.locator('#playground-answer-text')).to_contain_text(expected)
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                            page.screenshot(path=str(args.output/f'{sector}-{width}.png'),full_page=True)
                            page.locator('#playground-question').fill('A different question')
                            expect(page.locator('#playground-answer')).not_to_be_visible()
                            expect(page.locator('#playground-run')).not_to_be_visible()
                            assert page.request.get(base+f'/demo/api/context?source={sector}').json()==before
                            page.goto(base+f'/demo/query?source={sector}&version=missing',wait_until='networkidle')
                            expect(page.locator('#playground-error')).to_contain_text('not published')
                            expect(page.locator('#playground-ready')).not_to_be_visible()
                            assert not errors,errors
                            outcomes.append({'source':sector,'width':width,'status':'passed'});page.close()
                    browser.close()
            finally:
                process.terminate();process.wait(timeout=15)
    (args.output/'results.json').write_text(json.dumps(outcomes,indent=2))
    print(json.dumps(outcomes,indent=2))

if __name__=='__main__':main()
