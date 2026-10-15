"""Published playground boundaries, fixed semantics, and query provenance."""
import copy
import json
import time

import pytest
from pydantic import ValidationError
from helios_core.demo.playground import Question, RunPlan
from helios_core.demo.registry import DemoError
from helios_core.demo.context import ContextDefinition
from helios_core.demo.runtime import DemoRuntime
from helios_core.retrieval.service import RetrievalError
from apps.helios.tests.test_demo_context import pack, validated, review_request, publish, binding


class FakeLLM:
    provider='test'
    model='typed-planner'
    def __init__(self, response):
        self.response=response
        self.calls=[]
    def complete(self, system, prompt):
        self.calls.append((system,prompt))
        return json.dumps(self.response)


def released(tmp_path, sector='manufacturing'):
    runtime=DemoRuntime(pack(sector),tmp_path)
    validated(runtime)
    runtime.workspace.review(review_request(runtime))
    publish(runtime)
    return runtime


def question(runtime, **updates):
    release=runtime.workspace.release('v1')
    metric=release['definition']['metrics'][0]
    return Question(**(binding(runtime)|dict(version='v1',context_sha256=release['context_sha256'],
        question=metric['description'],metric=metric['name'])|updates))


def run(runtime, plan):
    return runtime.playground.execute(RunPlan(**binding(runtime),plan_id=plan['plan_id']))


@pytest.mark.parametrize('sector',['finance','manufacturing','pharma','power'])
def test_saved_metric_runs_published_release_without_activation(tmp_path,sector):
    r=released(tmp_path,sector)
    try:
        before=r.workspace.view()
        q=question(r)
        plan=r.playground.interpret(q)
        assert plan['status']=='ready',plan
        assert plan['manifest']['publication']['status']=='published'
        result=run(r,plan)
        assert result['rows']==r.workspace.release('v1')['validation']['metrics'][0]['result']['rows']
        assert result['context_sha256']==q.context_sha256
        assert result['context_version']=='v1'
        assert r.workspace.view()==before
        assert r.workspace.active() is None
        assert r.playground.interpret(q)['retrieval']['cache_hit']
        assert plan['graph']['context_sha256']==q.context_sha256
    finally:r.close()


def test_draft_changes_do_not_change_pinned_query(tmp_path):
    r=released(tmp_path)
    try:
        plan=r.playground.interpret(question(r))
        first=run(r,plan)
        draft=r.workspace.view()['draft']
        changed=copy.deepcopy(draft['definition']);changed['metrics'][0]['expression']='MAX(work_orders.downtime_minutes)'
        r.workspace.save(draft['revision'],ContextDefinition.model_validate(changed))
        assert run(r,plan)==first
    finally:r.close()


def test_unpublished_stale_cross_source_expired_and_tampered_queries_rejected(tmp_path):
    r=released(tmp_path)
    other=released(tmp_path/'other')
    try:
        for changes in [{'context_sha256':'0'*64},{'session_id':'wrong'},{'pack_id':'power'},{'snapshot_sha256':'0'*64},{'version':'missing'}]:
            with pytest.raises((DemoError,RetrievalError)):
                r.playground.interpret(question(r,**changes))
        plan=r.playground.interpret(question(r))
        with pytest.raises(DemoError):run(other,plan)
        r.playground.plans[plan['plan_id']]['expires']=time.monotonic()-1
        with pytest.raises(DemoError):run(r,plan)
        with pytest.raises(ValidationError):
            RunPlan(**binding(r),plan_id=plan['plan_id'],sql='SELECT * FROM work_orders')
        validated(r);r.workspace.review(review_request(r,version='unpublished'))
        release=r.workspace.release('unpublished')
        with pytest.raises(RetrievalError):
            r.playground.interpret(question(r,version='unpublished',context_sha256=release['context_sha256']))
    finally:r.close();other.close()


def test_llm_request_compiles_only_within_retrieved_bundle(tmp_path):
    r=released(tmp_path)
    try:
        fake=FakeLLM({'status':'ready','message':'Total downtime. No planned-only filter exists.',
          'request':{'metrics':['planned_downtime_minutes'],'dimensions':[],'filters':[],'limit':100}})
        plan=r.playground.interpret(question(r,metric=None,question='What is total downtime?'),fake)
        assert plan['provenance']['method']=='llm_typed_request'
        assert run(r,plan)['rows']==[['312.00000000']]
        assert 'reference_sql' not in fake.calls[0][1]
        assert 'documents' not in json.loads(fake.calls[0][1])
        fake.response['request']['dimensions']=['customers.customer_id']
        assert r.playground.interpret(question(r,metric=None),fake)['status']=='needs_clarification'
        fake.response['request']={'metrics':['invented_metric']}
        assert r.playground.interpret(question(r,metric=None),fake)['status']=='needs_clarification'
        fake.response={'status':'ready','message':'bad','sql':'DROP TABLE work_orders'}
        assert r.playground.interpret(question(r,metric=None),fake)['status']=='needs_clarification'
    finally:r.close()


def test_clarification_and_grouped_execution(tmp_path):
    r=released(tmp_path)
    try:
        assert r.playground.interpret(question(r,metric=None))['status']=='needs_clarification'
        unknown=FakeLLM({'status':'needs_clarification','message':'Which time period?', 'request':None})
        assert r.playground.interpret(question(r,metric=None),unknown)['message']=='Which time period?'
        fake=FakeLLM({'status':'ready','message':'Downtime by asset.','request':{
            'metrics':['planned_downtime_minutes'],'dimensions':['work_orders.asset_id'],'filters':[],'limit':1}})
        plan=r.playground.interpret(question(r,metric=None,question='downtime by work_orders.asset_id'),fake)
        result=run(r,plan)
        assert len(result['rows'])==1 and result['truncated']
        assert len(result['columns'])==2
    finally:r.close()


def test_api_contract_is_source_scoped_and_publication_bound(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.helios.console import demo
    monkeypatch.setenv('HELIOS_DEMO_DATASET','manufacturing')
    monkeypatch.setenv('HELIOS_DEMO_STATE',str(tmp_path))
    monkeypatch.setattr(demo,'llm_from_env',lambda:None)
    r=released(tmp_path);r.close()
    app=FastAPI();app.include_router(demo.demo_router);demo.configure_demo(app)
    with TestClient(app) as client:
        runtime=app.state.demo_hub.runtime('manufacturing')
        before=runtime.workspace.view()
        assert client.get('/demo/api/playground?source=manufacturing').json()['versions'][0]['version']=='v1'
        plan=client.post('/demo/api/playground/interpret?source=manufacturing',json=question(runtime).model_dump())
        assert plan.status_code==200,plan.text
        payload=binding(runtime)|{'plan_id':plan.json()['plan_id']}
        result=client.post('/demo/api/playground/run?source=manufacturing',json=payload)
        assert result.status_code==200,result.text
        assert result.json()['context_version']=='v1'
        assert client.post('/demo/api/playground/run?source=power',json=payload).status_code==409
        assert client.post('/demo/api/playground/run?source=manufacturing',json=payload|{'sql':'SELECT 1'}).status_code==422
        assert runtime.workspace.view()==before


def test_json_fence_is_accepted_without_relaxing_typed_schema(tmp_path):
    r=released(tmp_path)
    try:
        class Fenced(FakeLLM):
            def complete(self, system, prompt):
                return "```json\n" + json.dumps(self.response) + "\n```"
        fake=Fenced({'status':'ready','message':'Saved downtime metric.',
                    'request':{'metrics':['planned_downtime_minutes'],'limit':100}})
        plan=r.playground.interpret(question(r,metric=None),fake)
        assert plan['status']=='ready'
        fake.response['request']['sql']='SELECT * FROM work_orders'
        assert r.playground.interpret(question(r,metric=None),fake)['status']=='needs_clarification'
    finally:r.close()


def test_finance_plans_before_resolving_join_dependencies(tmp_path):
    r=released(tmp_path, 'finance')
    try:
        fake=FakeLLM({'status':'ready','message':'Settled sender outflow by sender jurisdiction.',
          'request':{'metrics':['total_amount_sgd'],'dimensions':['payments.jurisdiction'],'filters':[], 'limit':100}})
        plan=r.playground.interpret(question(r,metric=None,question='Show settled payment amount by sender jurisdiction.'),fake)
        assert plan['status']=='ready'
        result=run(r,plan)
        assert sorted(result['rows'])==[['GB','44454.90000000'],['HK','350641.68000000'],['SG','291476.38000000']]
        assert 'JOIN' not in plan['sql']
        evidence=json.loads(fake.calls[0][1])
        assert evidence['semantic_bundle']['observed_date_ranges']['payments.booking_date']==['2026-09-01','2026-09-30']
        assert 'reference_sql' not in fake.calls[0][1]
        # Choosing an actual ambiguous relationship still fails closed.
        fake.response['request']['dimensions']=['accounts.account_id']
        blocked=r.playground.interpret(question(r,metric=None,question='Break down by account.'),fake)
        assert blocked['status']=='needs_clarification' and 'plan_id' not in blocked
    finally:r.close()


def test_clarification_never_creates_an_executable_plan(tmp_path):
    r=released(tmp_path,'power')
    try:
        fake=FakeLLM({'status':'needs_clarification','message':'No tariff metric is published.','request':None})
        before=len(r.playground.plans)
        response=r.playground.interpret(question(r,metric=None,question='What is my electricity bill?'),fake)
        assert response['status']=='needs_clarification'
        assert 'plan_id' not in response and len(r.playground.plans)==before
    finally:r.close()


@pytest.mark.parametrize('sector,metric,field,date_value',[
    ('finance','total_amount_sgd','payments.booking_date','2026-09-04'),
    ('power','measured_import_kwh','meter_readings.reading_date','2026-09-24')])
def test_compiler_date_filters_execute_without_widening_local_sql(tmp_path,sector,metric,field,date_value):
    r=released(tmp_path,sector)
    try:
        fake=FakeLLM({'status':'ready','message':'Exact source date.', 'request':{
            'metrics':[metric],'filters':[{'field':field,'op':'=','value':date_value}]}})
        plan=r.playground.interpret(question(r,metric=None,question='Use the selected source date.'),fake)
        assert plan['status']=='ready'
        result=run(r,plan)
        assert result['rows'] and result['rows'][0][0] is not None
        table=field.split('.')[0]
        for sql in [f"SELECT CAST('1' AS INTEGER) FROM {table}", f"SELECT CAST('invalid' AS DATE) FROM {table}"]:
            with pytest.raises(DemoError):r.query_local(sql)
    finally:r.close()
