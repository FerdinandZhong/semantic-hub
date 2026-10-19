"""Model-family request compatibility, covering both text and tool requests."""
import httpx
import pytest
from helios_core.llm.client import LLMClient


@pytest.mark.parametrize('model',['gpt-5.4','gpt-5.4-2026-03-05','gpt-4o','custom-model'])
def test_text_and_tool_requests_use_supported_generation_parameters(monkeypatch,model):
    requests=[]
    def post(url,**kwargs):
        requests.append(kwargs['json'])
        return httpx.Response(200,request=httpx.Request('POST',url),json={
            'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}],'usage':{}})
    monkeypatch.setattr(httpx,'post',post)
    client=LLMClient('openai',model,'test-only-key','https://api.openai.com/v1',max_tokens=32)
    assert client.complete('Reply OK','Check')=='OK'
    client.tool_turn('Reply OK',[{'role':'user','content':'Check'}],[])
    assert len(requests)==2
    for body in requests:
        if model.startswith('gpt-5.4'):
            assert body['max_completion_tokens']==32
            assert body['reasoning_effort']=='none'
            assert 'max_tokens' not in body and 'temperature' not in body
        else:
            assert body['max_tokens']==32 and body['temperature']==0
            assert 'max_completion_tokens' not in body


@pytest.mark.parametrize('model', ['gpt-6.1-sol', 'gpt-6.1-sol-2026-09-29', 'gpt-6-sol', 'gpt-6-luna', 'gpt-6-astra'])
def test_new_models_route_text_and_tools_to_responses(monkeypatch, model):
    seen = []
    def post(url, **kwargs):
        seen.append((url, kwargs['json']))
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': 'OK'}]}],
            'usage': {'input_tokens': 7, 'output_tokens': 3}})
    monkeypatch.setattr(httpx, 'post', post)
    client = LLMClient('openai', model, 'test-key', 'https://api.openai.com/v1', max_tokens=32)
    assert client.complete_with_usage('Reply OK', 'Check') == ('OK', 7, 3)
    assert client.tool_turn('Reply OK', [{'role': 'user', 'content': 'Check'}], []).text == 'OK'
    for url, body in seen:
        assert url.endswith('/responses')
        assert body['reasoning'] == {'effort': 'low'}
        assert body['max_output_tokens'] >= 1024
        assert body['store'] is False
        assert not {'max_tokens', 'max_completion_tokens', 'temperature'} & body.keys()


def test_responses_tool_continuation_keeps_reasoning_and_call_ids(monkeypatch):
    seen = []
    output = [{'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'test-encrypted'},
              {'type': 'function_call', 'id': 'fc_1', 'call_id': 'call_1', 'name': 'inspect_model', 'arguments': '{}'}]
    def post(url, **kwargs):
        seen.append(kwargs['json'])
        body = {'status': 'completed', 'output': output if len(seen) == 1 else [
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Checked'}]}]}
        return httpx.Response(200, request=httpx.Request('POST', url), json=body)
    monkeypatch.setattr(httpx, 'post', post)
    client = LLMClient('openai', 'gpt-6.1-sol', 'key', 'https://api.openai.com/v1')
    tools = [{'name': 'inspect_model', 'inputSchema': {'type': 'object', 'properties': {}}}]
    messages = [{'role': 'user', 'content': 'Inspect model'}]
    first = client.tool_turn('Inspect scope', messages, tools)
    assert first.tool_calls[0].id == 'call_1'
    messages += [{'role': 'assistant', 'response_items': first.response_items},
                 {'role': 'tool', 'tool_call_id': 'call_1', 'content': '{"model":"finance"}'}]
    assert client.tool_turn('Inspect scope', messages, tools).text == 'Checked'
    assert seen[0]['tools'][0]['name'] == 'inspect_model'
    assert seen[0]['include'] == ['reasoning.encrypted_content']
    assert seen[1]['input'][1:3] == output
    assert seen[1]['input'][3] == {'type': 'function_call_output', 'call_id': 'call_1', 'output': '{"model":"finance"}'}


@pytest.mark.parametrize('arguments', ['[]', '{invalid'])
def test_responses_invalid_tool_arguments_are_recoverable(monkeypatch, arguments):
    def post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={'output': [
            {'type': 'function_call', 'call_id': 'call_1', 'name': 'inspect', 'arguments': arguments}]})
    monkeypatch.setattr(httpx, 'post', post)
    turn = LLMClient('openai', 'gpt-6.1-sol', 'key', 'https://api.openai.com/v1').tool_turn('', [], [])
    assert turn.tool_calls[0].parse_error
    assert turn.tool_calls[0].raw_arguments == arguments


def test_incomplete_response_never_becomes_a_partial_answer(monkeypatch):
    from helios_core.llm import LLMError
    def post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'status': 'incomplete', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Partial'}]}]})
    monkeypatch.setattr(httpx, 'post', post)
    with pytest.raises(LLMError, match='output budget'):
        LLMClient('openai', 'gpt-6.1-sol', 'key', 'https://api.openai.com/v1').complete('', '')


@pytest.mark.parametrize('model,api', [('gpt-4o','openai-completions'), ('gpt-5.4','openai-completions'),
                                     ('custom-model','openai-completions'), ('gpt-6.1-sol','openai-responses')])
def test_agent_adapter_uses_model_compatible_protocol(model, api):
    from helios_core.demo.agent.harness import profile
    _, adapter = profile(LLMClient('openai', model, 'key', 'https://api.openai.com/v1'))
    assert adapter['api'] == api
    assert bool(adapter['models'][0].get('reasoningEfforts')) == (api == 'openai-responses')


def test_default_budget_is_capped_per_model_family():
    from helios_core.llm.client import LLMClient
    from helios_core.llm.openai_compat import openai_compatibility
    assert LLMClient('openai', 'gpt-4o', 'k').max_tokens == 128000
    assert openai_compatibility('gpt-4o').chat_options(128000, 0)['max_tokens'] == 16384
    assert openai_compatibility('gpt-4.1-mini').chat_options(128000, 0)['max_tokens'] == 32768
    assert openai_compatibility('gpt-5.4').chat_options(128000, 0)['max_completion_tokens'] == 128000
    assert openai_compatibility('gpt-6.1-sol').response_options(128000)['max_output_tokens'] == 128000
    assert openai_compatibility('local-llama').chat_options(128000, 0)['max_tokens'] == 4000
    # Explicit smaller budgets (Playground, connection test) are unchanged.
    assert openai_compatibility('gpt-4o').chat_options(600, 0)['max_tokens'] == 600


def test_default_timeout_is_120_seconds(monkeypatch):
    from helios_core.llm.client import LLMClient
    monkeypatch.delenv('HELIOS_LLM_TIMEOUT_SECONDS', raising=False)
    assert LLMClient('openai', 'gpt-4o', 'k').timeout == 120
