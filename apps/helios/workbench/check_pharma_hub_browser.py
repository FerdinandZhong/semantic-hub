"""Read-only checks of the pharmaceutical model and unified document navigation."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8084')
    parser.add_argument('--output', type=Path, default=Path('/tmp/helios-pharma-hub-browser'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in [1440, 390]:
            page = browser.new_page(viewport={'width': width, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            before = page.request.get(args.base + '/demo/api/context?source=manufacturing').json()
            page.goto(args.base + '/demo', wait_until='networkidle')
            expect(page.locator('.source-card')).to_have_count(5)
            card = page.locator('.source-card').filter(has_text='Pharmaceutical Industry Intelligence & New Drug Analysis')
            expect(card).to_have_count(1)
            expect(card).to_contain_text('6 metrics · 8 tables')
            page.locator('#source-search').fill('Pharmaceutical Industry')
            expect(page.locator('.source-card')).to_have_count(1)
            page.screenshot(path=str(args.output / f'hub-{width}.png'), full_page=True)
            card.get_by_role('link', name='Open Studio', exact=True).click()
            page.locator('#tab-source').click()
            expect(page.locator('#documents-status')).to_contain_text('4 documents')
            expect(page.locator('#local-document-notes')).not_to_have_attribute('open', '')
            expect(page.locator('#document-add')).not_to_be_visible()
            expect(page.locator('#add-supporting-material')).to_have_attribute('href', '/demo/materials?source=pharma_intelligence')
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
            page.locator('#source-documents').screenshot(path=str(args.output / f'studio-documents-{width}.png'))
            page.locator('#add-supporting-material').click()
            expect(page.locator('#return-material-studio')).to_have_attribute('href', '/demo/context?source=pharma_intelligence#source')
            expect(page.locator('.material-workflow li')).to_have_count(4)
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
            page.screenshot(path=str(args.output / f'materials-{width}.png'), full_page=True)
            after = page.request.get(args.base + '/demo/api/context?source=manufacturing').json()
            assert before == after, 'Navigation must preserve existing manufacturing state'
            assert not errors, errors
            outcomes.append({'width': width, 'status': 'passed', 'manufacturing_unchanged': True, 'page_errors': errors})
            page.close()
        browser.close()
    (args.output / 'results.json').write_text(json.dumps(outcomes, indent=2) + '\n')
    print(json.dumps(outcomes, indent=2))


if __name__ == '__main__':
    main()
