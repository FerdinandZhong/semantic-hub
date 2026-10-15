"""Verify local Swagger authentication and a read-only request without logging credentials."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8096')
    parser.add_argument('--token-file',type=Path)
    parser.add_argument('--chromium',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    token=args.token_file.read_text().strip() if args.token_file else None
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.chromium)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(args.url+'/docs')
        if token:
            page.get_by_label('Consumer API token').fill('invalid-token')
            page.get_by_role('button',name='Open API documentation').click()
            page.get_by_role('status').filter(has_text='not accepted').wait_for()
            page.get_by_label('Consumer API token').fill(token)
            page.get_by_role('button',name='Open API documentation').click()
        page.locator('.swagger-ui .opblock').first.wait_for()
        if token:
            page.wait_for_function("document.querySelector('.swagger-ui .auth-wrapper .authorize')?.classList.contains('locked')")
            assert page.get_by_label('Consumer API token').input_value()==''
            assert token not in page.locator('body').inner_text()
        else:
            assert not page.get_by_label('Consumer API token').is_visible()
        assert page.evaluate('localStorage.length')==0
        assert page.evaluate('sessionStorage.length')==0
        screenshot=args.output.with_suffix('.png')
        page.screenshot(path=str(screenshot),full_page=True)
        endpoint=page.locator('.opblock').filter(has=page.locator('.opblock-summary-path[data-path="/api/semantic-hub/v1/capabilities"]'))
        endpoint.locator('.opblock-summary').click()
        endpoint.get_by_role('button',name='Try it out').click()
        with page.expect_response(lambda response:response.url.endswith('/api/semantic-hub/v1/capabilities')) as pending:
            endpoint.get_by_role('button',name='Execute',exact=True).click()
        assert pending.value.status==200
        assert pending.value.json()['service']=='Semantic Hub'
        assert not errors,'Browser script error'
        page.reload()
        if token:
            assert page.get_by_label('Consumer API token').input_value()==''
            assert page.locator('.swagger-ui .opblock').count()==0
        else:
            page.locator('.swagger-ui .opblock').first.wait_for()
        browser.close()
    report={'ok':True,'url':args.url+'/docs','authentication':'bearer' if token else 'local_no_auth','invalid_token_rejected':True if token else None,
            'schema_loaded':True,'try_it_out_status':200,
            'token_persisted':False,'reload_clears_access':True if token else None,'browser_errors':0,
            'screenshot':str(screenshot)}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
