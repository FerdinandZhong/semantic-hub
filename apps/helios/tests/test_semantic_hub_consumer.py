"""Consumer HTTP contracts use isolated published state, never hosted services."""
import json

import pytest
from fastapi.testclient import TestClient

from apps.helios.console.demo_hub import DemoHub
from apps.helios.console.semantic_hub_api import PREFIX, create_application
from apps.helios.tests.test_demo_context import validated, review_request, publish
from apps.helios.tests.test_pharma_intelligence import registry, FIXTURES
from helios_core.demo.runtime import DemoRuntime

METRIC = 'us_new_medicine_sales_share_percent'
QUESTION = 'US share of new medicines launched during 2020–2024'


class FakeSettings:
    def __init__(self, embedding=None):
        self.embedding = embedding

    def client(self, role):
        assert role == 'embedding'
        return self.embedding


@pytest.fixture(scope='module')
def published(tmp_path_factory):
    root = tmp_path_factory.mktemp('consumer-api')
    reg = registry()
    runtime = DemoRuntime(reg.load('pharma_intelligence'), root)
    hub = DemoHub(reg, root, runtime)
    value = runtime.workspace.seed()
    refs = {item['metric']: item['reference_sql'] for item in json.loads(
        (FIXTURES / 'pharma_intelligence/evaluation/references.json').read_text())}
    for metric in value['metrics']:
        metric['reference_sql'] = refs[metric['name']]
    validated(runtime, value)
    runtime.workspace.review(review_request(runtime))
    publish(runtime)
    pin = dict(model_id='pharma_intelligence', version='v1',
               context_sha256=runtime.workspace.release('v1')['context_sha256'])
    yield hub, runtime, pin
    hub.close()


@pytest.fixture
def client(published, monkeypatch):
    monkeypatch.setenv('SEMANTIC_HUB_API_TOKEN', 'consumer-test-secret')
    with TestClient(create_application(published[0], FakeSettings()),
                    headers={'Authorization': 'Bearer consumer-test-secret'}) as value:
        yield value


def post(client, endpoint, body):
    return client.post(PREFIX + '/' + endpoint, json=body)


def resolved(client, pin, question=QUESTION):
    response = post(client, 'resolve', pin | dict(query=question, metric=METRIC, required_fields=[
        "industry_observations.period_start", "industry_observations.period_end"]))
    assert response.status_code == 200, response.text
    return pin | dict(bundle_id=response.json()['bundle_id'], question=question,
                      metrics=[METRIC], dimensions=[], filters=[], limit=10)


def test_authentication_fails_closed_and_schema_is_protected(client, monkeypatch):
    for endpoint in ('capabilities', 'models', 'openapi.json'):
        response = client.get(PREFIX + '/' + endpoint, headers={'Authorization': 'Bearer invalid'})
        assert response.status_code == 401
        assert response.headers['www-authenticate'] == 'Bearer'
        assert response.headers['cache-control'] == 'no-store'
    monkeypatch.delenv('SEMANTIC_HUB_API_TOKEN')
    response = client.get(PREFIX + '/capabilities')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'api_not_configured'


def test_inventory_excludes_unpublished_models_and_reports_capabilities(client):
    inventory = client.get(PREFIX + '/models').json()
    assert [item['model_id'] for item in inventory['items']] == ['pharma_intelligence']
    assert inventory['total'] == 1
    assert client.get(PREFIX + '/models', params={'offset': 1}).json()['items'] == []
    assert client.get(PREFIX + '/models/power').status_code == 404
    caps = client.get(PREFIX + '/capabilities').json()
    assert caps['search']['keyword'] is True and caps['search']['embedding'] is False
    assert caps['execution']['arbitrary_sql'] is False


def test_swagger_shell_requires_token_to_load_schema_and_call_api(client):
    shell=client.get('/docs',headers={'Authorization':''})
    assert shell.status_code==200
    assert 'Consumer API token' in shell.text
    assert 'persistAuthorization:false' in shell.text
    assert 'consumer-test-secret' not in shell.text
    assert client.get('/docs/assets/swagger-ui-bundle.js').status_code==200
    assert client.get(PREFIX+'/openapi.json',headers={'Authorization':''}).status_code==401
    schema=client.get(PREFIX+'/openapi.json').json()
    assert schema['components']['securitySchemes']['ConsumerBearer']=={'type':'http','scheme':'bearer'}
    for path,operations in schema['paths'].items():
        assert path.startswith(PREFIX)
        for operation in operations.values():
            assert {'ConsumerBearer':[]} in operation['security']


def test_version_details_graph_documents_and_pin_rejection(client, published):
    pin = published[2]
    base = PREFIX + '/models/pharma_intelligence'
    assert client.get(base).json()['versions']
    assert client.get(base + '/versions').json()['versions'][0]['version'] == 'v1'
    for suffix in ('', '/graph', '/documents'):
        response = client.get(base + '/versions/v1' + suffix, params={'context_sha256': pin['context_sha256']})
        assert response.status_code == 200, response.text
        assert response.json()['context_sha256'] == pin['context_sha256']
        assert client.get(base + '/versions/v1' + suffix,
                          params={'context_sha256': '0' * 64}).status_code == 409
    details = client.get(base + '/versions/v1').json()
    assert details['immutable'] is True
    assert METRIC in {metric['name'] for metric in details['definition']['metrics']}
    assert client.get(base + '/versions/v1/documents').json()['items'] == []


def test_keyword_search_and_explicit_embedding_unavailability(client, published):
    body = published[2] | dict(query='new medicine', limit=5)
    result = post(client, 'search', body).json()
    assert result['method'] == 'keyword' and result['items']
    assert all(item['context_sha256'] == published[2]['context_sha256'] for item in result['items'])
    response = post(client, 'search', body | dict(mode='embedding'))
    assert response.status_code == 409
    assert 'Embedding search is unavailable' in response.text


def test_resolve_compile_and_sample_execution_are_pinned(client, published):
    request = resolved(client, published[2])
    compiled = post(client, 'compile', request)
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()['status'] == 'ready'
    assert compiled.json()['sql'] and 'rows' not in compiled.json()
    response = post(client, 'query', request)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer['status'] == 'answered'
    assert float(answer['rows'][0][0]) == 74.1
    assert answer['context_sha256'] == published[2]['context_sha256']
    assert answer['engine'] == 'local_duckdb'
    for change in (dict(bundle_id='unknown-bundle'), dict(context_sha256='0' * 64), dict(version='missing')):
        assert post(client, 'query', request | change).status_code == 409
    assert post(client, 'query', request | dict(limit=101)).status_code == 422
    assert post(client, 'query', request | dict(metrics=[METRIC, METRIC])).status_code == 422
    assert post(client, 'query', request | dict(sql='SELECT 74.1')).status_code == 422


@pytest.mark.parametrize('explicit_metric', [True, False])
def test_resolve_automatically_includes_mandatory_cohort_fields(client, published, explicit_metric):
    body = published[2] | dict(query=QUESTION)
    if explicit_metric:
        body['metric'] = METRIC
    response = post(client, 'resolve', body)
    assert response.status_code == 200, response.text
    context = response.json()
    assert context['status'] == 'ready', context
    request = published[2] | dict(bundle_id=context['bundle_id'], question=QUESTION,
        metrics=[METRIC], dimensions=[], filters=[], limit=10)
    compiled = post(client, 'compile', request)
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()['status'] == 'ready'
    assert compiled.json()['request']['filters'] == [
        dict(field='industry_observations.period_start', op='=', value=2020),
        dict(field='industry_observations.period_end', op='=', value=2024)]


def test_missing_cohort_is_no_data_and_fixed_geography_cannot_change(client, published):
    pin = published[2]
    question = 'US share of new medicines launched from 1999 to 2020'
    coverage = post(client, 'coverage', pin | dict(metric=METRIC, question=question)).json()
    assert coverage['status'] == 'no_data'
    response = post(client, 'query', resolved(client, pin, question)).json()
    assert response['status'] == 'no_data' and response['rows'] == []
    request = resolved(client, pin) | dict(filters=[
        dict(field='industry_observations.geography', op='=', value='Korea')])
    response = post(client, 'query', request)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'unsupported_scope'
    assert response.json()['rows'] == []
    assert 'USA' in response.json()['message']


def test_surface_has_no_model_mutations_or_authoring_routes(client):
    schema = client.get(PREFIX + '/openapi.json').json()
    post_paths = {path for path, methods in schema['paths'].items() if 'post' in methods}
    assert post_paths == {PREFIX + '/' + path for path in ('search', 'resolve', 'coverage', 'compile', 'query')}
    assert not any({'put', 'patch', 'delete'} & set(methods) for methods in schema['paths'].values())
    assert client.post('/demo/api/context/publish', json={}).status_code == 404
    assert client.post(PREFIX + '/models', json={}).status_code == 405


class FakeEmbedding:
    model = 'test-semantic-embedding'
    fingerprint = 'consumer-test-embedding-v1'
    base_url = 'https://not-called.invalid'

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        # Deliberately rank the requested semantic metric above unrelated records.
        return [[1.0, 0.0] if text == 'semantic target' or METRIC in text else [0.0, 1.0]
                for text in texts]


def test_embedding_ranking_uses_provider_vectors_and_lance_cache(client, published):
    pytest.importorskip('lancedb')
    embedding = FakeEmbedding()
    client.app.state.semantic_hub_consumer.settings = FakeSettings(embedding)
    assert client.get(PREFIX + '/capabilities').json()['search']['embedding'] is True
    body = published[2] | dict(query='semantic target', mode='embedding', limit=3)
    first = post(client, 'search', body)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['method'] == 'embedding' and result['storage'] == 'Lance'
    assert result['items'][0]['name'] == METRIC
    assert result['items'][0]['score'] == 1.0
    assert embedding.calls
    embedding.calls.clear()
    assert post(client, 'search', body).json() == result
    assert embedding.calls == []


def test_explicit_local_mode_needs_no_token_and_keeps_version_binding(published, monkeypatch):
    monkeypatch.delenv('SEMANTIC_HUB_API_TOKEN', raising=False)
    with TestClient(create_application(published[0], FakeSettings(), local_no_auth=True)) as client:
        assert client.get(PREFIX+'/models').status_code == 200
        assert 'without authentication' in client.get(PREFIX+'/capabilities').json()['authorization']
        schema = client.get(PREFIX+'/openapi.json').json()
        assert 'securitySchemes' not in schema['components']
        assert all('security' not in op for ops in schema['paths'].values() for op in ops.values())
        assert 'const localNoAuth=true' in client.get('/docs').text
        query = resolved(client, published[2])
        assert post(client, 'query', query).json()['status'] == 'answered'
        query['context_sha256'] = '0'*64
        assert post(client, 'query', query).status_code == 409
