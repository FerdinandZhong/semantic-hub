"""Verify the native Studio canvas without saving or reviewing semantic changes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8082')
    parser.add_argument('--browser', help='Optional Chromium executable path')
    parser.add_argument('--source', default='power')
    parser.add_argument('--output', type=Path, default=Path('/tmp/helios-canvas-browser'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path':args.browser} if args.browser else {}))
        page = browser.new_page(viewport={'width':1440, 'height':1100})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.base + '/demo/context?source=' + args.source, wait_until='networkidle')
        expect(page.locator('.canvas-node').first).to_be_visible()
        expect(page.locator('.canvas-edge.derived').first).to_be_visible()
        original = page.evaluate('JSON.stringify(contextStudio.getState())')
        dataset = page.locator('.canvas-node.dataset').first
        dataset.click()
        expect(page.locator('#source-inspector')).to_be_visible()
        page.wait_for_function('!contextStudio.getState().busy')
        before = page.evaluate('JSON.stringify({dirty:contextStudio.getState().dirty,draft:contextStudio.getState().workspace.draft})')
        box = dataset.bounding_box()
        page.mouse.move(box['x']+70, box['y']+25)
        page.mouse.down()
        page.mouse.move(box['x']+130, box['y']+65, steps=8)
        page.mouse.up()
        after = page.evaluate('JSON.stringify({dirty:contextStudio.getState().dirty,draft:contextStudio.getState().workspace.draft})')
        assert before == after, 'Layout drag modified semantic draft or validation'
        expect(page.locator('.canvas-view-options')).not_to_be_visible()
        assert page.locator('.canvas-toolbar button:visible').count() == 6
        page.get_by_role('button',name='View options',exact=True).click()
        assert page.locator('.canvas-stage').evaluate('(e)=>e.getBoundingClientRect().bottom<=e.closest(".semantic-canvas").getBoundingClientRect().bottom+1'), 'View options clipped the graph controls'
        page.get_by_role('combobox',name='Graph view',exact=True).select_option('metadata')
        page.get_by_role('button',name='Fit',exact=True).click()
        page.locator('.canvas-node.metric').first.click()
        all_count=page.locator('.canvas-node').count()
        page.get_by_role('button',name='Neighbors',exact=True).click()
        assert page.locator('.canvas-node').count()<all_count, 'Neighbors did not filter the graph'
        page.get_by_role('button',name='Show all',exact=True).click()
        page.get_by_role('combobox',name='Graph view',exact=True).select_option('metadata')
        assert page.locator('.canvas-node.column').count() > 0
        page.get_by_role('combobox',name='Graph view',exact=True).select_option('semantic')
        page.get_by_role('button',name='Zoom in',exact=True).click()
        page.get_by_role('button',name='Fit',exact=True).click()
        first_name = page.locator('.canvas-node.dataset').first.get_attribute('data-node-id')
        page.get_by_role('searchbox',name='Find graph object').fill(first_name)
        assert page.evaluate('canvasHandle.getState().selected') == first_name
        page.get_by_role('searchbox',name='Find graph object').fill('')
        expect(page.get_by_role('button',name='Save view',exact=True)).to_have_count(0)
        expect(page.get_by_role('combobox',name='Saved layout')).to_have_count(0)
        # Column drill-down must be reversible even after selecting a field.
        for width,height in ((1440,1100),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            page.get_by_role('button',name='Show all',exact=True).click()
            page.locator('.canvas-node.dataset').first.click()
            page.get_by_role('button',name='Neighbors',exact=True).click()
            neighbors=set(page.locator('.canvas-node.dataset').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.nodeId)'))
            assert len(neighbors)>1, 'Fixture must exercise a dataset with neighbors'
            page.get_by_role('button',name='Columns',exact=True).click()
            expect(page.locator('.canvas-node.dataset')).to_have_count(1)
            assert page.locator('.canvas-node.column').count()>0
            page.locator('.canvas-node.column').first.click()
            page.get_by_role('button',name='Neighbors',exact=True).click()
            assert set(page.locator('.canvas-node.dataset').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.nodeId)')) == neighbors
            expect(page.locator('.canvas-node.column')).to_have_count(0)
            expect(page.get_by_role('button',name='Neighbors',exact=True)).to_have_attribute('aria-pressed','true')
            page.get_by_role('button',name='Show all',exact=True).click()
            assert page.locator('.canvas-node.dataset').count() == page.evaluate('sourceGraph.nodes.filter(n=>n.kind==="dataset" || n.type==="dataset").length')
        page.set_viewport_size({'width':1440,'height':1100})
        page.get_by_role('button',name='Fullscreen',exact=True).click()
        page.wait_for_function('document.fullscreenElement === document.getElementById("studio-canvas")')
        expect(page.get_by_role('button',name='Exit fullscreen',exact=True)).to_be_visible()
        page.wait_for_function('(()=>{const r=document.fullscreenElement.getBoundingClientRect();return Math.abs(r.x)<1&&Math.abs(r.y)<1&&Math.abs(r.width-innerWidth)<2&&Math.abs(r.height-innerHeight)<2})()')
        page.screenshot(path=str(args.output/'canvas-fullscreen.png'))
        page.get_by_role('button',name='Exit fullscreen',exact=True).click()
        page.wait_for_function('!document.fullscreenElement')
        expect(page.get_by_role('button',name='Fullscreen',exact=True)).to_be_visible()
        page.get_by_role('button',name='Fullscreen',exact=True).click()
        page.wait_for_function('!!document.fullscreenElement')
        # External browser exit uses the same fullscreenchange event as Escape.
        page.evaluate('document.exitFullscreen()')
        expect(page.get_by_role('button',name='Fullscreen',exact=True)).to_be_visible()
        assert before == page.evaluate('JSON.stringify({dirty:contextStudio.getState().dirty,draft:contextStudio.getState().workspace.draft})')
        page.reload(wait_until='networkidle')
        page.get_by_role('button',name='View options',exact=True).click()
        fields = page.evaluate('sourceGraph.nodes.flatMap(n=>(n.columns||[]).map(c=>({...c,dataset:n.id})))')
        definition = page.evaluate('contextStudio.getState().definition')
        pairs = [(a,b) for a in fields for b in fields if a['dataset']!=b['dataset'] and a['type']==b['type'] and not any(j['from_field']==a['qualified'] and j['to_field']==b['qualified'] for j in definition['joins'])]
        assert pairs, 'Fixture has no available matching cross-dataset fields'
        a,b = pairs[0]
        page.get_by_role('button',name='Connect fields',exact=True).click()
        dialog = page.locator('dialog.canvas-relationship-dialog')
        for width,height in ((1440,1100),(768,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            expect(dialog).to_be_visible()
            assert dialog.locator('form').evaluate('(e)=>getComputedStyle(e).display') == 'flex'
            title_box=dialog.get_by_role('heading',name='Declare a relationship').bounding_box()
            help_box=dialog.get_by_text('The server validates SQL and join cardinality before review.').bounding_box()
            assert title_box['height'] < 60 and help_box['y'] >= title_box['y']+title_box['height']
            assert dialog.evaluate('(e)=>e.scrollWidth<=e.clientWidth')
            action_box=dialog.get_by_role('button',name='Add relationship',exact=True).bounding_box()
            assert action_box['y']+action_box['height'] <= height
            dialog.screenshot(path=str(args.output/f'connect-fields-{width}.png'))
        page.set_viewport_size({'width':1440,'height':1100})
        dialog.locator('[name=from_field]').select_option(a['qualified'])
        dialog.locator('[name=to_field]').select_option(a['qualified'])
        dialog.locator('[name=meaning]').fill('Browser check relationship')
        dialog.get_by_role('button',name='Add relationship',exact=True).click()
        expect(dialog.locator('[role=alert]')).to_contain_text('different fields')
        dialog.locator('[name=to_field]').select_option(b['qualified'])
        dialog.locator('[name=name]').fill('browser_check_relationship')
        dialog.get_by_role('button',name='Add relationship',exact=True).click()
        expect(dialog).to_have_count(0)
        assert page.evaluate('contextStudio.getState().dirty')
        expect(page.locator('.canvas-edge.derived')).to_have_count(0)
        assert page.evaluate('contextStudio.getState().definition.joins.some(j=>j.name==="browser_check_relationship")')
        # Discard the unsaved UI draft. No save or review endpoint is called.
        page.on('dialog',lambda d:d.accept())
        page.locator('#reload').click()
        page.wait_for_function('!contextStudio.getState().busy && !contextStudio.getState().dirty')
        page.get_by_role('combobox',name='Graph view',exact=True).select_option('metadata')
        page.get_by_role('button',name='Edit',exact=True).click()
        page.get_by_role('button',name='Fit',exact=True).click()
        source = page.locator('[data-connect-field="'+a['id']+'"]')
        target = page.locator('[data-node-id="'+b['id']+'"]')
        sb,tb=source.bounding_box(),target.bounding_box()
        page.mouse.move(sb['x']+sb['width']/2,sb['y']+sb['height']/2)
        page.mouse.down()
        page.mouse.move(tb['x']+tb['width']/2,tb['y']+tb['height']/2,steps=8)
        page.mouse.up()
        expect(dialog).to_be_visible()
        expect(dialog.locator('[name=from_field]')).to_have_value(a['qualified'])
        expect(dialog.locator('[name=to_field]')).to_have_value(b['qualified'])
        dialog.get_by_role('button',name='Cancel',exact=True).click()
        page.get_by_role('button',name='View options',exact=True).click()
        expect(page.locator('.canvas-view-options')).not_to_be_visible()
        page.screenshot(path=str(args.output/'canvas-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button',name='View options',exact=True).click()
        expect(page.get_by_role('combobox',name='Graph view')).to_be_visible()
        assert page.locator('.canvas-stage').evaluate('(e)=>e.getBoundingClientRect().bottom<=e.closest(".semantic-canvas").getBoundingClientRect().bottom+1'), 'Mobile view options clipped the graph controls'
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.get_by_role('button',name='View options',exact=True).click()
        page.screenshot(path=str(args.output/'canvas-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
        assert '/demo/context' in page.url, 'Dataset selection changed route'
        assert not errors, errors
        (args.output/'report.json').write_text(json.dumps({'passed':True,'checks':['selection inspector','layout draft isolation','neighbor filter','search zoom lens','columns to neighbors reversal','fullscreen entry and exit','saved-view controls removed','invalid and valid relationship form','drag connection'],'errors':errors},indent=2))
        print('PASS: canvas browser checks; evidence:', args.output)
        browser.close()

if __name__ == '__main__':
    main()
