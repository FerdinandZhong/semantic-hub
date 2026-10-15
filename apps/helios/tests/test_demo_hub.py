"""Hub exposes source profiles and isolates each local semantic workspace."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.helios.console import demo


def make_app(monkeypatch, root):
    monkeypatch.setenv('HELIOS_DEMO_DATASET', 'power')
    monkeypatch.setenv('HELIOS_DEMO_STATE', str(root))
    app = FastAPI()
    app.include_router(demo.demo_router)
    demo.configure_demo(app)
    return app


def binding(config):
    return {key: config[key] for key in ('pack_id', 'snapshot_sha256', 'session_id')}


def test_hub_catalog_and_selected_source(monkeypatch, tmp_path):
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        assert client.get('/demo').status_code == 200
        catalog = client.get('/demo/api/hub').json()
        assert {source['id'] for source in catalog['sources']} == {'finance', 'manufacturing', 'pharma', 'power', 'pharma_intelligence'}
        assert all(source['model'] is not None for source in catalog['sources'])
        assert catalog['default_source'] == 'power'
        intelligence = next(source for source in catalog['sources'] if source['id'] == 'pharma_intelligence')
        assert intelligence['name'] == 'Pharmaceutical Industry Intelligence & New Drug Analysis'
        assert intelligence['model']['synthetic'] is False
        assert intelligence['model']['generation_mode'] == 'public-source-derived; curated published facts'
        assert 'synthetic' not in intelligence['description'].lower()
        intelligence_config = client.get('/demo/api/config?source=pharma_intelligence').json()
        assert intelligence_config['mode'] == 'public_source_derived'
        assert intelligence_config['synthetic'] is False
        intelligence_draft = client.get('/demo/api/context?source=pharma_intelligence').json()['draft']
        assert 'synthetic' not in intelligence_draft['definition']['description'].lower()
        for source in catalog['sources']:
            config = client.get('/demo/api/config', params={'source': source['id']}).json()
            assert config['pack_id'] == source['id']
            assert config['connection_id'] == source['id']
            assert client.get(source['query_url']).status_code == 200
            assert client.get(source['studio_url']).status_code == 200
        assert client.get('/demo/api/hub/source?source=missing').status_code == 404
        assert client.get('/demo/api/config?source=missing').status_code == 409


def test_same_pack_connections_isolate_state_and_persist(monkeypatch, tmp_path):
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        sources = [client.post('/demo/api/connections', json={'name': name, 'kind': 'local', 'config': {'pack_id': 'power'}}).json()
                   for name in ('Operator A', 'Operator B')]
        config_a, config_b = [client.get('/demo/api/config', params={'source': source['id']}).json() for source in sources]
        assert config_a['session_id'] != config_b['session_id']
        draft = client.get('/demo/api/context', params={'source': sources[0]['id']}).json()['draft']
        draft['definition']['title'] = 'Operator A semantic context'
        payload = binding(config_a) | {'revision': 0, 'definition': draft['definition']}
        assert client.post('/demo/api/context/draft', params={'source': sources[1]['id']}, json=payload).status_code == 409
        assert client.post('/demo/api/context/draft', params={'source': sources[0]['id']}, json=payload).status_code == 200
        assert client.get('/demo/api/context', params={'source': sources[1]['id']}).json()['draft']['revision'] == 0
        assert client.get('/demo/api/context').json()['draft']['revision'] == 0
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        state = client.get('/demo/api/context', params={'source': sources[0]['id']}).json()['draft']
        assert state['revision'] == 1
        assert state['definition']['title'] == 'Operator A semantic context'
        assert client.get('/demo/api/context', params={'source': sources[1]['id']}).json()['draft']['revision'] == 0
        assert client.post('/demo/api/context/propose', params={'source': sources[0]['id']}, json=binding(config_a) | {'revision': 1, 'mode': 'evidence'}).status_code == 409


@pytest.mark.parametrize('kind,config', [
    ('iceberg', {'catalog_uri': 'https://catalog.example', 'warehouse': 's3://warehouse/root'}),
    ('trino', {'endpoint': 'https://trino.example', 'catalog': 'iceberg', 'schema': 'analytics'}),
    ('atlas', {'endpoint': 'https://atlas.example'}),
])
def test_remote_profiles_have_setup_without_borrowed_models(monkeypatch, tmp_path, kind, config):
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        response = client.post('/demo/api/connections', json={'name': 'Remote source', 'kind': kind, 'config': config})
        assert response.status_code == 200, response.text
        source = client.get('/demo/api/hub/source', params={'source': response.json()['id']}).json()
        assert source['status'] == 'configured'
        assert source['model'] is None
        assert source['query_url'] is None
        assert source['capabilities']['query'] is False
        assert source['message']
        assert client.get(source['studio_url']).status_code == 200
        assert client.get('/demo/api/context', params={'source': source['id']}).status_code == 409
        assert client.get('/demo/query', params={'source': source['id']}).status_code == 409


def test_connection_validation_revision_and_old_session(monkeypatch, tmp_path):
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        invalid = client.post('/demo/api/connections', json={'name': 'Secret', 'kind': 'atlas', 'config': {'endpoint': 'https://user:password@atlas.example'}})
        assert invalid.status_code == 422
        assert 'password' not in invalid.text
        old = client.get('/demo/api/config?source=power').json()
        payload = {'id': 'power', 'kind': 'local', 'revision': 1, 'name': 'Updated power', 'config': {'pack_id': 'power'}}
        assert client.post('/demo/api/connections/update', json=payload).status_code == 200
        assert client.post('/demo/api/connections/update', json=payload).status_code == 409
        new = client.get('/demo/api/config?source=power').json()
        assert new['session_id'] != old['session_id']
        assert new['connection_name'] == 'Updated power'
        assert client.post('/demo/api/context/propose?source=power', json=binding(old) | {'revision': 0, 'mode': 'evidence'}).status_code == 409
        assert client.post('/demo/api/context/propose?source=power', json=binding(new) | {'revision': 0, 'mode': 'evidence'}).status_code == 200


def test_hub_preserves_existing_published_version_and_active_query_context(monkeypatch, tmp_path):
    from apps.helios.tests.test_demo_context import definition, approve_items, review_request, publish
    from helios_core.demo.context import ContextDefinition
    app = make_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        runtime = app.state.demo_runtime
        workspace = runtime.workspace
        workspace.save(0, ContextDefinition.model_validate(definition(workspace)))
        workspace.validate(1)
        approve_items(runtime)
        workspace.review(review_request(runtime))
        publish(runtime)
        workspace.activate('v1', workspace.release('v1')['context_sha256'])
        original = workspace.view()
    with TestClient(make_app(monkeypatch, tmp_path)) as client:
        model = client.get('/demo/api/hub/source?source=power').json()['model']
        assert model['status'] == 'published'
        assert model['versions'] == original['versions']
        assert model['active_version'] == 'v1'
        assert client.get('/demo/api/context?source=power').json() == original
        assert client.get('/demo/api/hub/source?source=finance').json()['model']['versions'] == []
