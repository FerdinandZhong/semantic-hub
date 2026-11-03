"""Chat must return executed data, truthful retrieval scores, and terminal states."""
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.tests.test_demo_playground import released, question, FakeLLM
from apps.helios.tests.test_document_answers import document_runtime, doc_question, DocumentLLM
from helios_core.demo.chat import answer
from helios_core.demo.registry import DemoError


@pytest.fixture(scope='module')
def finance(tmp_path_factory):
    runtime = released(tmp_path_factory.mktemp('chat-finance'), 'finance')
    yield runtime
    runtime.close()


def test_saved_metric_executes_data_and_does_not_invent_confidence(finance):
    events = []
    factory = Mock(side_effect=AssertionError('Saved metrics need no LLM'))
    result = answer(finance.playground, question(finance), factory, lambda *event: events.append(event))
    assert Decimal(str(result['rows'][0][0])) == Decimal('686572.96')
    assert result['sql'] and result['result_sha256']
    assert [event[0] for event in events] == ['retrieve', 'check', 'retrieval', 'execute', 'execute', 'answer']
    assert result['retrieval_details']['confidence'] is None
    assert result['retrieval_details']['matches'] == []
    assert result['retrieval_details']['method'] == 'Saved metric selection'
    canvas = result['semantic_canvas']
    tables = {t.name for t in __import__('sqlglot').parse_one(result['sql'], read='duckdb').find_all(__import__('sqlglot').exp.Table)}
    assert {n['id'] for n in canvas['graph']['nodes']} == tables
    assert canvas['focus'] and canvas['focus'] in canvas['graph']['metric_dependencies']
    factory.assert_not_called()


def test_natural_question_runs_grouped_query_and_reports_actual_ranking(finance):
    llm = FakeLLM({'status':'ready', 'message':'Group settled outflow by sender jurisdiction.',
        'request':{'metrics':['total_amount_sgd'], 'dimensions':['payments.jurisdiction'], 'filters':[], 'limit':100}})
    payload = question(finance, metric=None, mode='auto',
        question='Show total settled sender outflow in SGD by sender jurisdiction.')
    result = answer(finance.playground, payload, lambda: llm, lambda *args: None)
    assert len(result['rows']) == 3
    assert sum(Decimal(str(row[-1])) for row in result['rows']) == Decimal('686572.96')
    details = result['retrieval_details']
    assert details['method'] == 'SQLite FTS5 lexical relevance'
    assert details['confidence'] is None
    _, scope, _ = finance.playground.adopted(payload.version, payload.context_sha256)
    assert details['matches'] == finance.playground.retrieval.discover(payload.question, scope)[0]['matches']


def test_clarification_does_not_execute(finance, monkeypatch):
    llm = FakeLLM({'status':'needs_clarification', 'message':'Specify an available period.', 'request':None})
    execute = Mock(side_effect=AssertionError('No checked plan'))
    monkeypatch.setattr(finance.playground, 'execute', execute)
    result = answer(finance.playground, question(finance, metric=None, question='Show 2025 revenue'), lambda:llm, lambda *args:None)
    assert result['status'] == 'needs_clarification'
    execute.assert_not_called()


def test_stopped_request_never_starts_answer_execution(finance, monkeypatch):
    execute = Mock(side_effect=AssertionError('Request stopped'))
    monkeypatch.setattr(finance.playground, 'execute', execute)
    def emit(stage, detail):
        if stage == 'execute':
            raise DemoError('Request stopped')
    with pytest.raises(DemoError, match='stopped'):
        answer(finance.playground, question(finance), lambda:None, emit)
    execute.assert_not_called()


def test_document_answer_has_citations_and_real_keyword_scores(tmp_path):
    runtime = document_runtime(tmp_path)
    try:
        events = []
        result = answer(runtime.playground, doc_question(runtime), DocumentLLM, lambda *event:events.append(event))
        assert result['kind'] == 'document' and result['claims'][0]['citations']
        assert 'sql' not in result
        nodes = result['semantic_canvas']['graph']['nodes']
        assert nodes[0]['type'] == 'document_group'
        assert {n['citation'] for n in nodes[1:]} >= {c['citation'] for c in result['claims'][0]['citations']}
        details = result['retrieval_details']
        assert details['confidence'] is None and details['method'] == 'Keyword overlap'
        assert all(0 <= m['score'] <= m['query_terms'] for m in details['matches'])
        assert any(stage == 'answer' for stage, _ in events)
    finally:
        runtime.close()


def test_stream_route_pins_binding_and_returns_terminal_result(finance):
    from apps.helios.console.demo import demo_router
    app = FastAPI()
    app.state.demo_runtime = finance
    app.include_router(demo_router)
    with TestClient(app) as client:
        payload = question(finance).model_dump()
        response = client.post('/demo/api/playground/chat', json=payload)
        assert response.status_code == 200, response.text
        assert response.headers['content-type'].startswith('application/x-ndjson')
        events = [json.loads(line) for line in response.text.splitlines()]
        assert events[0]['type'] == 'progress'
        assert events[-1]['type'] == 'result'
        assert Decimal(str(events[-1]['result']['rows'][0][0])) == Decimal('686572.96')
        assert client.post('/demo/api/playground/chat', json=payload | {'session_id':'different'}).status_code == 409
        assert client.post('/demo/api/playground/chat', json=payload | {'sql':'DELETE FROM payments'}).status_code == 422
