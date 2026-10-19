"""Material API keeps revision guards and provider credentials behind public routes."""
import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.console import demo
from apps.helios.tests.test_materials import EvidenceModel, Vectors


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('HELIOS_DEMO_DATASET', 'power')
    monkeypatch.setenv('HELIOS_DEMO_STATE', str(tmp_path))
    llm = EvidenceModel()
    llm.base_url = 'https://model.example.test/v1'
    monkeypatch.setattr(demo, 'llm_from_env', lambda: llm)
    app = FastAPI()
    app.include_router(demo.demo_router)
    demo.configure_demo(app)
    with TestClient(app) as http:
        yield http, app, llm


def upload(http, text='Total planned maintenance minutes; not observed downtime.', **changes):
    response = http.post('/demo/api/materials/upload', json={'filename': 'policy.md', 'content_base64': base64.b64encode(text.encode()).decode()} | changes)
    assert response.status_code == 200, response.text
    return response.json()


def path(item, action=None):
    return '/demo/api/materials/' + item['document_id'] + ('/' + action if action else '')


def test_catalog_upload_detail_analysis_and_revision_history(client):
    http, app, llm = client
    catalog = http.get('/demo/api/materials')
    assert catalog.status_code == 200
    assert catalog.json() == {'items': [], 'embedding_ready': False}
    item = upload(http)
    assert item['revision'] == 1
    assert http.get(path(item)).json()['sha256'] == item['sha256']
    assert http.get('/demo/api/materials').json()['items'][0]['document_id'] == item['document_id']
    response = http.post(path(item, 'analyze'), json={'revision': 1})
    assert response.status_code == 200, response.text
    assert response.json()['analysis']['claims'][0]['quote'] in item['chunks'][0]['text']
    assert len(llm.calls) == 1
    newer = upload(http, 'New maintenance policy.', document_id=item['document_id'])
    assert newer['revision'] == 2
    assert http.get(path(item), params={'revision': 1}).json()['sha256'] == item['sha256']
    assert http.post(path(item, 'analyze'), json={'revision': 1}).status_code == 409
    assert len(llm.calls) == 1
    assert http.get(path(item)).headers['Cache-Control'] == 'no-store'


def test_keyword_review_apply_and_draft_revision_guards(client):
    http, app, llm = client
    item = upload(http)
    suggested = http.post(path(item, 'suggest'), json={'revision': 1})
    assert suggested.status_code == 200, suggested.text
    link = next(l for l in suggested.json()['links'] if l['source'] == 'manufacturing')
    apply = {'revision': 1, 'link_ids': [link['id']], 'source': 'manufacturing', 'expected_revision': 0}
    assert http.post(path(item, 'apply'), json=apply).status_code == 409
    assert http.post(path(item, 'review'), json={'revision': 1, 'link_ids': [link['id']], 'decision': 'approved', 'reviewer': 'API test', 'note': 'Confirmed source scope.'}).status_code == 200
    assert http.post(path(item, 'apply'), json=apply | {'expected_revision': 9}).status_code == 409
    response = http.post(path(item, 'apply'), json=apply)
    assert response.status_code == 200, response.text
    draft = http.get('/demo/api/context', params={'source': 'manufacturing'}).json()['draft']
    assert draft['revision'] == 1
    assert draft['definition']['document_attachments'][0]['supporting_material']['document_id'] == item['document_id']
    assert http.post(path(item, 'apply'), json=apply).status_code == 409
    assert http.get('/demo/api/context', params={'source': 'finance'}).json()['draft']['revision'] == 0


def test_disabled_embedding_and_drafting_profiles_fail_without_calls(client):
    http, app, llm = client
    item = upload(http)
    response = http.post(path(item, 'suggest'), json={'revision': 1, 'use_embeddings': True})
    assert response.status_code == 409
    assert 'embedding model' in response.json()['detail']
    assert not llm.calls
    assert http.post('/demo/api/llm/test', json={'purpose': 'embedding'}).status_code == 409
    assert http.post('/demo/api/llm', json={'purpose': 'draft', 'mode': 'disabled', 'revision': 0}).status_code == 200
    assert http.post(path(item, 'analyze'), json={'revision': 1}).status_code == 409
    assert not llm.calls


def test_embedding_profile_connection_test_and_material_matching(client, monkeypatch):
    http, app, llm = client
    vectors = Vectors()
    vectors.provider = 'test-embeddings'
    settings = app.state.demo_llm_settings
    original = settings.client

    def fake_client(purpose, fallback_factory=None):
        return vectors if purpose == 'embedding' else original(purpose, fallback_factory)

    monkeypatch.setattr(settings, 'client', fake_client)
    response = http.post('/demo/api/llm/test', json={'purpose': 'embedding'})
    assert response.status_code == 200, response.text
    assert response.json()['dimensions'] == 3
    assert response.json()['model'] == vectors.model
    assert http.get('/demo/api/materials').json()['embedding_ready'] is True
    item = upload(http)
    response = http.post(path(item, 'suggest'), json={'revision': 1, 'use_embeddings': True})
    assert response.status_code == 200, response.text
    assert response.json()['matching']['method'] == 'keyword+embedding'
    assert len(vectors.calls) > 1
    assert not llm.calls


@pytest.mark.parametrize('action', ['analyze', 'suggest'])
def test_provider_failures_never_echo_tokens_or_document_text(client, monkeypatch, action):
    http, app, llm = client
    item = upload(http)
    secret = 'TOKEN-DO-NOT-RETURN private document payload https://secret-provider.test'

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    if action == 'analyze':
        monkeypatch.setattr(llm, 'complete', fail)
        payload = {'revision': 1}
    else:
        vectors = Vectors()
        monkeypatch.setattr(vectors, 'embed', fail)
        monkeypatch.setattr(app.state.demo_llm_settings, 'client', lambda *args, **kwargs: vectors)
        payload = {'revision': 1, 'use_embeddings': True}
    response = http.post(path(item, action), json=payload)
    assert response.status_code == 502
    assert secret not in response.text
    assert 'TOKEN-DO-NOT-RETURN' not in response.text
    stored = http.get(path(item)).json()
    assert stored['analysis'] is None and stored['links'] == []


@pytest.mark.parametrize('suffix', ['material-invalid', 'material-' + 'a' * 32 + '/download', 'material-' + 'a' * 32 + '/analyze/extra', '../llm/settings'])
def test_public_route_allowlist_blocks_invalid_material_paths(client, suffix):
    http, app, llm = client
    response = http.get('/demo/api/materials/' + suffix)
    assert response.status_code == 404
    assert response.json()['detail'] == 'Unavailable in local sample mode'


def test_material_input_and_unknown_selection_errors_are_safe(client):
    http, app, llm = client
    assert http.post('/demo/api/materials/upload', json={'filename': 'bad.txt', 'content_base64': 'invalid!'}).status_code == 409
    assert http.get('/demo/api/materials/material-' + 'f' * 32).status_code == 409
    item = upload(http)
    response = http.post(path(item, 'review'), json={'revision': 1, 'link_ids': ['missing'], 'decision': 'approved', 'reviewer': 'Test', 'note': 'Checked'})
    assert response.status_code == 409
    assert 'unknown link' in response.json()['detail']


@pytest.mark.parametrize('error,expected', [
    ('timeout', 'provider timed out'),
    ('budget', 'exhausted its output budget'),
    ('provider', 'The model request failed.'),
])
def test_analysis_model_failures_are_explained_without_provider_text(client, monkeypatch, error, expected):
    from helios_core.llm.client import LLMError, LLMTimeoutError
    http, _, llm = client
    item = upload(http)
    secret = 'PRIVATE-KEY-123 document text'
    def fail(system, user):
        raise {'timeout': LLMTimeoutError('openai provider timed out (response limit: 30 seconds)'),
               'budget': LLMError('The model exhausted its output budget before completing the response.'),
               'provider': LLMError(secret)}[error]
    monkeypatch.setattr(llm, 'complete', fail)
    response = http.post(path(item, 'analyze'), json={'revision': 1})
    assert response.status_code == 502
    assert expected in response.json()['detail'] and secret not in response.text
