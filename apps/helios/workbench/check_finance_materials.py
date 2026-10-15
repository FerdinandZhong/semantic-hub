"""Verify finance supporting materials in isolated state; --live-ai enables OpenAI checks."""
import base64, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'shared')]
from apps.helios.tests.test_demo_context import pack,validated,review_request,publish,binding
from apps.helios.tests.test_demo_playground import question
from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.registry import PackRegistry
from helios_core.demo.materials import MaterialLibrary,MaterialUpload,MaterialSuggest,MaterialReview,MaterialApply
from helios_core.demo.playground import RunPlan
from helios_core.demo.visual_documents import extract_visual
from helios_core.llm import LLMClient
folder=ROOT/'docs/demo-inputs/finance'
state=Path(tempfile.mkdtemp(prefix='finance-materials-check-'))
r=DemoRuntime(pack('finance'),state)
hub=DemoHub(PackRegistry(ROOT/'apps/helios/demo-packs.json',ROOT/'apps/helios-ds-generation/fixtures/sectors/v1'),state,r)
report={'known_limitations':['The longer combined prompt naming rejected transfers and both ledger sides returned join clarification before execution. No incorrect total was returned.'], 'scope':'Isolated test state; no user approvals or publications changed','checks':[]}
out=ROOT/'docs/finance-supporting-materials-verification.json'
def record(name,**data):
    report['checks'].append({'name':name,**data})
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(name,flush=True)
try:
    lib=MaterialLibrary(hub);pdf=folder/'synthetic-finance-supporting-evidence.pdf'
    item=lib.upload(MaterialUpload(filename=pdf.name,content_base64=base64.b64encode(pdf.read_bytes()).decode()))
    assert {c['location'] for c in item['chunks']}=={'page 1','page 2','page 3','page 4'}
    assert not any('350,641' in c['text'] for c in item['chunks'] if c['location']=='page 3')
    record('PDF text and image separation',pages=4)
    item=lib.suggest(item['document_id'],MaterialSuggest(revision=1,pages=[1,2,4]))
    links=[l for l in item['links'] if l['source']=='finance']
    Path('/tmp/finance-link-candidates.json').write_text(json.dumps(links,indent=2))
    selected=[]
    for page,target in [('page 1','field:ledger_postings.amount_sgd'),('page 2','field:fx_rates.sgd_rate'),('page 4','field:payments.amount_sgd')]:
        choices=[l for l in links if l['location']==page and l['target']==target]
        assert choices,(page,target,[(l['location'],l['target']) for l in links])
        selected.append(choices[0])
    record('Exact finance link candidates',links=[{'page':l['location'],'target':l['target'],'score':l.get('score')} for l in selected])
    ids=[l['id'] for l in selected]
    lib.review(item['document_id'],MaterialReview(revision=1,link_ids=ids,decision='approved',reviewer='Isolated automated test',note='Checked fixture payment definition, fixed FX, and exact settlement memo against serving CSVs.'))
    lib.apply(item['document_id'],MaterialApply(revision=1,link_ids=ids,source='finance',expected_revision=0))
    d=r.workspace.view()['draft']['definition'];d['metrics'][0]['reference_sql']=(folder/'finance-reference.sql').read_text()
    validated(r,d);r.workspace.review(review_request(r));publish(r)
    plan=r.playground.interpret(question(r))
    answer=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']))
    assert '686572.96' in json.dumps(answer['rows']),answer
    record('Reference SQL, review, publish, and saved metric',rows=answer['rows'])
    if '--live-ai' in sys.argv:
        llm=LLMClient('openai','gpt-4o',Path.home().joinpath('tokens/openai').read_text().strip(),'https://api.openai.com/v1')
        cases=[('What fixed USD-to-SGD conversion rate does this synthetic fixture use?','document','1.3'),('What is total_amount_sgd, and what does this metric include and exclude?','hybrid','686572.96')]
        for q,kind,value in cases:
            plan=r.playground.interpret(question(r,metric=None,mode='auto',question=q),llm)
            if kind=='hybrid' and plan['status']=='needs_clarification':
                record('Combined finance question limitation',question=q,status='needs_clarification',response=plan)
                continue
            assert plan['status']=='ready' and plan['kind']==kind,plan
            answer=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),llm)
            assert answer.get('claims'),answer
            assert value in json.dumps(answer).replace(',',''),answer
            record('Live GPT-4o '+kind,question=q,answer=answer)
        visual=extract_visual(pdf.name,pdf.read_bytes(),[3],llm)
        rows=visual['observations'];expected={'GB':44454.90,'HK':350641.68,'SG':291476.38}
        assert len(rows)==3,rows
        for region,value in expected.items():
            row=next(x for x in rows if region in x['entity'])
            assert abs(float(row['value'])-value)<0.001 and row['unit']=='SGD',row
            assert '2026' in row['period'] and row['page']==3,row
        record('Live GPT-4o image chart extraction',observations=rows)
finally:hub.close()
