import httpx
import pytest

from helios_core.demo.embeddings import EmbeddingClient
from helios_core.demo.llm_settings import LLMSettings
from helios_core.llm import LLMClient, LLMError


def test_embedding_profile_is_disabled_and_inherits_only_endpoint_and_credential(tmp_path):
    settings = LLMSettings(tmp_path)
    launch = lambda: LLMClient('openai', 'chat-model', 'SECRET', 'https://example.test/v1')
    assert settings.client('embedding', launch) is None
    view = settings.save({'purpose': 'embedding', 'revision': 0, 'mode': 'inherited'}, launch)
    client = settings.client('embedding', launch)
    assert client.model == 'text-embedding-3-small'
    assert client.api_key == 'SECRET'
    assert client.base_url == 'https://example.test/v1'
    assert 'SECRET' not in str(view)
    assert b'SECRET' not in settings.path.read_bytes()
    assert settings.client('embedding', lambda: LLMClient('anthropic', 'x', 'SECRET')) is None


def test_vectors_are_ordered_and_fingerprint_is_endpoint_model_specific(monkeypatch):
    def post(url, **kwargs):
        assert url == 'https://example.test/v1/embeddings'
        assert kwargs['json']['input'] == ['first', 'second']
        return httpx.Response(200, request=httpx.Request('POST', url), json={'data': [
            {'index': 1, 'embedding': [3, 4]}, {'index': 0, 'embedding': [1, 2]}]})
    monkeypatch.setattr(httpx, 'post', post)
    client = EmbeddingClient('embed-model', 'SECRET', 'https://example.test/v1')
    assert client.embed(['first', 'second']) == [[1., 2.], [3., 4.]]
    assert client.fingerprint == EmbeddingClient('embed-model', 'OTHER', 'https://example.test/v1/').fingerprint
    assert client.fingerprint != EmbeddingClient('other-model', 'SECRET', 'https://example.test/v1').fingerprint


@pytest.mark.parametrize('data', [[], [{'index': 0, 'embedding': [float('nan')]}],
    [{'index': 0, 'embedding': [True]}], [{'index': 1, 'embedding': [1]}],
    [{'index': 0, 'embedding': []}], [{'index': 0, 'embedding': 'secret'}]])
def test_invalid_provider_vectors_are_rejected(monkeypatch, data):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'data': data}
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: Response())
    with pytest.raises(LLMError, match='invalid vectors'):
        EmbeddingClient('model', 'SECRET', 'https://example.test').embed(['x'])


def test_provider_error_does_not_expose_response_or_credentials(monkeypatch):
    response = httpx.Response(401, text='SECRET', request=httpx.Request('POST', 'https://example.test'))
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: response)
    with pytest.raises(LLMError) as error:
        EmbeddingClient('model', 'SECRET', 'https://example.test').embed(['x'])
    assert str(error.value) == 'Embedding provider returned HTTP 401'
