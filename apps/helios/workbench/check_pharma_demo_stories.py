"""Verify the two pharma demo stories in temporary state, without live AI calls."""
import sys,json,tempfile,csv,base64,re,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'shared')]
from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.registry import PackRegistry,digest
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.materials import MaterialLibrary,MaterialUpload,MaterialSuggest,MaterialReview,MaterialApply
from helios_core.demo.context import ContextDefinition
from helios_core.demo.document_facts import FactRow,MaterialFacts,write_fact_pack,write_json
from apps.helios.tests.test_demo_context import approve_items,review_request,publish
from apps.helios.tests.test_demo_playground import question,run
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pdf',type=Path,required=True)
parser.add_argument('--output',type=Path,default=Path('/tmp/pharma-demo-stories-verification.json'))
args=parser.parse_args()
pdf=args.pdf
def queries(filename):
 s=(ROOT/'docs/demo-inputs'/filename).read_text();s=re.sub(r'--[^\n]*','',s)
 import sqlglot
 return [x.sql(dialect='duckdb') for x in sqlglot.parse(s,read='duckdb') if x is not None]
def verify(runtime,definition):
 w=runtime.workspace;v=w.save(w.view()['draft']['revision'],ContextDefinition.model_validate(definition));v=w.validate(v['draft']['revision']);report=v['draft']['validation'];assert report['passed'],report
 approve_items(runtime);w.review(review_request(runtime));publish(runtime)
 outputs={}
 for m in definition['metrics']:
  plan=runtime.playground.interpret(question(runtime,metric=m['name'],question=m['description']))
  assert plan['status']=='ready',plan
  outputs[m['name']]=run(runtime,plan)['rows']
 return {'validation_passed':True,'metrics':len(report['metrics']),'joins':len(report['joins']),'saved_metric_results':outputs}
report={'checked_on':'2026-10-14','scope':'Isolated temporary workspaces only. No live approvals or publication.', 'live_llm_extraction_tested':False,'row_evidence':'Nine presenter-guide values visually checked against original PDF pages 4 and 5; fixture used to verify SQL and publication.', 'pdf_sha256':digest(pdf.read_bytes())}
registry=PackRegistry(ROOT/'apps/helios/demo-packs.json',ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')
with tempfile.TemporaryDirectory(prefix='helios-story-verification-') as temp:
 temp=Path(temp);r=DemoRuntime(registry.load('pharma_intelligence'),temp/'story1');hub=DemoHub(registry,temp/'story1',r)
 try:
  library=MaterialLibrary(hub);item=library.upload(MaterialUpload(filename=pdf.name,content_base64=base64.b64encode(pdf.read_bytes()).decode()))
  item=library.suggest(item['document_id'],MaterialSuggest(revision=1))
  wanted={'field:industry_observations.indicator','metric:us_new_medicine_sales_share_percent'}
  links=[l for l in item['links'] if l['source']=='pharma_intelligence' and l['location']=='page 14' and l['target'] in wanted]
  assert {l['target'] for l in links}==wanted,[(l['target'],l['location']) for l in item['links'] if l['source']=='pharma_intelligence']
  ids=[l['id'] for l in links]
  library.review(item['document_id'],MaterialReview(revision=1,link_ids=ids,decision='approved',reviewer='Isolated automated test',note='Test-only scope/exclusion linkage for different market definitions; no live approval.'))
  library.apply(item['document_id'],MaterialApply(revision=1,link_ids=ids,source='pharma_intelligence',expected_revision=0))
  definition=r.workspace.view()['draft']['definition']
  qs=queries('story-1-pharma-reference.sql');assert len(qs)==6
  for m,q in zip(definition['metrics'],qs):assert f"AS {m['name']}" in q;m['reference_sql']=q
  report['story1']=verify(r,definition)|{'page14_targets':[l['target'] for l in links]}
 finally:hub.close()
 guide=list(csv.DictReader((ROOT/'docs/demo-inputs/efpia-pages-4-5-row-guide.csv').open()))
 rows=[FactRow(id=f'observation_{i+11}',page=int(x['source_page']),entity=x['entity'],metric=x['metric'],value=float(x['value']),unit=x['unit'],period=x['period'],population=x['population'],denominator=None,source_quote=f"{x['entity']}: {x['value']} (presenter-guide test fixture)",extraction_kind='chart',uncertainty='Isolated SQL test fixture; not live AI output') for i,x in enumerate(guide)]
 item={'document_id':'story2-test','revision':1,'filename':pdf.name,'sha256':digest(pdf.read_bytes()),'visual_extraction':{'model':'reviewed-guide-fixture','observations':[x.model_dump() for x in rows]},'links':[]}
 payload=MaterialFacts(revision=1,extraction_id='a'*64,title='Story 2 isolated verification',rows=rows,reviewer='Isolated automated test',note='Test fixture only; no live user approval',acknowledged=True)
 output=temp/'fact-pack';output.mkdir();entry=write_fact_pack(output,'doc_story2_test',item,payload);write_json(output/'registry.json',{'schema':'helios.demo-registry.v1','packs':[entry]})
 r=DemoRuntime(PackRegistry(output/'registry.json',output).load('doc_story2_test'),temp/'story2')
 try:
  definition=r.workspace.view()['draft']['definition'];qs=queries('story-2-efpia-reference.sql');assert len(qs)==10
  definition['metrics'][0]['reference_sql']=qs[0]
  for m,g,q in zip(definition['metrics'][1:],guide,qs[1:]):m['name']=g['metric_name'];m['reference_sql']=q
  report['story2']=verify(r,definition)
 finally:r.close()
args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
