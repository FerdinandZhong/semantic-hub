"""LLM profiles affect only their purpose and cannot bypass reviewed sample execution."""
import json
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.helios.console import demo
from helios_core.demo.runtime import review_pack
from helios_core.demo.query_explanation import ExplainExample, explain_example


class FakeLLM:
    provider = 'test'
    model = 'fake-model'
    base_url = 'https://llm.example.test/v1'
    def __init__(self):
        self.calls = []
        self.fail = False
    def complete(self, system, user):
        self.calls.append((system, user))
        if self.fail:
            raise RuntimeError('Secret provider error TOKEN-DO-NOT-RETURN')
        return 'The reviewed sample reports the supplied amount. This is synthetic data.'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('HELIOS_DEMO_DATASET', 'power')
    monkeypatch.setenv('HELIOS_DEMO_STATE', str(tmp_path))
    llm = FakeLLM()
    monkeypatch.setattr(demo, 'llm_from_env', lambda: llm)
    app = FastAPI()
    app.include_router(demo.demo_router)
    demo.configure_demo(app)
    with TestClient(app) as client:
        yield client, app.state.demo_runtime, llm


def sample_payload(client):
    config = client.get('/demo/api/config').json()
    return {k: config[k] for k in ('pack_id', 'session_id', 'snapshot_sha256', 'context_sha256')} | {'example_id': config['examples'][0]['id']}


def test_profiles_are_independent_and_settings_test_uses_saved_profile(client):
    client, runtime, llm = client
    assert client.get('/demo/llm').status_code == 200
    profiles = client.get('/demo/api/llm').json()['profiles']
    assert profiles['draft']['ready'] and profiles['query']['model'] == 'fake-model'
    response = client.post('/demo/api/llm', json={'purpose': 'draft', 'mode': 'disabled', 'revision': 0})
    assert response.status_code == 200
    assert not response.json()['profiles']['draft']['ready']
    assert response.json()['profiles']['query']['ready']
    assert client.get('/demo/api/context/proposals').json()['llm_available'] is False
    assert client.post('/demo/api/llm/test', json={'purpose': 'draft'}).status_code == 409
    assert not llm.calls
    assert client.post('/demo/api/llm/test', json={'purpose': 'query'}).status_code == 200
    assert len(llm.calls) == 1
    assert client.post('/demo/api/llm', json={'purpose': 'draft', 'mode': 'inherited', 'revision': 0}).status_code == 409
    assert client.post('/demo/api/llm', json={'purpose': 'query', 'mode': 'openai-compatible', 'revision': 0, 'base_url': 'https://user:secret@host/v1'}).status_code == 422


def test_explanation_rejects_unreviewed_stale_and_cross_source_before_model_call(client):
    client, runtime, llm = client
    payload = sample_payload(client) | {'result_sha256': '0' * 64}
    assert client.post('/demo/api/example/explain', json=payload).status_code == 409
    assert not llm.calls
    review_pack(runtime.pack, runtime.state_root, 'automated-test-only')
    assert client.post('/demo/api/example/explain', json=payload).status_code == 409
    result = client.post('/demo/api/example', json=sample_payload(client)).json()
    payload['result_sha256'] = result['result_sha256']
    for changes in ({'session_id': 'stale'}, {'context_sha256': '0'*64}, {'pack_id': 'finance'}):
        assert client.post('/demo/api/example/explain', json=payload | changes).status_code == 409
    assert client.post('/demo/api/example/explain?source=finance', json=payload).status_code == 409
    assert not llm.calls
    response = client.post('/demo/api/example/explain', json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['result_sha256'] == result['result_sha256']
    evidence = json.loads(llm.calls[-1][1])
    assert evidence['rows'] == [[str(result['rows'][0][0])]]
    assert len(llm.calls[-1][1]) <= 12000
    assert 'sql' not in evidence
    assert runtime.workspace.view()['draft']['revision'] == 0
    assert client.post('/demo/api/llm', json={'purpose':'query', 'mode':'disabled', 'revision':0}).status_code == 200
    assert client.post('/demo/api/example/explain', json=payload).status_code == 409
    assert len(llm.calls) == 1


def test_provider_errors_do_not_echo_provider_credentials(client):
    client, runtime, llm = client
    llm.fail = True
    response = client.post('/demo/api/llm/test', json={'purpose': 'query'})
    assert response.status_code == 502
    assert 'TOKEN-DO-NOT-RETURN' not in response.text


def test_direct_key_save_and_validation_never_echo_secret(client,monkeypatch):
    client,runtime,llm=client
    secret='private-test-api-key-not-for-output'
    body={'purpose':'query','revision':0,'mode':'openai-compatible','credential_mode':'api_key','api_key':secret}
    response=client.post('/demo/api/llm',json=body)
    assert response.status_code==200
    assert secret not in response.text
    assert response.json()['profiles']['query']['has_saved_api_key']
    assert secret not in client.get('/demo/api/llm').text
    from helios_core.llm import LLMClient
    seen=[]
    def complete(self,*args):
        seen.append(self.api_key)
        return 'OK'
    monkeypatch.setattr(LLMClient,'complete',complete)
    assert client.post('/demo/api/llm/test',json={'purpose':'query'}).status_code==200
    assert seen==[secret]
    for changes in ({'api_key':secret+' invalid'}, {'base_url':'bad-url'}, {'purpose':'invalid'}):
        error=client.post('/demo/api/llm',json=body|changes)
        assert error.status_code==422
        assert secret not in error.text


def test_connection_error_reports_safe_parameter_without_provider_body(client,monkeypatch):
    import httpx
    from helios_core.llm.client import LLMError
    client,runtime,llm=client
    def fail(*args):
        response=httpx.Response(400,request=httpx.Request('POST','https://example.test/v1/chat/completions'),
                               json={'error':{'param':'max_tokens','message':'SECRET-PROVIDER-BODY'}})
        try:response.raise_for_status()
        except httpx.HTTPStatusError as cause:raise LLMError('SECRET-PROVIDER-BODY') from cause
    monkeypatch.setattr(llm,'complete',fail)
    response=client.post('/demo/api/llm/test',json={'purpose':'query'})
    assert response.status_code==502
    assert 'max_tokens' in response.text
    assert 'SECRET-PROVIDER-BODY' not in response.text


def test_explanation_evidence_is_bounded():
    class Runtime:
        pack=SimpleNamespace(synthetic=True,generation_mode='synthetic')
        def execute(self, request):
            return {'result_sha256':'a'*64,'context_sha256':'','snapshot_sha256':'b'*64,'context_version':None,
                    'question':'Sample','unit':'count','columns':[f'c{i}' for i in range(30)],
                    'rows':[['x'*2000 for _ in range(30)] for _ in range(200)]}
        def summary(self):
            return {'context_sha256':''}
    llm = FakeLLM()
    request = ExplainExample(pack_id='power', session_id='test', snapshot_sha256='b'*64, context_sha256='', example_id='aggregate', result_sha256='a'*64)
    result = explain_example(Runtime(), request, llm)
    assert len(llm.calls[0][1]) <= 12000
    assert result['shown_rows'] < 20
    assert result['total_rows'] == 200
