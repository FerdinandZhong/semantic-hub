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
