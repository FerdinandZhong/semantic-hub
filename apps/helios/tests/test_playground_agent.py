"""Scope enforcement is independent of AI intent, prose, and chosen period filters."""
import json
from pathlib import Path
import pytest

from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.agent.scope import requirements, check_scope
from helios_core.demo.agent.tools import SemanticTools
from helios_core.demo.registry import DemoError
from apps.helios.tests.test_demo_context import validated, review_request, publish
from apps.helios.tests.test_demo_playground import FakeLLM, question, run
from apps.helios.tests.test_pharma_intelligence import registry, FIXTURES


@pytest.fixture(scope='module')
def pharma(tmp_path_factory):
    r=DemoRuntime(registry().load('pharma_intelligence'),tmp_path_factory.mktemp('agent-pharma'))
    value=r.workspace.seed()
    refs={item['metric']:item['reference_sql'] for item in json.loads((FIXTURES/'pharma_intelligence/evaluation/references.json').read_text())}
    for metric in value['metrics']:metric['reference_sql']=refs[metric['name']]
    validated(r,value);r.workspace.review(review_request(r));publish(r)
    yield r
    r.close()


def planner():
    return FakeLLM({'status':'ready','message':'Wrongly ignores the requested time!', 'request':{
        'metrics':['us_new_medicine_sales_share_percent'],'dimensions':[],
        'filters':[{'field':'industry_observations.period_start','op':'=','value':2020}], 'limit':100}})


@pytest.mark.parametrize('text',[
 'What is the US share of sales for new medicines launched from 1999 to 2020?',
 'What is the US new medicine sales share between 1999 and 2020?',
 '美国1999年至2020年上市新药的销售占比是多少？',
 'US new medicine share in 2000–2024',
 'US new medicine share in 2020–2025',
])
def test_original_period_cannot_be_dropped_or_partially_matched(pharma,text):
    result=pharma.playground.interpret(question(pharma,metric=None,question=text),planner())
    assert result['status']=='no_data',result
    assert 'plan_id' not in result and '74.1' not in result['message']
    assert result['scope_check']['coverage'][0]['periods']==[[2020,2024]]


def test_valid_cohort_gets_server_filters_and_executes(pharma):
    result=pharma.playground.interpret(question(pharma,metric=None,question='US share of new medicines launched during 2020–2024'),planner())
    assert result['status']=='ready',result
    assert result['request']['filters']==[
        {'field':'industry_observations.period_start','op':'=','value':2020},
        {'field':'industry_observations.period_end','op':'=','value':2024}]
    assert float(run(pharma,result)['rows'][0][0])==74.1


def test_report_year_requires_scope_clarification(pharma):
    result=pharma.playground.interpret(question(pharma,metric=None,question='US new medicine share in 2025'),planner())
    assert result['status']=='needs_clarification'
    assert 'sales year' in result['message']


def test_date_year_guard_adds_filters_and_rejects_absent_year(pharma):
    metric=next(m for m in pharma.workspace.seed()['metrics'] if m['name']=='novel_approval_count')
    assert check_scope(pharma,metric,'How many approvals in 1999?',[])['status']=='no_data'
    check=check_scope(pharma,metric,'How many FDA approvals in 2025?',[])
    assert check['status']=='supported' and len(check['filters'])==2


def test_tools_require_inspection_and_are_read_only(pharma):
    tools=SemanticTools(pharma.playground,question(pharma,metric=None,question='US share from 1999 to 2020'),planner())
    with pytest.raises(DemoError):tools.call('prepare_query',{'metric':'us_new_medicine_sales_share_percent'})
    tools.call('inspect_model',{})
    checked=tools.call('inspect_coverage',{'metric':'us_new_medicine_sales_share_percent'})
    assert checked['status']=='no_data'
    receipt=tools.call('prepare_query',{'metric':'us_new_medicine_sales_share_percent'})
    assert tools.receipts[receipt['receipt_id']]['status']=='no_data'
    with pytest.raises(DemoError):tools.call('execute_sql',{'sql':'DROP TABLE drugs'})


def test_tools_budget_and_no_cross_release_memory(pharma,tmp_path):
    from helios_core.demo.agent.memory import Memory
    tools=SemanticTools(pharma.playground,question(pharma,metric=None),planner())
    for _ in range(12):tools.call('inspect_model',{})
    with pytest.raises(DemoError):tools.call('inspect_model',{})
    a,b=Memory(tmp_path/'release-a'),Memory(tmp_path/'release-b')
    a.record('turn-a','release-a','snapshot-a','question',{'status':'no_data'},[])
    import sqlite3
    with sqlite3.connect(b.path) as db:assert db.execute('SELECT COUNT(*) FROM turns').fetchone()[0]==0


def test_relative_dates_cannot_silently_run_all_rows(pharma):
    metric=next(m for m in pharma.workspace.seed()['metrics'] if m['name']=='novel_approval_count')
    for q in ['How many approvals last month?', 'How many approvals yesterday?', '昨天批准了多少新药？']:
        assert check_scope(pharma,metric,q,[])['status']=='needs_clarification'


def test_schemas_bind_metric_names_and_qualified_fields(pharma):
    tools=SemanticTools(pharma.playground,question(pharma,metric=None),planner())
    prepare=next(s for s in tools.schemas if s['name']=='prepare_query')['parameters']['properties']
    assert 'us_new_medicine_sales_share_percent' in prepare['metric']['enum']
    assert 'industry_observations.geography' in prepare['filters']['items']['properties']['field']['enum']
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):tools.call('inspect_coverage',{'metric':'metric-id-is-not-a-name'})


def test_split_scope_cannot_erase_a_clause(pharma):
    q=question(pharma,metric=None,mode='auto',question='US new medicine share from 1999 to 2020 and source notes')
    tools=SemanticTools(pharma.playground,q,planner())
    with pytest.raises(DemoError):tools.metric_question({'metric_question':'US new medicine share','document_question':'source notes'})


def test_paraphrase_without_document_clause_cannot_replace_original(pharma):
    q=question(pharma,metric=None,question='US share of new medicines from 1999 to 2020')
    tools=SemanticTools(pharma.playground,q,planner())
    assert tools.metric_question({'metric_question':'US share from 2020 to 2024'}) == q.question


def test_independent_review_rejects_wrong_market_and_discards_plan(pharma,monkeypatch):
    from helios_core.llm.client import LLMClient
    llm=LLMClient('openai','test',None)
    monkeypatch.setattr(llm,'complete',lambda system,prompt: json.dumps({
        'supported':False,'reason':'Entire market is not new-medicine sales.'}))
    q=question(pharma,metric=None,question='North America entire market share from 2020 to 2024')
    tools=SemanticTools(pharma.playground,q,llm)
    tools.call('inspect_model',{})
    tools.call('inspect_coverage',{'metric':'us_new_medicine_sales_share_percent'})
    before=set(pharma.playground.plans)
    with pytest.raises(DemoError,match='scope review rejected'):
        tools.call('prepare_query',{'metric':'us_new_medicine_sales_share_percent'})
    assert set(pharma.playground.plans)==before
    assert not tools.receipts


def test_independent_review_accepts_boolean_without_optional_reason(pharma,monkeypatch):
    from helios_core.llm.client import LLMClient
    llm=LLMClient('openai','test',None)
    monkeypatch.setattr(llm,'complete',lambda system,prompt: '{"supported":true}')
    q=question(pharma,metric=None,question='US new-medicine sales share from 2020 to 2024')
    tools=SemanticTools(pharma.playground,q,llm)
    tools.call('inspect_model',{})
    tools.call('inspect_coverage',{'metric':'us_new_medicine_sales_share_percent'})
    assert tools.call('prepare_query',{'metric':'us_new_medicine_sales_share_percent'})['status']=='ready'


def test_conflicting_country_is_rejected_before_execution(pharma):
    fake=FakeLLM({'status':'ready','message':'Legacy interpretation', 'request':{
        'metrics':['us_new_medicine_sales_share_percent'],'dimensions':[],
        'filters':[{'field':'industry_observations.geography','op':'=','value':'Korea'}],'limit':10}})
    plan=pharma.playground.interpret(question(pharma,metric=None,question='Korea share from 2020 to 2024'),fake)
    assert plan['status']=='unsupported_scope'
    assert 'plan_id' not in plan
    assert 'Korea' in plan['message'] and 'USA' in plan['message']
    assert plan['scope_check']['reason_dimensions']==['geography']
    assert plan['scope_check']['checks'][0]['status']=='supported'


def test_diagnostics_do_not_confuse_missing_country_and_missing_period(pharma):
    from helios_core.demo.agent.scope import check_query_scope
    metric=next(m for m in pharma.workspace.seed()['metrics'] if m['name']=='us_new_medicine_sales_share_percent')
    filters=[{'field':'industry_observations.geography','op':'=','value':'Korea'}]
    check=check_query_scope(pharma,metric,'Korea new-medicine share during 2020–2024',filters)
    assert check['reason_dimensions']==['geography']
    assert check['checks'][0]['status']=='supported'
    both=check_query_scope(pharma,metric,'Korea new-medicine share during 1999–2020',filters)
    assert both['reason_dimensions']==['period','geography']
    usa=check_query_scope(pharma,metric,'USA new-medicine share during 1999–2020',[
        {'field':'industry_observations.geography','op':'=','value':'USA'}])
    assert usa['reason_dimensions']==['period']
    assert usa['status']=='no_data'


def test_country_clarification_uses_checked_reason_instead_of_model_prose(pharma):
    tools=SemanticTools(pharma.playground,question(pharma,metric=None,question='Korea new-medicine share during 2020–2024'),planner())
    receipt=tools.call('request_clarification',{'metric':'us_new_medicine_sales_share_percent',
        'filters':[{'field':'industry_observations.geography','op':'=','value':'Korea'}],
        'message':'The years are incorrect.'})
    checked=tools.receipts[receipt['receipt_id']]
    assert checked['status']=='unsupported_scope'
    assert 'years are incorrect' not in checked['message']
    assert checked['scope_check']['reason_dimensions']==['geography']


def test_document_fallback_cannot_claim_model_time_gap(pharma,monkeypatch):
    tools=SemanticTools(pharma.playground,question(pharma,metric=None,mode='auto',question='Korea share during 2020–2024'),planner())
    tools.inspected=True;tools.read_documents=True
    monkeypatch.setattr(pharma.playground,'_interpret',lambda *args,**kwargs:{'status':'needs_clarification','message':'Document dates do not match.'})
    with pytest.raises(DemoError,match='do not establish missing model data'):
        tools.call('prepare_document',{})
    assert not tools.receipts


def test_auto_scope_failure_checks_documents_before_final_refusal(pharma,monkeypatch):
    import helios_core.demo.agent.tools as module
    tools=SemanticTools(pharma.playground,question(pharma,metric=None,mode='auto',question='Korea share during 2020–2024'),planner())
    monkeypatch.setattr(module,'passages',lambda release:[{'text':'Other published evidence'}])
    args={'metric':'us_new_medicine_sales_share_percent','filters':[{'field':'industry_observations.geography','op':'=','value':'Korea'}]}
    result=tools.call('inspect_coverage',args)
    assert result['status']=='inspect_alternative_evidence'
    assert result['metric_status']=='unsupported_scope'
    assert 'receipt_id' not in result
    with pytest.raises(DemoError,match='Inspect the published document evidence'):
        tools.call('request_clarification',args|{'message':'No matching geography'})
    tools.read_documents=True
    result=tools.call('request_clarification',args|{'message':'No matching geography'})
    assert tools.receipts[result['receipt_id']]['scope_check']['reason_dimensions']==['geography']
