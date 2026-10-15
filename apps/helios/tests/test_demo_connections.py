"""Source profiles are strict, revision-bound, and contain references instead of secrets."""
import pytest
from pydantic import ValidationError
from helios_core.demo.connections import ConnectionStore, connection_schemas
from helios_core.demo.registry import DemoError

PACKS = ['finance', 'manufacturing', 'pharma', 'power']


def test_builtin_seeding_and_persistence(tmp_path):
    store = ConnectionStore(tmp_path, PACKS)
    assert [item['id'] for item in store.list()['items']] == PACKS
    assert all(item['status'] == 'ready' for item in store.list()['items'])
    assert len(ConnectionStore(tmp_path, PACKS).list()['items']) == 4
    old = store.get('power')
    updated = store.update('power', {'revision': 1, 'kind': 'local', 'name': 'Power source', 'description': 'Operator label', 'config': old['config']})
    assert updated['revision'] == 2
    assert ConnectionStore(tmp_path, PACKS).get('power')['name'] == 'Power source'
    with pytest.raises(DemoError, match='changed'):
        store.update('power', {'revision': 1, 'name': 'Stale', 'config': old['config']})
    with pytest.raises(DemoError, match='retain'):
        store.update('power', {'revision': 2, 'name': 'Other', 'config': {'pack_id': 'finance'}})
    with pytest.raises(DemoError, match='type'):
        store.update('power', {'revision': 2, 'kind': 'atlas', 'name': 'Other', 'config': {'endpoint': 'https://atlas.example'}})


@pytest.mark.parametrize('kind,config', [
    ('local', {'pack_id': 'pharma'}),
    ('iceberg', {'catalog_uri': 'https://catalog.example:8181', 'warehouse': 's3://warehouse/root', 'namespace': 'analytics', 'credential_ref': 'ICEBERG_TOKEN'}),
    ('trino', {'endpoint': 'https://trino.example:8443', 'catalog': 'iceberg', 'schema': 'analytics', 'username': 'analyst', 'credential_ref': 'TRINO_TOKEN'}),
    ('atlas', {'endpoint': 'http://atlas.example:21000', 'credential_ref': 'ATLAS_TOKEN'}),
])
def test_type_specific_profiles_are_configured_without_network_claim(tmp_path, kind, config):
    store = ConnectionStore(tmp_path, PACKS)
    saved = store.create({'name': 'Source', 'kind': kind, 'config': config})
    assert saved['status'] == ('ready' if kind == 'local' else 'configured')
    assert saved['builtin'] is False
    assert store.get(saved['id']) == saved
    assert store.get(saved['id'])['config'] | config == store.get(saved['id'])['config']
    assert connection_schemas()[kind]['additionalProperties'] is False


@pytest.mark.parametrize('value', [
    'https://user:password@example.com', 'https://example.com?token=secret',
    'https://example.com#secret', 'ftp://example.com', 'https://example.com:0',
    'https://example.com:65536', 'https://example.com:invalid', 'https://example.com secret',
])
def test_secret_bearing_or_invalid_endpoint_rejects_without_writes(tmp_path, value):
    store = ConnectionStore(tmp_path, PACKS)
    with pytest.raises(ValidationError):
        store.create({'name': 'Source', 'kind': 'atlas', 'config': {'endpoint': value}})
    assert len(store.list()['items']) == 4


@pytest.mark.parametrize('extra', [{'password': 'secret'}, {'token': 'secret'}, {'credential_ref': 'actual-token-value!'}])
def test_plaintext_credentials_reject(tmp_path, extra):
    store = ConnectionStore(tmp_path, PACKS)
    with pytest.raises(ValidationError):
        store.create({'name': 'Source', 'kind': 'atlas', 'config': {'endpoint': 'https://atlas.example'} | extra})


def test_local_pack_allowlist_and_unknown_profile(tmp_path):
    store = ConnectionStore(tmp_path, PACKS)
    with pytest.raises(DemoError, match='registered'):
        store.create({'name': 'Source', 'kind': 'local', 'config': {'pack_id': 'unknown'}})
    with pytest.raises(DemoError, match='not found'):
        store.get('missing')


def test_new_registered_pack_seeds_without_changing_existing_profiles(tmp_path):
    store = ConnectionStore(tmp_path, PACKS)
    old = store.get('power')
    store.update('power', {'revision': 1, 'name': 'Operator power', 'config': old['config']})
    metadata = {'pharma_intelligence': {
        'title': 'Pharmaceutical Industry Intelligence & New Drug Analysis',
        'description': 'Built-in public source-derived dataset connection',
    }}
    expanded = ConnectionStore(tmp_path, PACKS + ['pharma_intelligence'], metadata)
    source = expanded.get('pharma_intelligence')
    assert source['name'] == metadata['pharma_intelligence']['title']
    assert source['description'] == metadata['pharma_intelligence']['description']
    assert source['config'] == {'pack_id': 'pharma_intelligence'}
    assert expanded.get('power')['name'] == 'Operator power'
    assert expanded.get('power')['revision'] == 2
    assert len(ConnectionStore(tmp_path, PACKS + ['pharma_intelligence'], metadata).list()['items']) == 5
