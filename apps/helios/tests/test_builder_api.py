"""Studio API stages candidates and preserves reviewed operator state."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.console import demo
from apps.helios.tests.test_builder_proposals import FakeLLM
from apps.helios.tests.test_demo_context import (
    binding, definition, approve_items, review_request, publish,
)
from helios_core.demo.context import ContextDefinition


@pytest.fixture
def studio(tmp_path, monkeypatch, request):
    monkeypatch.setenv('HELIOS_DEMO_DATASET', getattr(request, 'param', 'power'))
    monkeypatch.setenv('HELIOS_DEMO_STATE', str(tmp_path))
    monkeypatch.setattr(demo, 'llm_from_env', lambda: FakeLLM())
    app = FastAPI()
    app.include_router(demo.demo_router)
    demo.configure_demo(app)
    runtime = app.state.demo_runtime
    with TestClient(app) as client:
        yield client, runtime
    runtime.close()


@pytest.mark.parametrize('studio', ['finance', 'manufacturing', 'pharma', 'power'], indirect=True)
def test_api_stages_and_binding_revision_guard(studio):
    client, runtime = studio
    base = binding(runtime)
    before = client.get('/demo/api/context').json()['draft']
    status = client.get('/demo/api/context/proposals').json()
    assert status['llm_available'] and status['llm_provider'] == 'fake'
    for mode in ('evidence', 'llm'):
        response = client.post('/demo/api/context/propose', json=base | {'revision': 0, 'mode': mode})
        assert response.status_code == 200, response.text
        candidate = response.json()
        assert client.get('/demo/api/context').json()['draft'] == before
        assert candidate['mode'] == mode
    invalid = client.post('/demo/api/context/propose', json=base | {'revision': 0, 'mode': 'evidence', 'snapshot_sha256': '0' * 64})
    assert invalid.status_code == 409
    assert client.get('/demo/api/context').json()['draft'] == before
    response = client.post('/demo/api/context/proposal/apply', json=base | {'revision': 0, 'candidate_id': candidate['candidate_id']})
    assert response.status_code == 200, response.text
    assert response.json()['draft']['revision'] == 1
    assert client.post('/demo/api/context/proposal/apply', json=base | {'revision': 0, 'candidate_id': candidate['candidate_id']}).status_code == 409


def test_provider_unavailable_is_explicit(studio, monkeypatch):
    client, runtime = studio
    monkeypatch.setattr(demo, 'llm_from_env', lambda: None)
    assert client.get('/demo/api/context/proposals').json()['llm_available'] is False
    response = client.post('/demo/api/context/propose', json=binding(runtime) | {'revision': 0, 'mode': 'llm'})
    assert response.status_code == 409
    assert runtime.workspace.view()['draft']['revision'] == 0


def test_document_invalidates_validation_and_reviewed_export_preserves_metadata(studio, monkeypatch):
    client, runtime = studio
    ws = runtime.workspace
    value = definition(ws)
    value['metrics'][0].update(synonyms=['Energy consumed'], example_questions=['What is energy consumed?'],
        owner='Operations', inclusion_rules=['Reviewed source events'], exclusion_rules=['No additional exclusion'],
        ontology_concepts=['meter_readings'], evidence_refs=['table:meter_readings'],
        assumptions=['Source timezone applies'], confidence=.8, rationale='Declared source aggregate')
    ws.save(0, ContextDefinition.model_validate(value))
    ws.validate(1)
    response = client.post('/demo/api/context/document', json=binding(runtime) | {
        'revision': 1, 'filename': 'business-definition.md', 'content': 'Reviewed meter definition.', 'entity_links': []})
    assert response.status_code == 200, response.text
    state = response.json()
    assert state['draft']['revision'] == 2 and state['draft']['validation'] is None
    assert any(item['kind'] == 'document' for item in state['review']['items'])
    assert client.post('/demo/api/context/document', json=binding(runtime) | {
        'revision': 1, 'filename': 'stale.md', 'content': 'Stale', 'entity_links': []}).status_code == 409
    ws.validate(2)
    approve_items(runtime)
    documents = client.get('/demo/api/context/documents').json()['items']
    assert documents and all(doc['review_status'] == 'approved' for doc in documents)
    ws.review(review_request(runtime))
    publish(runtime)
    release = ws.release('v1')
    assert any(item['kind'] == 'ontology' for item in release['item_review']['items'])
    assert 'artifacts' in release
    ws.activate('v1', release['context_sha256'])
    active = ws.view()['active_version']
    artifacts = client.get('/demo/api/context/artifacts?version=v1')
    assert artifacts.status_code == 200, artifacts.text
    artifact = artifacts.json()
    assert any(doc['filename'] == 'business-definition.md' and doc['content'] == 'Reviewed meter definition.' for doc in artifact['documents'])
    metric = artifact['metadata']['metrics'][0]
    for key in ('synonyms', 'example_questions', 'owner', 'inclusion_rules', 'exclusion_rules', 'ontology_concepts', 'evidence_refs', 'assumptions', 'confidence', 'rationale'):
        assert metric[key] == value['metrics'][0][key]
    exported = client.get('/demo/api/context/export?version=v1')
    assert exported.status_code == 200, exported.text
    assert 'Energy consumed' in json.dumps(exported.json())
    assert 'Reviewed meter definition.' in json.dumps(exported.json())
    staged = client.post('/demo/api/context/propose', json=binding(runtime) | {'revision': 2, 'mode': 'evidence'})
    assert staged.status_code == 200
    assert ws.view()['active_version'] == active
    assert ws.release('v1')['context_sha256'] == release['context_sha256']
    # New artifact-generation code cannot rewrite an approved version's evidence.
    from helios_core.demo.builder_artifacts import BuilderArtifacts
    def no_regeneration(*args, **kwargs):
        raise AssertionError('An immutable release must return its stored artifacts')
    monkeypatch.setattr(BuilderArtifacts, 'bundle', no_regeneration)
    assert client.get('/demo/api/context/artifacts?version=v1').json() == release['artifacts']
    assert client.get('/demo/api/context/export?version=v1').json()['artifacts'] == release['artifacts']


@pytest.mark.parametrize('studio', ['finance', 'manufacturing', 'pharma', 'power'], indirect=True)
def test_readable_documents_are_scoped_and_survive_invalid_metric_sql(studio):
    client, runtime = studio
    initial = client.get('/demo/api/context/documents')
    assert initial.status_code == 200, initial.text
    items = initial.json()['items']
    assert {doc['id'] for doc in items} == {doc.document_id for doc in runtime.pack.documents}
    assert all(doc['review_status'] == 'pending' and doc['content'] for doc in items)
    text = '# Business note\n<script>untrusted source text</script>\n'
    result = client.post('/demo/api/context/document', json=binding(runtime) | {
        'revision':0,'filename':'business-note.md','content':text,'entity_links':[]})
    assert result.status_code == 200, result.text
    state = result.json()
    value = state['draft']['definition']
    value['metrics'][0]['expression'] = 'SUM(unknown_source.unknown_column)'
    runtime.workspace.save(1, ContextDefinition.model_validate(value))
    response = client.get('/demo/api/context/documents')
    assert response.status_code == 200, response.text
    doc = next(item for item in response.json()['items'] if item['origin'] == 'operator_attachment')
    assert doc['content'] == text and doc['review_status'] == 'pending'
    assert response.json()['revision'] == 2
    another = 'finance' if runtime.pack.entry.id != 'finance' else 'power'
    assert all(item['filename'] != 'business-note.md' for item in client.get('/demo/api/context/documents?source=' + another).json()['items'])
