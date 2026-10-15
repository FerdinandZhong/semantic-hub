import copy
import hashlib
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.banking_access import Caller,PlatformDecision,authenticate,require_execution
from app.config import Settings
from app.connectors import ConnectionFailure
from app.contracts import Plan
from app.main import create_app
from app.samples import model
from app.semantic_retrieval import SemanticIndex,Clarification,validate_request
from app.semantics import digest,compile_query

HELIOS=os.environ.get('TEST_HELIOS_PATH','')


def caller(doc,fields,subject='alice'):
    return Caller(subject,'analyst','p1',digest(doc),fields)


def test_restricted_dependencies_never_enter_bundle():
    doc=model();doc['datasets'][0]['fields'].append({'name':'private_salary','description':'Confidential payroll','expression':{'dialects':[{'dialect':'ANSI_SQL','expression':'private_salary'}]}})
    doc['metrics'].append({'name':'salary_total','expression':{'dialects':[{'dialect':'ANSI_SQL','expression':'SUM(payments.private_salary)'}]}})
    identity=caller(doc,{'iceberg.demo.payments':['amount_sgd','jurisdiction']})
    index=SemanticIndex(doc,identity)
    bundle,evidence=index.bundle('total outward payments by jurisdiction')
    serialized=json.dumps(bundle)
    assert 'private_salary' not in serialized and 'salary_total' not in serialized and 'customer_id' not in serialized
    assert {f['name'] for f in bundle['datasets'][0]['fields']}=={'amount_sgd','jurisdiction'}
    assert evidence['release_sha256']==digest(doc) and evidence['policy_revision']=='p1'
    with pytest.raises(Clarification):index.bundle('private_salary')


def test_two_principals_receive_different_semantics():
    doc=model()
    alice=SemanticIndex(doc,caller(doc,{'iceberg.demo.payments':['amount_sgd']})).authorized_document()
    bob=SemanticIndex(doc,caller(doc,{'iceberg.demo.payments':['jurisdiction']},'bob')).authorized_document()
    assert alice['metrics'] and bob['metrics']==[]
    assert 'amount_sgd' not in json.dumps(bob) and 'jurisdiction' not in json.dumps(alice)


def joined_model():
    doc=model()
    doc['datasets'].append({'name':'customers','source':'iceberg.demo.customers','fields':[
        {'name':'id','expression':{'dialects':[{'dialect':'ANSI_SQL','expression':'id'}]}},
        {'name':'country','description':'Customer country','dimension':{},'expression':{'dialects':[{'dialect':'ANSI_SQL','expression':'country'}]}}]})
    doc['relationships']=[{'name':'payment_customer','from':'payments','to':'customers','from_columns':['customer_id'],'to_columns':['id']}]
    return doc


def test_join_dependency_closure_and_denied_join_key():
    doc=joined_model();scopes={'iceberg.demo.payments':['amount_sgd','customer_id'],'iceberg.demo.customers':['id','country']}
    bundle,_=SemanticIndex(doc,caller(doc,scopes)).bundle('total outward payments by country')
    assert bundle['relationships'][0]['name']=='payment_customer'
    assert {(d['name'],f['name']) for d in bundle['datasets'] for f in d['fields']}=={('payments','amount_sgd'),('payments','customer_id'),('customers','id'),('customers','country')}
    scopes['iceberg.demo.customers']=['country']
    with pytest.raises(Clarification,match='join path'):SemanticIndex(doc,caller(doc,scopes)).bundle('total outward payments by country')


def test_parallel_relationships_require_a_reviewed_default():
    doc=joined_model();other=copy.deepcopy(doc['relationships'][0]);other['name']='alternative';doc['relationships'].append(other)
    with pytest.raises(Clarification,match='relationships'):SemanticIndex(doc).bundle('total outward payments by country')
    doc['relationships'][0]['custom_extensions']=[{'vendor_name':'HELIOS','data':json.dumps({'is_default':True})}]
    bundle,_=SemanticIndex(doc).bundle('total outward payments by country')
    assert [rel['name'] for rel in bundle['relationships']]==['payment_customer']


def test_ambiguity_and_budget_do_not_expand_to_full_model():
    doc=model();other=copy.deepcopy(doc['metrics'][0]);other['name']='net_outward_payments';doc['metrics'].append(other)
    with pytest.raises(Clarification,match='Choose an approved metric'):SemanticIndex(doc).bundle('outward payments')
    with pytest.raises(Clarification,match='context budget'):SemanticIndex(model()).bundle('total outward payments',max_chars=50)


def test_large_catalog_keeps_prompt_bounded():
    doc=model()
    for index in range(2000):
        doc['datasets'].append({'name':f'archive_{index}','source':f'iceberg.archive.table_{index}','fields':[
            {'name':f'field_{n}','expression':{'dialects':[{'dialect':'ANSI_SQL','expression':f'field_{n}'}]}} for n in range(30)]})
    bundle,evidence=SemanticIndex(doc).bundle('total outward payments')
    assert evidence['dataset_count']==1 and evidence['field_count']<=3 and evidence['context_chars']<24000
    assert 'archive_1999' not in json.dumps(bundle)


def test_opaque_extensions_stay_out_of_prompts():
    doc=model();doc['datasets'][0]['custom_extensions']=[{'vendor_name':'PRIVATE','data':'restricted metadata'}]
    bundle,_=SemanticIndex(doc).bundle('total outward payments')
    assert 'restricted metadata' not in json.dumps(bundle)


def test_declared_metric_source_must_be_permitted():
    doc=joined_model()
    doc['metrics'][0]['custom_extensions']=[{'vendor_name':'HELIOS','data':json.dumps({'dataset':'customers'})}]
    identity=caller(doc,{'iceberg.demo.payments':['amount_sgd']})
    authorized=SemanticIndex(doc,identity).authorized_document()
    assert authorized['metrics']==[] and 'customers' not in json.dumps(authorized)


def test_real_helios_compiles_bundle_and_rejects_unretrieved_field():
    if not Path(HELIOS,'shared/helios_core').exists():pytest.skip('Helios checkout required')
    settings=Settings(helios_path=HELIOS)
    doc=model()
    for n in range(20):doc['datasets'][0]['fields'].append({'name':f'zz_unused_{n}','expression':{'dialects':[{'dialect':'ANSI_SQL','expression':f'zz_unused_{n}'}]}})
    bundle,_=SemanticIndex(doc).bundle('total outward payments')
    request={'metrics':['total_outward_payments']}
    validate_request(settings,bundle,request)
    assert 'SUM' in compile_query(settings,bundle,request).upper()
    with pytest.raises(ConnectionFailure):validate_request(settings,bundle,{**request,'dimensions':['payments.zz_unused_9']})


def secured(tmp_path,platform=None):
    doc=model();model_file=tmp_path/'model.json';model_file.write_text(json.dumps(doc))
    policy={'schema':'uob.access.v1','revision':'p1','principals':[
        {'subject':subject,'role':role,'token_sha256':hashlib.sha256(token.encode()).hexdigest(),
         'model_sha256':digest(doc),'fields':{'iceberg.demo.payments':fields}}
        for subject,role,token,fields in [('alice','analyst','alice-fixture',['amount_sgd']),('bob','analyst','bob-fixture',['jurisdiction']),('operator','operator','operator-fixture',['amount_sgd','jurisdiction'])]]}
    path=tmp_path/'policy.json';path.write_text(json.dumps(policy))
    settings=Settings(access_policy_file=str(path),api_token='old-shared',semantic_file=str(model_file),semantic_sha=digest(doc),semantic_version='r1',helios_path=HELIOS,llm_url='',llm_model='')
    return TestClient(create_app(settings,tmp_path/'settings.json',platform)),settings,path


def head(token='alice-fixture'):return {'Authorization':'Bearer '+token}


def test_authenticated_scopes_and_operator_boundary(tmp_path):
    client,_,_=secured(tmp_path)
    assert client.get('/api/semantics',headers=head('old-shared')).status_code==401
    alice=client.get('/api/semantics',headers=head()).json()
    bob=client.get('/api/semantics',headers=head('bob-fixture')).json()
    assert 'amount_sgd' in str(alice) and 'jurisdiction' not in str(alice)
    assert 'amount_sgd' not in str(bob) and 'jurisdiction' in str(bob)
    for path in ['/api/settings','/api/semantic-workspace','/api/connections','/api/observability-context']:
        assert client.get(path,headers=head()).status_code==403
    assert client.post('/api/settings/connections/data',json={},headers=head()).status_code==403
    assert client.post('/api/query',json={'tab':'nifi','question':'show status'},headers=head()).status_code==403
    forged={'tab':'data','question':'show payments','subject':'operator'}
    assert client.post('/api/query',json=forged,headers=head()).status_code==422


def test_prompt_contains_only_retrieved_permitted_definitions(tmp_path,monkeypatch):
    client,_,_=secured(tmp_path)
    captured=[]
    async def planner(query,settings,semantic_doc,*args):
        captured.append(json.dumps(semantic_doc));return Plan(tool='semantic_describe'),'fixture'
    monkeypatch.setattr('app.orchestration.plan_query',planner)
    result=client.post('/api/query',json={'tab':'data','question':'total outward payments'},headers=head()).json()
    assert result['status']=='completed'
    assert 'jurisdiction' not in captured[0] and 'customer_id' not in captured[0]
    assert result['semantic_retrieval']['release_sha256']
    captured.clear()
    response=client.post('/api/query',json={'tab':'data','question':'private_salary'},headers=head())
    assert response.json()['status']=='needs_clarification' and captured==[]


def test_unavailable_execution_never_uses_shared_account(tmp_path,monkeypatch):
    client,_,_=secured(tmp_path)
    async def planner(*args):return Plan(tool='semantic_query',semantic={'metrics':['total_outward_payments']}),'fixture'
    monkeypatch.setattr('app.orchestration.plan_query',planner)
    monkeypatch.setattr('app.orchestration.execute_trino',lambda *args:pytest.fail('Shared-account fallback'))
    response=client.post('/api/query',json={'tab':'data','question':'total outward payments'},headers=head())
    assert response.status_code==503 and response.json()['sample_fallback'] is False
    assert 'No shared-account fallback' in response.json()['error']


@pytest.mark.parametrize('decision',[PlatformDecision(True,False,'alice'),PlatformDecision(True,True,'bob')])
def test_platform_identity_checks_fail_closed(tmp_path,decision):
    _,settings,path=secured(tmp_path)
    identity=authenticate(path,'Bearer alice-fixture')
    class Platform:
        def authorize(self,*args):return decision
    with pytest.raises(ConnectionFailure):require_execution(settings,Platform(),identity,{'iceberg.demo.payments'})


def test_policy_revocation_and_release_change(tmp_path):
    client,settings,path=secured(tmp_path)
    identity=authenticate(path,'Bearer alice-fixture')
    doc=model();doc['name']='new release'
    with pytest.raises(ConnectionFailure,match='release'):SemanticIndex(doc,identity)
    policy=json.loads(path.read_text());policy['principals']=[];path.write_text(json.dumps(policy))
    assert client.get('/api/semantics',headers=head()).status_code==401
    with pytest.raises(ConnectionFailure,match='changed'):require_execution(settings,object(),identity,{'iceberg.demo.payments'})
    path.write_text('invalid')
    assert client.get('/api/semantics',headers=head()).status_code==503


def test_live_preparation_cannot_bypass_execution_boundary(tmp_path,monkeypatch):
    client,_,_=secured(tmp_path)
    monkeypatch.setattr('app.source_workflow.execute_trino',lambda *a:pytest.fail('Live discovery bypass'))
    assert client.post('/api/sources/discover',json={'mode':'live','action':'catalogs'},headers=head('operator-fixture')).status_code==503
    client.app.state.semantic_workspace.data['drafts']['live']={'id':'live','mode':'live'}
    assert client.post('/api/semantic-workspace/drafts/live/validate',json={'revision':1,'reference_sql':'SELECT 1'},headers=head('operator-fixture')).status_code==503
    assert client.post('/api/semantic-workspace/releases/live/activate',json={},headers=head('operator-fixture')).status_code==503


def test_verified_adapter_fixture_executes_compiled_bundle(tmp_path,monkeypatch):
    """Application integration only; this fixture is not database enforcement evidence."""
    class Platform:
        def __init__(self):self.checks=[];self.calls=[]
        def authorize(self,settings,identity,sources):
            self.checks.append((identity.subject,sources))
            return PlatformDecision(True,True,identity.subject)
        def execute(self,settings,sql,identity):
            self.calls.append((identity.subject,sql))
            return [{'total_outward_payments':4900}]
    platform=Platform();client,_,_=secured(tmp_path,platform)
    async def planner(*args):return Plan(tool='semantic_query',semantic={'metrics':['total_outward_payments']}),'fixture'
    monkeypatch.setattr('app.orchestration.plan_query',planner)
    response=client.post('/api/query',json={'tab':'data','question':'total outward payments'},headers=head())
    assert response.status_code==200,response.text
    assert response.json()['rows']==[{'total_outward_payments':4900}]
    assert len(platform.checks)==2 and len(platform.calls)==1
    assert platform.calls[0][0]=='alice' and 'jurisdiction' not in platform.calls[0][1]
    # Bob lacks the metric inputs, so retrieval stops before the adapter is called.
    result=client.post('/api/query',json={'tab':'data','question':'total outward payments'},headers=head('bob-fixture')).json()
    assert result['status']=='needs_clarification' and len(platform.calls)==1


def test_compile_preview_cannot_escape_scope(tmp_path):
    client,_,_=secured(tmp_path)
    response=client.post('/api/semantics/compile',json={'metrics':['total_outward_payments'],'dimensions':['payments.customer_id']},headers=head())
    assert response.status_code==503 and 'customer_id' not in response.text
