from pathlib import Path
import os
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parent
out=root/'screenshots';out.mkdir(exist_ok=True)
with sync_playwright() as p:
    options={'headless':True}
    if os.getenv('SCREENSHOT_CHROMIUM_PATH'):options['executable_path']=os.environ['SCREENSHOT_CHROMIUM_PATH']
    browser=p.chromium.launch(**options)
    page=browser.new_page(viewport={'width':1500,'height':1100},device_scale_factor=2)
    errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if not r.url.startswith(('file:','data:','https://isomer-user-content.by.gov.sg/302/316d5d40-0b43-4a81-ab58-c4edd8b076f2/sp_group.png')) else None)
    for key in ['index','context','observability','nifi','data']:
        page.goto((root/(key+'.html')).as_uri(),wait_until='networkidle')
        page.wait_for_function("document.querySelector('.sp-group-logo').complete && document.querySelector('.sp-group-logo').naturalWidth > 0")
        expect(page.locator('.brand')).to_have_attribute('aria-label','SP Group AI workspace home')
        expect(page.locator('.notice')).to_contain_text('sample' if key in ['index','context'] else 'Sample preview')
        assert page.locator('nav .nav-item').all_text_contents()==['Sources','Build semantic context','NiFi01','Observability02','Data understanding03']
        assert page.locator('.nav-label').inner_text()=='WORKSPACE'
        assert page.locator('.nav-group-label').all_text_contents()==['Prepare','Explore']
        assert page.locator('.top-actions').inner_text().splitlines()==['Demo workspace','Models','Access settings','SP','SP Group workspace','Shared access']
        assert 'Screenshot' not in page.locator('.sidebar').inner_text()
        assert 'screenshot' not in page.locator('body').inner_text().lower()
        if key=='observability':
            expect(page.locator('.query-panel')).to_be_visible()
            expect(page.locator('.evidence')).to_be_visible()
            assert page.locator('.query-panel #result .chart').count()==1
            assert page.locator('.query-panel #result .donut').count()==1
            assert page.locator('.query-panel #result .answer').count()==2
            assert page.locator('.page > .stats .stat > span').all_text_contents()==['QUERY TARGET','PLANNING','SEMANTIC CONTEXT','CONNECTIONS']
            expect(page.locator('#question')).to_contain_text('Summarize the errors')
            expect(page.locator('#source')).to_be_visible()
        if key=='data':
            expect(page.locator('.query-panel')).to_be_visible()
            expect(page.locator('.evidence')).to_be_visible()
            expect(page.locator('#helios-panel')).to_be_visible()
            expect(page.locator('#minutes')).to_be_disabled()
            assert page.locator('.query-panel #result .chart').count()==1
            assert page.locator('.query-panel #result tbody tr').count()==7
            assert page.locator('.query-panel #result .stat').count()==4
            expect(page.locator('#result .answer')).to_contain_text('8,547.28 kWh')
            expect(page.locator('#question')).to_contain_text('measured imported energy')
            assert page.locator('.page > .stats .stat > span').all_text_contents()==['QUERY TARGET','PLANNING','SEMANTIC CONTEXT','CONNECTIONS']
        if key=='context':
            for index,name in enumerate(['power_measured_import','power_feeder_demand','meter_ingestion_observability']):
                page.locator(f'[data-model="{index}"]').click()
                expect(page.locator('#model-detail h2').first).to_have_text(name)
                page.screenshot(path=str(out/f'context-{index+1}.png'),full_page=True)
            page.locator('[data-model="0"]').click()
        for width,height in [(1500,1100),(1920,1080),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),(key,width)
            page.screenshot(path=str(out/f'{key}-{width}.png'),full_page=True)
        page.set_viewport_size({'width':1500,'height':1100})
        # Every page must also open as a local file. The logo may require network access.
        page.goto((root/(key+'.html')).as_uri(),wait_until='load')
        expect(page.locator('h1')).to_be_visible()
    assert not errors,errors
    assert not external,external
    browser.close()
    print('PASS: five local pages, three model selections, desktop/mobile layouts, 18 PNG exports, no JavaScript errors and no unexpected external requests.')
