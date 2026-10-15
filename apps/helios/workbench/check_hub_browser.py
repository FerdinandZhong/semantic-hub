"""Exercise Hub navigation and saved source profiles on an isolated local instance."""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8086')
    parser.add_argument('--output', type=Path, default=Path('/tmp/helios-hub-browser'))
    parser.add_argument('--preview-only', action='store_true', help='Capture existing state without creating or editing sources')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in [(1440, 1000), (390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            def shot(name):
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), name
                page.screenshot(path=str(args.output / f'{width}-{name}.png'), full_page=True)
            page.goto(args.base, wait_until='networkidle')
            expect(page.locator('h1')).to_have_text('Semantic Hub')
            expect(page.locator('.source-card').first).to_be_visible()
            shot('hub')
            page.locator('#source-search').fill('power')
            expect(page.locator('.source-card')).to_have_count(1)
            page.get_by_role('button', name='Details', exact=True).click()
            expect(page.locator('#detail-title')).to_have_text('Power sample')
            expect(page.locator('#connection-details')).to_contain_text('power')
            shot('source-details')
            if args.preview_only:
                page.locator('#source-search').fill('')
                page.locator('#close-detail').click()
                page.locator('#configure-source').click()
                page.locator('#connection-kind').select_option('trino')
                shot('connection-dialog')
                page.locator('#connection-close').click()
                page.goto(args.base + '/demo/context?source=power', wait_until='networkidle')
                expect(page.locator('#studio-canvas .canvas-node').first).to_be_visible()
                shot('studio')
                assert not errors, errors
                results.append({'width': width, 'preview_only': True, 'javascript_errors': errors, 'passed': True})
                page.close()
                continue
            page.locator('#detail-actions').get_by_role('link', name='Open Studio').click()
            expect(page.locator('#source-nav-title')).to_have_text('Power sample')
            expect(page.locator('#studio-canvas .canvas-node').first).to_be_visible()
            page.locator('#nav-versions').click()
            expect(page.locator('#workspace-heading')).to_have_text('Versions & releases')
            assert parse_qs(urlparse(page.url).query)['source'] == ['power']
            page.locator('nav').get_by_role('link', name='Model playground', exact=True).click()
            expect(page.locator('#source-nav-title')).to_have_text('Power sample')
            assert parse_qs(urlparse(page.url).query)['source'] == ['power']
            page.locator('nav').get_by_role('link', name='Semantic Hub', exact=True).click()
            expect(page.locator('h1')).to_have_text('Semantic Hub')
            configs = {
                'local': {'pack_id': 'finance'},
                'iceberg': {'catalog_uri': 'https://catalog.example.test', 'warehouse': 's3://demo/warehouse'},
                'trino': {'endpoint': 'https://trino.example.test', 'catalog': 'iceberg', 'schema': 'analytics'},
                'atlas': {'endpoint': 'https://atlas.example.test', 'credential_ref': 'ATLAS_TOKEN'},
            }
            for kind, config in configs.items():
                page.locator('#configure-source').click()
                page.locator('#connection-name').fill(f'Browser {kind} {width}')
                page.locator('#connection-kind').select_option(kind)
                for key, value in config.items():
                    field = page.locator(f'#connection-config [name="{key}"]')
                    if key == 'pack_id':
                        field.select_option(value)
                    else:
                        field.fill(value)
                shot(f'configure-{kind}')
                page.locator('#connection-save').click()
                expect(page.locator('#connection-dialog')).not_to_be_visible()
                expect(page.locator('#detail-title')).to_have_text(f'Browser {kind} {width}')
                source = parse_qs(urlparse(page.url).query)['source'][0]
                page.locator('#detail-actions').get_by_role('link', name='Open Studio').click()
                if kind == 'local':
                    expect(page.locator('#source-nav-title')).to_have_text(f'Browser {kind} {width}')
                    expect(page.locator('#studio-canvas .canvas-node').first).to_be_visible()
                    page.locator('[data-inspector="metric"]').click()
                    page.locator('#metric-description').fill(f'Custom finance connection {width}')
                    page.locator('#save').click()
                    expect(page.locator('#notice')).to_contain_text('saved')
                    custom = page.request.get(args.base + '/demo/api/context', params={'source': source}).json()
                    original = page.request.get(args.base + '/demo/api/context?source=finance').json()
                    assert custom['draft']['revision'] == 1
                    assert original['draft']['revision'] == 0
                    shot('local-studio')
                else:
                    expect(page.locator('#source-name')).to_have_text(f'Browser {kind} {width}')
                    expect(page.locator('#adapter-status')).to_be_visible()
                    assert page.request.get(args.base + '/demo/api/config', params={'source': source}).status == 409
                    shot(f'{kind}-setup')
                page.goto(args.base + '/demo', wait_until='networkidle')
            # Two browser tabs retain independent source selection.
            second = browser.new_page()
            second.goto(args.base + '/demo/context?source=finance', wait_until='networkidle')
            page.goto(args.base + '/demo/context?source=power', wait_until='networkidle')
            expect(second.locator('#source-nav-title')).to_have_text('Finance sample')
            expect(page.locator('#source-nav-title')).to_have_text('Power sample')
            assert second.evaluate('window.contextStudio.getState().config.pack_id') == 'finance'
            assert page.evaluate('window.contextStudio.getState().config.pack_id') == 'power'
            second.close()
            assert not errors, errors
            results.append({'width': width, 'source_types': list(configs), 'javascript_errors': errors, 'passed': True})
            page.close()
        browser.close()
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
