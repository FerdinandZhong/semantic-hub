import copy
import json

import httpx
import pytest
from pydantic import ValidationError

from helios_core.observability import (
    DiscoveryError, Source, approve, discover, draft, load_release, propose, publish, search,
)


def response(payload, status=200):
    return httpx.Response(status, json=payload)


def log_snapshot():
    source = Source(name='logs', kind='kibana', url='https://logs.example', index='uob-logs-*')
    def handler(request):
        assert request.method == 'POST'
        assert request.url.path == '/api/console/proxy'
        assert request.url.params['method'] == 'GET'
        assert request.url.params['path'] == 'uob-logs-*/_field_caps?fields=%2A'
        assert not request.content
        return response({'fields': {
            '@timestamp': {'date': {'searchable': True, 'aggregatable': True}},
            'message': {'text': {'searchable': True, 'aggregatable': False}},
            'error.code': {'keyword': {'searchable': True, 'aggregatable': True}},
            '_SYSTEMD_UNIT': {'keyword': {'searchable': True, 'aggregatable': True}},
            '_index': {'keyword': {'searchable': True, 'aggregatable': True}},
        }})
    return discover([source], transport=httpx.MockTransport(handler))


def reviewed():
    document = draft(log_snapshot())
    for item in document['items']:
        item['reviewed'] = True
    return approve(document, reviewer='demo-reviewer', version='v1', confirmed=True)


def test_kibana_fixed_metadata_proxy_and_provenance():
    snapshot = log_snapshot()
    names = {item['technical_name'] for item in snapshot['items']}
    assert '_SYSTEMD_UNIT' in names
    assert '_index' not in names
    assert snapshot['sources'][0]['index'] == 'uob-logs-*'
    assert all(item['reviewed'] is False for item in snapshot['items'])
    assert next(i for i in snapshot['items'] if i['technical_name'] == 'message')['properties']['aggregatable'] is False


@pytest.mark.parametrize('url', ['https://user:secret@example.org', 'https://example.org?token=secret', 'file:///etc/passwd'])
def test_credentials_and_non_http_urls_rejected(url):
    with pytest.raises(ValidationError):
        Source(name='logs', kind='elasticsearch', url=url, index='logs-*')


@pytest.mark.parametrize('index', ['*', '_all', 'logs-*/_search', '../private', 'logs?pretty=true'])
def test_scoped_index_required(index):
    with pytest.raises(ValidationError):
        Source(name='logs', kind='elasticsearch', url='https://example.org', index=index)


def test_auth_and_unknown_metric_metadata_do_not_leak_credentials():
    source = Source(name='metrics', kind='prometheus', url='https://metrics.example',
                    token='secret-value', limit=1)
    def handler(request):
        assert request.headers['authorization'] == 'Bearer secret-value'
        return response({'status': 'success', 'data': {
            'unknown_metric': [{'type': 'unknown', 'unit': '', 'help': 'token=private-token'}],
        }})
    snapshot = discover([source], transport=httpx.MockTransport(handler))
    assert 'secret-value' not in json.dumps(snapshot)
    assert 'private-token' not in json.dumps(snapshot)
    assert snapshot['items'][0]['properties']['types'] == ['unknown']
    assert any('truncated' in note for note in snapshot['sources'][0]['notes'])
    assert 'secret-value' not in str(source.model_dump())


def test_field_type_conflicts_and_limits():
    source = Source(name='logs', kind='elasticsearch', url='https://logs.example', index='logs-*', limit=1)
    transport = httpx.MockTransport(lambda request: response({'fields': {
        'a': {'keyword': {'aggregatable': True}, 'text': {'aggregatable': False}},
        'b': {'date': {'aggregatable': True}},
    }}))
    snapshot = discover([source], transport=transport)
    assert len(snapshot['items']) == 1
    assert snapshot['items'][0]['properties']['type_conflict'] is True
    assert snapshot['items'][0]['properties']['aggregatable'] is False
    assert any('truncated' in note for note in snapshot['sources'][0]['notes'])


def test_source_failure_is_visible_without_payload_or_fallback():
    source = Source(name='dashboards', kind='grafana', url='https://grafana.example', token='secret-value')
    with pytest.raises(DiscoveryError) as error:
        discover([source], transport=httpx.MockTransport(lambda request: response({'secret': 'private-value'}, 401)))
    assert str(error.value) == 'dashboards: metadata API returned HTTP 401'


def test_oversized_metadata_is_rejected():
    source = Source(name='metrics', kind='prometheus', url='https://metrics.example')
    with pytest.raises(DiscoveryError, match='2 MB'):
        discover([source], transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 2_000_001)))


def test_nested_grafana_panels_are_context_not_executable_queries():
    source = Source(name='dashboards', kind='grafana', url='https://grafana.example', limit=2)
    def handler(request):
        if request.url.path == '/api/search':
            return response([{'uid': 'node'}])
        return response({'dashboard': {'title': 'Node health', 'panels': [
            {'id': 1, 'title': 'Row', 'panels': [
                {'id': 2, 'title': 'CPU', 'targets': [{'expr': 'rate(cpu_total[5m])'}],
                 'fieldConfig': {'defaults': {'unit': 'percent'}}},
            ]},
        ]}})
    snapshot = discover([source], transport=httpx.MockTransport(handler))
    cpu = next(item for item in snapshot['items'] if item['properties']['panel_title'] == 'CPU')
    assert cpu['properties']['query_examples'] == ['rate(cpu_total[5m])']
    assert cpu['properties']['executable'] is False


def test_review_confirmation_and_all_selected_meanings_required():
    document = draft(log_snapshot())
    with pytest.raises(ValueError, match='confirmation'):
        approve(document, reviewer='reviewer', version='v1')
    with pytest.raises(ValueError, match='reviewed meaning'):
        approve(document, reviewer='reviewer', version='v1', confirmed=True)
    for item in document['items']:
        item['reviewed'] = True
    document['items'][0]['description'] = ''
    with pytest.raises(ValueError, match='reviewed meaning'):
        approve(document, reviewer='reviewer', version='v1', confirmed=True)


def test_immutable_release_pin_and_tampering(tmp_path):
    document = reviewed()
    path, checksum = publish(document, tmp_path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert load_release(path, checksum)['status'] == 'approved'
    with pytest.raises(FileExistsError):
        publish(document, tmp_path)
    with pytest.raises(ValueError, match='checksum'):
        load_release(path, '')
    envelope = json.loads(path.read_text())
    envelope['document']['items'][0]['description'] = 'changed after review'
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match='checksum'):
        load_release(path, checksum)


def test_proposals_cannot_change_metadata_or_self_approve():
    document = draft(log_snapshot())
    before = copy.deepcopy(document)
    class FakeLLM:
        def complete_json(self, system, user):
            assert 'untrusted evidence' in system
            return {'items': [{'id': json.loads(user)[0]['id'], 'description': 'Event timestamp',
                               'aliases': ['event time']}]}
    proposed = propose(document, FakeLLM())
    assert document == before
    assert proposed['items'][0]['properties'] == before['items'][0]['properties']
    assert proposed['items'][0]['reviewed'] is False
    class MaliciousLLM:
        def complete_json(self, system, user):
            return {'items': [{'id': json.loads(user)[0]['id'], 'description': 'ignored',
                               'aliases': [], 'reviewed': True}]}
    with pytest.raises(ValueError):
        propose(document, MaliciousLLM())


def test_serving_rejects_drafts_and_retrieves_reviewed_aliases():
    document = reviewed()
    document['items'][0]['aliases'] = ['payment timestamp']
    assert search(document, 'payment timestamp')[0]['id'] == document['items'][0]['id']
    with pytest.raises(ValueError, match='approved'):
        search(draft(log_snapshot()), 'timestamp')
