"""Drafting and query profiles persist independently without credential values."""
import pytest
from pydantic import ValidationError
from helios_core.demo.llm_settings import LLMSettings
from helios_core.demo.registry import DemoError


class FakeClient:
    provider = 'fake'
    model = 'environment-model'
    base_url = 'https://example.test/v1'
    api_key = 'NEVER_RETURN_THIS_SECRET'


def test_defaults_inherit_injected_factory_and_never_return_secret(tmp_path):
    service = LLMSettings(tmp_path)
    view = service.view(lambda: FakeClient())
    assert set(view['profiles']) == {'draft', 'query', 'embedding'}
    assert view['profiles']['embedding']['mode'] == 'disabled'
    assert view['profiles']['embedding']['model'] == 'text-embedding-3-small'
    for purpose in ('draft', 'query'):
        profile = view['profiles'][purpose]
        assert profile['revision'] == 0
        assert profile['mode'] == 'inherited'
        assert profile['ready'] and profile['provider'] == 'fake'
        assert profile['model'] == 'environment-model'
    assert 'NEVER_RETURN_THIS_SECRET' not in str(view)
    assert isinstance(service.client('draft', lambda: FakeClient()), FakeClient)


def test_separate_profiles_persist_and_check_revisions(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_DRAFT_TOKEN', 'ACTUAL_SECRET_VALUE')
    service = LLMSettings(tmp_path)
    view = service.save({'purpose': 'draft', 'revision': 0, 'mode': 'openai-compatible',
        'model': 'draft-model', 'credential_ref': 'TEST_DRAFT_TOKEN'}, lambda: None)
    assert view['profiles']['draft']['ready']
    assert view['profiles']['draft']['revision'] == 1
    assert view['profiles']['query']['revision'] == 0
    client = service.client('draft', lambda: None)
    assert client.model == 'draft-model' and client.api_key == 'ACTUAL_SECRET_VALUE'
    assert client.base_url == 'https://api.openai.com/v1'
    assert 'ACTUAL_SECRET_VALUE' not in str(view)
    assert b'ACTUAL_SECRET_VALUE' not in service.path.read_bytes()
    persisted = LLMSettings(tmp_path)
    assert persisted.view(lambda: None)['profiles']['draft']['model'] == 'draft-model'
    with pytest.raises(DemoError, match='changed'):
        persisted.save({'purpose': 'draft', 'revision': 0, 'mode': 'disabled'})
    persisted.save({'purpose': 'query', 'revision': 0, 'mode': 'disabled'}, lambda: FakeClient())
    assert persisted.client('query', lambda: FakeClient()) is None
    assert persisted.view(lambda: None)['profiles']['query']['readiness'] == 'disabled'


def test_missing_credentials_and_inherited_unavailable_are_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv('NONEXISTENT_TOKEN', raising=False)
    service = LLMSettings(tmp_path)
    assert service.view(lambda: None)['profiles']['draft']['readiness'] == 'inherited_unavailable'
    view = service.save({'purpose': 'query', 'revision': 0, 'mode': 'openai-compatible', 'credential_ref': 'NONEXISTENT_TOKEN'}, lambda: None)
    assert view['profiles']['query']['readiness'] == 'missing_credential'
    assert service.client('query', lambda: FakeClient()) is None


@pytest.mark.parametrize('extra', [
    {'api_key': 'secret'}, {'credential_ref': 'secret-value!'},
    {'base_url': 'https://user:secret@example.com'}, {'base_url': 'https://example.com?token=secret'},
    {'base_url': 'https://example.com#secret'}, {'model': '  '},
])
def test_invalid_or_secret_bearing_settings_reject(tmp_path, extra):
    service = LLMSettings(tmp_path)
    with pytest.raises(ValidationError):
        service.save({'purpose': 'draft', 'revision': 0, 'mode': 'openai-compatible'} | extra)
    assert service.view(lambda: None)['profiles']['draft']['revision'] == 0


def test_typed_api_payload_uses_embedding_specific_defaults(tmp_path):
    from helios_core.demo.llm_settings import LLMSettingsSave
    settings = LLMSettings(tmp_path)
    payload = LLMSettingsSave.model_validate({'purpose': 'embedding', 'revision': 0})
    assert payload.mode == 'disabled'
    assert payload.model == 'text-embedding-3-small'
    assert settings.save(payload, lambda: FakeClient())['profiles']['embedding']['mode'] == 'disabled'
    assert LLMSettingsSave.model_validate({'purpose': 'draft', 'revision': 0}).model == 'gpt-4o'
    assert LLMSettingsSave.model_validate({'purpose': 'query', 'revision': 0}).mode == 'inherited'


def test_inherited_embedding_uses_openai_launch_environment(tmp_path, monkeypatch):
    from helios_core.llm import llm_from_env
    for key in ('ANTHROPIC_API_KEY', 'MISTRAL_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('INFERENCE_BASE_URL', 'https://api.openai.com/v1')
    monkeypatch.setenv('INFERENCE_TOKEN', 'TEST_ONLY_TOKEN')
    monkeypatch.setenv('INFERENCE_MODEL', 'generation-model')
    settings = LLMSettings(tmp_path)
    settings.save({'purpose': 'embedding', 'revision': 0, 'mode': 'inherited'}, llm_from_env)
    client = settings.client('embedding', llm_from_env)
    assert client.base_url == 'https://api.openai.com/v1'
    assert client.model == 'text-embedding-3-small'
    assert client.api_key == 'TEST_ONLY_TOKEN'


@pytest.mark.parametrize('purpose',['draft','query','embedding'])
def test_direct_key_is_encrypted_persistent_and_write_only(tmp_path,purpose):
    service=LLMSettings(tmp_path)
    secret='test-private-api-key-do-not-return'
    body={'purpose':purpose,'revision':0,'mode':'openai-compatible','credential_mode':'api_key','api_key':secret}
    view=service.save(body,lambda:None)
    assert view['profiles'][purpose]['ready']
    assert view['profiles'][purpose]['has_saved_api_key']
    assert secret not in str(view)
    assert 'api_key' not in view['profiles'][purpose]
    for path in tmp_path.rglob('*'):
        if path.is_file():assert secret.encode() not in path.read_bytes()
    assert (tmp_path/'.model-secrets').stat().st_mode&0o777==0o700
    assert (tmp_path/'.model-secrets/key').stat().st_mode&0o777==0o600
    reopened=LLMSettings(tmp_path)
    assert reopened.client(purpose).api_key==secret
    # Empty input preserves the saved key. Stale updates cannot rotate it.
    reopened.save(body|{'revision':1,'api_key':''},lambda:None)
    assert reopened.client(purpose).api_key==secret
    with pytest.raises(DemoError,match='changed'):
        reopened.save(body|{'revision':1,'api_key':'stale-replacement'},lambda:None)
    assert reopened.client(purpose).api_key==secret
    reopened.save(body|{'revision':2,'api_key':'new-private-key'},lambda:None)
    assert reopened.client(purpose).api_key=='new-private-key'
    result=reopened.save(body|{'revision':3,'api_key':None,'clear_api_key':True},lambda:None)
    assert not result['profiles'][purpose]['has_saved_api_key']
    assert not result['profiles'][purpose]['ready']
    assert reopened.client(purpose) is None


def test_direct_key_does_not_fall_back_to_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('INFERENCE_TOKEN','unrelated-environment-key')
    service=LLMSettings(tmp_path)
    view=service.save({'purpose':'query','revision':0,'mode':'openai-compatible','credential_mode':'api_key'},lambda:None)
    assert not view['profiles']['query']['ready']
    assert service.client('query') is None


def test_bare_openai_origin_normalizes_without_changing_custom_endpoints(tmp_path):
    from helios_core.demo.llm_settings import LLMProfile
    assert LLMProfile(base_url='https://api.openai.com').base_url=='https://api.openai.com/v1'
    assert LLMProfile(base_url='https://api.openai.com/').base_url=='https://api.openai.com/v1'
    assert LLMProfile(base_url='https://custom.example.test').base_url=='https://custom.example.test'
