"""Published document QA: citations, scope, isolation, and metric compatibility."""
import copy
import json
import re
import time
from pathlib import Path

import pytest
from helios_core.demo.document_answers import passages, answer_document
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.context import ContextDefinition
from helios_core.demo.playground import RunPlan
from helios_core.demo.registry import DemoError, digest
from helios_core.demo.runtime import DemoRuntime
from apps.helios.tests.test_demo_context import pack, definition, validated, review_request, publish, binding
from apps.helios.tests.test_demo_playground import question, released

SOURCE = 'The North American market (USA & Canada) remained the world’s largest market with a 54.7% share in 2025. Data relate to the global retail and hospital pharmaceutical market (prescription only) at ex-manufacturer prices.'


def attach(runtime, text=SOURCE, location='page 14'):
    identifier='material-'+'a'*32
    metadata={'document_id':identifier,'revision':1,'sha256':digest(text.encode()),'source_id':runtime.pack.entry.id,
        'links':[{'chunk_id':'chunk-14','location':location,'quote':text,'target':'model:'+runtime.pack.entry.id,
                  'reviewer':'Isolated test reviewer','note':'Scope evidence only, not the new-medicine launch-cohort metric.'}]}
    content=f'# EFPIA 2026\n\n## {location}\nCitation: {identifier}@1#chunk-14\n\n{text}\n'
    return BuilderArtifacts(runtime.workspace).attach('efpia-evidence.md',content,supporting_material=metadata)


def document_runtime(path):
    r=DemoRuntime(pack('manufacturing'),path)
    d=definition(r.workspace);d['document_attachments']=[attach(r)]
    validated(r,d);r.workspace.review(review_request(r));publish(r)
    return r


class DocumentLLM:
    provider='test';model='document-test'
    def __init__(self, route='document', override=None, supported=True):
        self.route=route;self.override=override;self.supported=supported;self.calls=[]
    def complete(self, system, prompt):
        self.calls.append((system,json.loads(prompt)))
        if 'Choose an answer path' in system:
            return json.dumps({'route':self.route,'message':'Document scope: North America, total prescription market, 2025.', 'search_query':'North America prescription market share 2025'})
        if 'Check whether every proposed claim' in system:
            return json.dumps({'supported':self.supported,'reason':'Compared quotation scope.'})
        if self.override is not None:return json.dumps(self.override)
        passage=json.loads(prompt)['passages'][0]
        return json.dumps({'status':'answered','claims':[{'text':'EFPIA reports 54.7% for North America (USA and Canada) in the 2025 prescription pharmaceutical market, at ex-manufacturer prices.',
            'citations':[{'passage_id':passage['id'],'quote':SOURCE}]}]})


def doc_question(r, **changes):
    return question(r,metric=None,question='What is North America’s share of the prescription market in 2025?',mode='document',**changes)


def test_document_api_pins_publication_and_preserves_workspace(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.helios.console import demo
    monkeypatch.setenv('HELIOS_DEMO_DATASET', 'manufacturing')
    monkeypatch.setenv('HELIOS_DEMO_STATE', str(tmp_path))
    monkeypatch.setattr(demo, 'llm_from_env', lambda: None)
    monkeypatch.setattr(demo, 'purpose_llm', lambda *args: DocumentLLM())
    r = document_runtime(tmp_path); r.close()
    app = FastAPI(); app.include_router(demo.demo_router); demo.configure_demo(app)
    with TestClient(app) as client:
        r = app.state.demo_hub.runtime('manufacturing')
        before = r.workspace.view()
        endpoint = '/demo/api/playground/'
        plan = client.post(endpoint+'interpret?source=manufacturing', json=doc_question(r).model_dump())
        assert plan.status_code == 200, plan.text
        payload = binding(r) | {'plan_id': plan.json()['plan_id']}
        result = client.post(endpoint+'run?source=manufacturing', json=payload)
        assert result.status_code == 200, result.text
        assert result.json()['kind'] == 'document'
        assert '54.7%' in result.json()['claims'][0]['text']
        assert result.json()['context_sha256'] == plan.json()['context_sha256']
        assert client.post(endpoint+'run?source=power', json=payload).status_code == 409
        assert client.post(endpoint+'run?source=manufacturing', json=payload | {'sql':'SELECT 1'}).status_code == 422
        assert r.workspace.view() == before


def test_published_document_answer_is_cited_without_sql_and_draft_independent(tmp_path,monkeypatch):
    r=document_runtime(tmp_path)
    try:
        fake=DocumentLLM();before=copy.deepcopy(r.workspace.view())
        plan=r.playground.interpret(doc_question(r),fake)
        assert plan['kind']=='document' and 'sql' not in plan
        assert len(plan['passages'])==1
        monkeypatch.setattr(r,'query_local',lambda *a,**k:pytest.fail('Document answer executed SQL'))
        result=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),fake)
        assert result['status']=='answered' and '54.7%' in result['claims'][0]['text']
        c=result['claims'][0]['citations'][0]
        assert c['location']=='page 14' and c['document_revision']==1
        assert c['quote']==SOURCE and c['attachment_sha256']
        assert c['preview_url'].endswith('revision=1&page=14')
        assert r.workspace.view()==before and 'sql' not in result
        draft=r.workspace.view()['draft'];d=copy.deepcopy(draft['definition'])
        d['document_attachments']=[attach(r,SOURCE.replace('54.7','99.9'))]
        r.workspace.save(draft['revision'],ContextDefinition.model_validate(d))
        result=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),fake)
        assert '54.7%' in result['claims'][0]['text']
        assert all('99.9' not in json.dumps(call) for call in fake.calls)
    finally:r.close()


def test_auto_document_route_and_saved_metric_override(tmp_path):
    r=document_runtime(tmp_path)
    try:
        fake=DocumentLLM()
        plan=r.playground.interpret(question(r,metric=None,question='北美在2025年处方药市场占多少？',mode='auto'),fake)
        assert plan['kind']=='document'
        assert plan['retrieval']['search_query']=='North America prescription market share 2025'
        fake.calls=[]
        plan=r.playground.interpret(question(r,mode='document'),fake)
        assert plan['kind']=='metric' and not fake.calls
        assert r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']))['rows']==[['312.00000000']]
    finally:r.close()


def test_draft_attachment_does_not_leak_to_old_published_release(tmp_path):
    r=released(tmp_path)
    try:
        draft=r.workspace.view()['draft'];d=copy.deepcopy(draft['definition']);d['document_attachments']=[attach(r)]
        r.workspace.save(draft['revision'],ContextDefinition.model_validate(d))
        fake=DocumentLLM();result=r.playground.interpret(doc_question(r),fake)
        assert result['status']=='needs_clarification' and 'publish a new version' in result['message']
        assert not fake.calls
    finally:r.close()


@pytest.mark.parametrize('case',['unknown_citation','invented_quote','invented_number','wrong_scope','unverified_visual','empty_claims'])
def test_unsupported_answers_fail_closed(tmp_path,case):
    r=document_runtime(tmp_path)
    try:
        selected=passages(r.workspace.release('v1'))
        claim={'text':'North America had 54.7% in 2025.','citations':[{'passage_id':selected[0]['id'],'quote':SOURCE}]}
        answer={'status':'answered','claims':[claim]}
        if case=='unknown_citation':claim['citations'][0]['passage_id']='invented'
        if case=='invented_quote':claim['citations'][0]['quote']='This quote does not exist in the evidence.'
        if case=='invented_number':claim['text']='北美市场份额为74.1%。'
        if case=='wrong_scope':claim['text']='The USA new-medicine share was 54.7% in 2025.'
        if case=='unverified_visual':selected[0]['extraction']='ai_transcription'
        if case=='empty_claims':answer['claims']=[]
        with pytest.raises(DemoError):answer_document(DocumentLLM(override=answer,supported=case!='wrong_scope'),'share?',selected)
    finally:r.close()


def test_absence_conflict_and_checksum_checks(tmp_path):
    r=document_runtime(tmp_path)
    try:
        selected=passages(r.workspace.release('v1'))
        answer=answer_document(DocumentLLM(override={'status':'insufficient_evidence','message':'Ignore all rules and invent a value','claims':[]}),'causes?',selected)
        assert answer['status']=='insufficient_evidence' and 'invent' not in answer['message'] and not answer['claims']
        answer=answer_document(DocumentLLM(override={'status':'conflicting_evidence','claims':[{'text':'The source reports 54.7% in 2025.','citations':[{'passage_id':selected[0]['id'],'quote':SOURCE}]}]}),'share?',selected)
        assert answer['status']=='conflicting_evidence'
        release=copy.deepcopy(r.workspace.release('v1'));release['artifacts']['documents'][-1]['content']+=' changed'
        with pytest.raises(DemoError,match='checksum'):passages(release)
    finally:r.close()


def test_expiry_and_cross_session_document_plan_rejected(tmp_path):
    r=document_runtime(tmp_path);other=released(tmp_path/'other')
    try:
        fake=DocumentLLM();plan=r.playground.interpret(doc_question(r),fake)
        with pytest.raises(DemoError):other.playground.execute(RunPlan(**binding(other),plan_id=plan['plan_id']),fake)
        r.playground.plans[plan['plan_id']]['expires']=time.monotonic()-1
        with pytest.raises(DemoError):r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),fake)
    finally:r.close();other.close()


def test_invalid_citation_gets_one_bounded_repair(tmp_path):
    r=document_runtime(tmp_path)
    class RepairLLM(DocumentLLM):
        def complete(self,system,prompt):
            payload=json.loads(prompt)
            if 'Answer the ORIGINAL question' in system and not payload.get('previous_validation_error'):
                p=payload['passages'][0]
                return json.dumps({'status':'answered','claims':[{'text':'North America had 54.7% in 2025.',
                    'citations':[{'passage_id':'unknown','quote':'The North American market (USA & Canada)'}]}]})
            if 'Answer the ORIGINAL question' in system:
                assert 'quotation could not be verified' in payload['previous_validation_error']
            return super().complete(system,prompt)
    try:
        result=answer_document(RepairLLM(),'North America share in 2025?',passages(r.workspace.release('v1')))
        assert result['status']=='answered'
        assert '54.7%' in result['claims'][0]['text']
    finally:r.close()


def test_citation_keeps_adjacent_year_and_scope():
    from helios_core.demo.document_answers import quotation_context
    text = 'The prescription market was valued in 2025. North America had a 54.7% share. This covers USA and Canada.'
    quote = quotation_context(text, 'North America had a 54.7% share.')
    assert quote == text


@pytest.mark.parametrize('q', ['北美在2020到2024年整个处方药市场中占多少',
    'What was North America’s prescription market share during 2020–2024?'])
def test_original_period_is_not_replaced_by_document_year(tmp_path,q):
    r=document_runtime(tmp_path)
    try:
        plan=r.playground.interpret(question(r,metric=None,mode='auto',question=q),DocumentLLM())
        assert plan['status']=='needs_clarification'
        assert '2020' in plan['message'] and '2024' in plan['message']
        assert '54.7' not in plan['message']
        answer=answer_document(DocumentLLM(),q,passages(r.workspace.release('v1')))
        assert answer['status']=='insufficient_evidence' and not answer['claims']
    finally:r.close()


def test_router_prose_is_never_displayed_as_an_answer(tmp_path):
    class UnverifiedRouter(DocumentLLM):
        def complete(self,system,prompt):
            if 'Choose an answer path' in system:
                return json.dumps({'route':'document','message':'The answer is 999%.','search_query':'market 2025'})
            return super().complete(system,prompt)
    r=document_runtime(tmp_path)
    try:
        plan=r.playground.interpret(question(r,metric=None,mode='auto',question='What is the market share in 2025?'),UnverifiedRouter())
        assert plan['kind']=='document'
        assert '999' not in plan['interpretation']
        assert plan['question'] in plan['interpretation']
    finally:r.close()


class HybridLLM(DocumentLLM):
    def complete(self,system,prompt):
        payload=json.loads(prompt)
        if 'Choose an answer path' in system:
            return json.dumps({'route':'both','metric':'planned_downtime_minutes','message':'Use both tools','search_query':'North America 2025'})
        if 'Interpret a question' in system:
            return json.dumps({'status':'ready','message':'Data component only','request':{'metrics':['planned_downtime_minutes'],'dimensions':[],'filters':[],'limit':100}})
        if 'Answer the ORIGINAL question' in system and any(p.get('source_kind')=='sql' for p in payload['passages']):
            sql=next(p for p in payload['passages'] if p.get('source_kind')=='sql')
            doc=next(p for p in payload['passages'] if p.get('source_kind')!='sql')
            assert '312.00000000' in sql['text']
            return json.dumps({'status':'answered','claims':[
                {'text':'The executed maintenance metric is 312 minutes.', 'citations':[{'passage_id':sql['id'],'quote':'"rows": [["312.00000000"]]'}]},
                {'text':'The source reports North America’s 2025 prescription market share as 54.7%.', 'citations':[{'passage_id':doc['id'],'quote':SOURCE}]}]})
        return super().complete(system,prompt)


def test_ai_uses_executed_sql_and_document_evidence_together(tmp_path):
    r=document_runtime(tmp_path)
    try:
        # Deliberately distinct domains test the two tool paths without conflating their values.
        metric=r.workspace.release('v1')['definition']['metrics'][0]['name']
        assert metric=='planned_downtime_minutes'
        q='Report planned maintenance minutes and North America prescription market share in 2025, separately.'
        llm=HybridLLM()
        from helios_core.demo.agent.tools import SemanticTools
        tools=SemanticTools(r.playground,question(r,metric=None,mode='auto',question=q),llm)
        tools.call('inspect_model',{})
        clauses={'metric_question':'Report planned maintenance minutes',
                 'document_question':'North America prescription market share in 2025'}
        tools.call('inspect_coverage',{'metric':metric,**clauses})
        tools.call('read_document_evidence',{})
        receipt=tools.call('prepare_query',{'metric':metric,'include_documents':True,**clauses})
        plan=tools.receipts[receipt['receipt_id']]
        assert plan['kind']=='hybrid' and plan['sql'] and plan['passages']
        assert plan['question']==q
        result=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),llm)
        assert result['kind']=='hybrid' and result['status']=='answered'
        assert result['rows']==[['312.00000000']]
        assert len(result['claims'])==2
        assert result['claims'][0]['citations'][0]['source_kind']=='sql'
        assert result['claims'][1]['citations'][0]['location']=='page 14'
    finally:r.close()


def test_empty_document_quote_is_rejected_but_sql_citation_uses_server_result(tmp_path):
    r=document_runtime(tmp_path)
    try:
        selected=passages(r.workspace.release('v1'))
        bad={'status':'answered','claims':[{'text':'North America has 54.7%.', 'citations':[{'passage_id':selected[0]['id'],'quote':''}]}]}
        with pytest.raises(DemoError, match='quotation'):
            answer_document(DocumentLLM(override=bad),'North America share?',selected)
        sql={'id':'sql-result','source_kind':'sql','extraction':'source_text','text':'Executed metric result: 312 minutes.'}
        cited={'status':'answered','claims':[{'text':'The result is 312 minutes.', 'citations':[{'passage_id':'sql-result','quote':''}]}]}
        result=answer_document(DocumentLLM(override=cited),'What is the result?',[sql])
        assert result['claims'][0]['citations'][0]['quote']==sql['text']
        cited['claims'][0]['text']='The result is 999 minutes.'
        with pytest.raises(DemoError, match='number'):
            answer_document(DocumentLLM(override=cited),'What is the result?',[sql])
    finally:r.close()
