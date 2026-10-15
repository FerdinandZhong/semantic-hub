"""Offline visual extraction UI checks with intercepted API fixtures."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import json,copy
output=Path('/tmp/helios-materials-visual-browser');output.mkdir(exist_ok=True)
root=Path(__file__).resolve().parents[1] / 'console'
base={'document_id':'visual','revision':1,'latest_revision':1,'revisions':[1],'filename':'report.png','title':'Report','status':'uploaded','chunk_count':0,'sha256':'fixture','chunks':[],'links':[],'models':[],'visual_source':{'page_count':2,'visual_capable':True},'fact_models':[]}
extraction={'extraction_id':'extract-1','pages':[1],'summary':'Revenue chart','observations':[{'id':'row-1','entity':'Example','metric':'<img src=x onerror=window.injected=true>','value':12,'unit':'USD','period':'2025','population':'All','denominator':None,'source_quote':'Revenue 12','uncertainty':'Chart approximation','page':1,'extraction_kind':'chart'}]}
with sync_playwright() as p:
 browser=p.chromium.launch()
 for width in [1440,390]:
  page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)));state=copy.deepcopy(base);bodies=[]
  def route(r):
   path=r.request.url.split('http://fixture')[1].split('?')[0]
   if path=='/demo/materials':r.fulfill(body=(root/'templates/demo-materials.html').read_text(),content_type='text/html')
   elif path.startswith('/static/'):
    f=root/'static'/path.split('/')[-1];r.fulfill(body=f.read_bytes() if f.exists() else b'',content_type='application/javascript' if path.endswith('.js') else 'text/css')
   elif path.endswith('/preview'):r.fulfill(body=b'',content_type='image/png')
   elif path=='/demo/api/materials':r.fulfill(json={'items':[state],'embedding_ready':False})
   elif path.endswith('/visual') and r.request.method == 'POST':
    if state.get('visual_extraction'):
     state['revision']+=1;state['latest_revision']=state['revision'];state['revisions'].append(state['revision']);state['fact_models']=[]
    state['visual_extraction']=copy.deepcopy(extraction);state['visual_extraction']['pages']=r.request.post_data_json['pages'];r.fulfill(json=state)
   elif path.endswith('/facts'):
    bodies.append(r.request.post_data_json);state['fact_models']=[{'source':'facts','extraction_id':'extract-1','studio_url':'/demo/context?source=facts'}];r.fulfill(json={'document':state,'source':'facts','studio_url':'/demo/context?source=facts'})
   else:r.fulfill(json=state)
  page.route('**/*',route);page.goto('http://fixture/demo/materials?document=visual');expect(page.locator('#visual-stage')).to_be_visible();expect(page.locator('#text-analysis-stage')).not_to_be_visible()
  page.locator('#visual-pages').fill('1, 1');page.locator('#analyze-visual').click();expect(page.locator('#materials-error')).to_contain_text('distinct')
  page.locator('#visual-pages').fill('1');page.locator('#analyze-visual').click();expect(page.locator('#visual-summary')).to_contain_text('Needs review')
  assert page.locator('#visual-rows img').count()==0;assert not page.evaluate('Boolean(window.injected)');expect(page.locator('#approve-visual')).to_be_disabled();page.locator('input[data-select]').check();page.locator('[data-field=value]').fill('13.5');page.locator('#visual-approval summary').click();page.locator('#visual-reviewer').fill('Reviewer');page.locator('#visual-review-note').fill('Compared against the original chart');page.locator('#visual-acknowledged').check();page.screenshot(path=str(output/f'visual-review-{width}.png'),full_page=True);page.locator('#approve-visual').click();expect(page.locator('#materials-notice')).to_contain_text('created a draft model');expect(page.locator('#analyze-visual')).to_be_enabled();assert bodies[0]['rows'][0]['value']==13.5;assert bodies[0]['acknowledged'] is True;expect(page.locator('#materials-notice a')).to_have_attribute('href','/demo/context?source=facts');assert not errors,errors
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),width
  page.screenshot(path=str(output/f'visual-approved-{width}.png'),full_page=True)
  page.locator('#visual-pages').fill('2');page.locator('#analyze-visual').click();expect(page.locator('#material-revision')).to_have_value('2');expect(page.locator('#visual-acknowledged')).not_to_be_checked();expect(page.locator('#matching-scope')).to_have_value('analyzed');expect(page.locator('#visual-pages')).to_have_value('2');expect(page.locator('#analyze-visual')).to_be_enabled()
  state['revision']=1;state['fact_models']=[];state['latest_revision']=2;state['revisions']=[1,2];page.reload();expect(page.locator('#analyze-visual')).to_be_disabled();expect(page.locator('input[data-select]')).to_be_disabled();state['latest_revision']=1;state['fact_review_pending']={'revision':1,'extraction_id':'extract-1','rows':[{'id':'row-1','value':99}], 'acknowledged':True};page.reload();expect(page.locator('#finish-visual-model')).to_be_visible();expect(page.locator('#analyze-visual')).to_be_disabled();page.locator('#finish-visual-model').click();expect(page.locator('#materials-notice')).to_contain_text('created a draft model');assert bodies[-1]['rows'][0]['value']==99;page.close();print(f'{width}: visual review, edited value, approval, repeat extraction, history, no overflow passed')
 browser.close()
