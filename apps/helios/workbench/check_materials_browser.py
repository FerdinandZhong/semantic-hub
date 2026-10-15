"""Isolated materials upload, keyword review, and draft application browser checks."""
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

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'shared')]
from playwright.sync_api import sync_playwright, expect
from apps.helios.tests.test_demo_playground import released

TEXT = '''# Operations notes
Manufacturing planned downtime minutes work orders maintenance support operational review.
<img src=x onerror="window.materialInjection=true"> is untrusted document text.

# Finance notes
Finance settled sender outflow SGD fixed synthetic FX total_amount_sgd payments amount_sgd account balances currency reporting.
'''
# Force separate extracted text chunks for each model scope.
TEXT = TEXT.replace('\n# Finance notes', '\n' + ('neutraltext ' * 155) + '\n\n# Finance notes') + ('neutraltext ' * 165)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/helios-materials-browser'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix='helios-materials-') as temp:
        state = Path(temp)
        for sector in ['finance', 'manufacturing']:
            runtime = released(state, sector)
            runtime.close()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        with (args.output / 'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'start_demo.py'), '--dataset', 'manufacturing', '--state-dir', temp, '--port', str(port)], cwd=ROOT, stdout=log, stderr=log, env={**os.environ, 'PYSTOW_HOME': str(state / 'pystow')})
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(base + '/demo/api/config', timeout=1)
                        break
                    except Exception:
                        if process.poll() is not None:
                            raise RuntimeError('Preview exited')
                        time.sleep(.2)
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    for width in [1440, 390]:
                        page = browser.new_page(viewport={'width': width, 'height': 1000})
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        before = page.request.get(base + '/demo/api/context?source=manufacturing').json()
                        finance_before = page.request.get(base + '/demo/api/context?source=finance').json()
                        page.goto(base + '/demo/context?source=manufacturing#source', wait_until='networkidle')
                        expect(page.locator('#add-supporting-material')).to_have_attribute('href', '/demo/materials?source=manufacturing')
                        expect(page.locator('#local-document-notes')).not_to_have_attribute('open', '')
                        expect(page.locator('#document-add')).not_to_be_visible()
                        assert page.get_by_text('Open supporting materials library', exact=True).count() == 0
                        page.locator('#add-supporting-material').click()
                        expect(page.locator('#return-material-studio')).to_have_attribute('href', '/demo/context?source=manufacturing#source')
                        expect(page.locator('#material-source-context')).to_contain_text('manufacturing')
                        expect(page.locator('.material-paths')).to_contain_text('or do both')
                        page.locator('#material-file').set_input_files({'name': f'materials-{width}.md', 'mimeType': 'text/markdown', 'buffer': TEXT.encode()})
                        page.locator('#upload-submit').click()
                        expect(page.locator('#materials-notice')).to_contain_text('Material uploaded', timeout=30000)
                        page.locator('#material-chunks').evaluate('el => el.closest("details").open=true')
                        expect(page.locator('#material-chunks')).to_contain_text('<img src=x')
                        assert page.locator('#material-chunks img').count() == 0
                        assert not page.evaluate('Boolean(window.materialInjection)')
                        expect(page.locator('#use-embeddings')).to_be_disabled()
                        page.locator('#suggest-material').click()
                        expect(page.locator('#materials-notice')).to_contain_text('Candidate links ready', timeout=30000)
                        document_id = page.evaluate('new URL(location.href).searchParams.get("document")')
                        assert document_id, 'Uploaded document should remain addressable'
                        expect(page.locator('#link-source')).to_have_value('manufacturing')
                        scores = page.locator('.material-link').evaluate_all('els => els.map(el => Number(el.dataset.score))')
                        assert scores == sorted(scores, reverse=True), scores
                        expect(page.locator('#material-model')).to_have_value('manufacturing')
                        detail = page.request.get(base + f'/demo/api/materials/{document_id}').json()
                        targets = [link for link in detail['links'] if link['source'] == 'manufacturing']
                        assert targets, detail
                        assert any(link['source'] == 'finance' for link in detail['links']), 'Expected cross-model finance candidates'
                        assert detail['analysis'] is None, 'Keyword matching must work without LLM analysis'
                        page.locator('#link-source').select_option('manufacturing')
                        page.locator('#link-status').select_option('suggested')
                        page.locator('#select-matching-links').click()
                        assert page.locator('#material-links input:checked').count() == len(targets)
                        page.locator('#clear-material-selection').click()
                        assert page.locator('#material-links input:checked').count() == 0
                        page.locator('#link-source').select_option('')
                        page.locator('#link-status').select_option('')
                        link_id = next(t for t in targets if t['target'].startswith(('field:', 'table:')))['id']
                        chosen = page.locator(f'[data-link-id="{link_id}"] input')
                        chosen.check()
                        page.locator('#material-reviewer').fill('Browser reviewer')
                        page.locator('#material-review-note').fill('Verified the document quote and manufacturing scope.')
                        page.locator('#approve-material').click()
                        expect(page.locator('#materials-notice')).to_contain_text('Selected links approved', timeout=30000)
                        expect(chosen).to_be_checked()
                        page.locator('#material-model').select_option('manufacturing')
                        expect(page.locator('#apply-material')).to_be_enabled()
                        page.locator('#apply-material').click()
                        expect(page.locator('#materials-notice')).to_contain_text('Approved evidence and document lineage added', timeout=30000)
                        expect(page.locator('#open-material-studio')).to_have_text('Open Studio to draft with AI')
                        expect(page.locator('#open-material-studio')).to_have_attribute('href', '/demo/context?source=manufacturing&draft=ai#source')
                        after = page.request.get(base + '/demo/api/context?source=manufacturing').json()
                        assert after['draft']['revision'] > before['draft']['revision']
                        for key in ['versions', 'active_version']:
                            if key in before:
                                assert after[key] == before[key], (key, before[key], after[key])
                        assert page.request.get(base + '/demo/api/context?source=finance').json() == finance_before
                        page.screenshot(path=str(args.output / f'materials-reviewed-{width}.png'), full_page=True)
                        # Inspect applied library provenance and its semantic evidence edge in Studio.
                        studio = browser.new_page(viewport={'width': 1440, 'height': 1000})
                        studio.on('pageerror', lambda error: errors.append(str(error)))
                        studio.goto(base + page.locator('#open-material-studio').get_attribute('href'), wait_until='networkidle')
                        expect(studio.locator('#evidence-draft')).to_be_visible()
                        expect(studio.locator('#propose-llm')).to_have_text('Draft semantic definitions with AI')
                        assert studio.request.get(base + '/demo/api/context?source=manufacturing').json()['draft']['revision'] == after['draft']['revision']
                        studio.locator('#tab-define').click()
                        group = studio.locator('[data-node-id="evidence:documents"]')
                        expect(group).to_be_visible(timeout=30000)
                        group.focus()
                        group.press('Enter')
                        filename = f"{document_id}-r1.md"
                        studio.locator('#source-inspector .document-inspector-item').filter(has_text=filename).click()
                        inspector = studio.locator('#source-inspector')
                        expect(inspector).to_contain_text('Reviewed semantic links')
                        expect(inspector).to_contain_text('Browser reviewer')
                        expect(inspector).to_contain_text('Verified the document quote')
                        expect(inspector).to_contain_text('Original upload checksum')
                        expect(inspector).not_to_contain_text('Model-wide context')
                        studio.locator('#studio-canvas').get_by_role('button', name='View options', exact=True).click()
                        studio.locator('#studio-canvas select[aria-label="Graph view"]').select_option('metadata')
                        expect(studio.locator('path[data-edge-id^="semantic-evidence:"]')).to_have_count(1)
                        studio.screenshot(path=str(args.output / f'materials-studio-{width}.png'), full_page=True)
                        studio.close()

                        # A new document revision must leave the original revision read-only.
                        page.locator('#upload-document').select_option(document_id)
                        page.locator('#material-file').set_input_files({'name': f'materials-{width}-r2.txt', 'mimeType': 'text/plain', 'buffer': (TEXT + '\nRevised policy: inspect current manufacturing maintenance definitions.\n').encode()})
                        page.locator('#upload-submit').click()
                        expect(page.locator('#materials-notice')).to_contain_text('Material uploaded', timeout=30000)
                        expect(page.locator('#material-revision')).to_have_value('2')
                        page.locator('#material-revision').select_option('1')
                        expect(page.locator('#revision-note')).to_contain_text('historical revision')
                        expect(page.locator('#suggest-material')).to_be_disabled()
                        expect(page.locator('#apply-material')).to_be_disabled()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page has horizontal overflow'
                        page.screenshot(path=str(args.output / f'materials-{width}.png'), full_page=True)
                        assert not errors, errors
                        expect(page.locator('#materials-error')).not_to_be_visible()
                        outcomes.append({'width': width, 'status': 'passed', 'document': document_id})
                        page.close()
                    browser.close()
            finally:
                process.terminate()
                process.wait(timeout=15)
    (args.output / 'results.json').write_text(json.dumps(outcomes, indent=2))
    print(json.dumps(outcomes, indent=2))


if __name__ == '__main__':
    main()
