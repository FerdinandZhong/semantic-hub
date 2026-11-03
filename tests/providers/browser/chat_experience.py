"""Verify real numeric chat, streamed progress, and validation feedback in isolated state."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', required=True)
parser.add_argument('--output', type=Path, default=Path('/tmp/hub-chat-review-images'))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
base = args.base_url.rstrip('/')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440, 'height':1000})
    # Slow delivery of real server events to make transient progress observable.
    # This changes test transport timing only, not events or query results.
    page.add_init_script("""(() => {
      const originalFetch = window.fetch;
      window.fetch = async (...args) => {
        const response = await originalFetch(...args);
        if (!String(args[0]).includes('/playground/chat') || !response.ok) return response;
        const decoder = new TextDecoder(), encoder = new TextEncoder(); let pending = '';
        const transform = new TransformStream({
          async transform(chunk, controller) {
            pending += decoder.decode(chunk, {stream:true});
            const lines = pending.split('\\n'); pending = lines.pop();
            for (const line of lines) {
              controller.enqueue(encoder.encode(line + '\\n'));
              await new Promise(resolve => setTimeout(resolve, 350));
            }
          },
          flush(controller) { if (pending) controller.enqueue(encoder.encode(pending)); }
        });
        return new Response(response.body.pipeThrough(transform), {status:response.status, headers:response.headers});
      };
    })();""")
    errors = []
    page.on('pageerror', lambda e:errors.append(str(e)))
    page.goto(base+'/v2?view=chat&workspace=finance', wait_until='networkidle')
    page.locator('[data-suggest]').first.wait_for()
    page.screenshot(path=str(args.output/'chat-welcome.png'), full_page=True)
    page.locator('[data-suggest]').first.click()
    assert page.locator('#question').input_value() == 'What is the total settled sender outflow in SGD for the sample?'
    page.locator('#ask').click()
    page.locator('.chat-flow [data-state=running]').first.wait_for()
    assert page.locator('#question').is_disabled()
    page.screenshot(path=str(args.output/'chat-progress.png'), full_page=True)
    page.locator('.answer-value').wait_for(timeout=30000)
    assert page.locator('.answer-value').inner_text() == 'SGD 686,572.96'
    assert page.locator('.chat-flow [data-state=done]').count() == 4
    assert 'No retrieval confidence score applies' in page.locator('.retrieval-panel').inner_text()
    page.locator('.answer-progress summary').click()
    page.screenshot(path=str(args.output/'chat-numeric.png'), full_page=True)

    # A deterministic document stream exercises the UI; this is not a live LLM test.
    fixture = [
        {'type':'progress','stage':'retrieve','detail':'Retrieve published document passages'},
        {'type':'retrieval','detail':{'method':'Keyword overlap','matches':[{'name':'MAS SG QR announcement','location':'page 1','score':7,'query_terms':10}], 'note':'Keyword matches measure relevance, not answer correctness.'}},
        {'type':'progress','stage':'answer','detail':'Verify cited claims'},
        {'type':'result','result':{'kind':'document','status':'answered','context_version':'v1', 'claims':[{'text':'The announcement describes PayNow integration into SG QR for person-to-person transfers.', 'citations':[{'title':'MAS SG QR announcement','location':'page 1','quote':'PayNow as part of the SG QR for person-to-person fund transfers.'}]}]}},
    ]
    page.route('**/demo/api/playground/chat?**', lambda route: route.fulfill(status=200,content_type='application/x-ndjson',body='\n'.join(json.dumps(e) for e in fixture)+'\n'))
    page.locator('#clear-chat').click()
    page.locator('#question').fill('According to MAS, how does SG QR support PayNow transfers?')
    page.locator('#ask').click()
    page.locator('.citation-card').wait_for()
    assert '7 / 10 terms' in page.locator('.retrieval-panel').inner_text()
    assert page.locator('.answer-value').count() == 0
    page.locator('.citation-card summary').click()
    page.screenshot(path=str(args.output/'chat-document-fixture.png'), full_page=True)
    page.unroute('**/demo/api/playground/chat?**')

    page.goto(base+'/v2/editor?source=finance#validate', wait_until='networkidle')
    page.locator('#validate:not([disabled])').wait_for()
    page.locator('#validate').click()
    page.locator('#validation-progress[data-state=running]').wait_for()
    assert page.locator('#notice').inner_text() == ''
    assert 'ready to validate' not in page.locator('#validation-status').inner_text()
    page.screenshot(path=str(args.output/'validation-progress.png'), full_page=True)
    page.locator('#validation-progress[data-state=done]').wait_for(timeout=60000)
    page.screenshot(path=str(args.output/'validation-complete.png'), full_page=True)
    assert not errors, errors
    browser.close()
print('Passed: real numeric execution, live progress, document UI fixture, real validation, no page errors.')
