"""Lance vectors persist without repeating embedding provider calls."""
import json
import sqlite3

import lancedb
import pytest

from helios_core.demo.lance_vectors import LanceVectorStore, text_hash
from helios_core.demo.registry import DemoError


class Embedder:
    model = 'model-v1'
    base_url = 'https://provider.example/v1'

    def __init__(self, fingerprint='endpoint-model-v1', width=3):
        self.fingerprint = fingerprint
        self.width = width
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return [[float(len(text))] * self.width for text in texts]


def test_persistent_cache_reuses_text_and_keeps_metadata(tmp_path):
    path = tmp_path / 'vectors.lancedb'
    client = Embedder()
    store = LanceVectorStore(path)
    expected = store.vectors(client, ['alpha', 'beta', 'alpha'])
    assert client.calls == [['alpha', 'beta']]
    assert LanceVectorStore(path).vectors(client, ['beta', 'alpha']) == [expected[1], expected[0]]
    assert len(client.calls) == 1
    db = lancedb.connect(str(path))
    table = db.open_table(db.list_tables().tables[0])
    assert table.count_rows() == 2
    rows = table.to_arrow().to_pylist()
    assert rows[0]['text_sha256'] == text_hash(rows[0]['text'])
    assert rows[0]['model'] == client.model
    assert rows[0]['endpoint'] == client.base_url
    assert table.schema.field('vector').type.list_size == 3
    assert list(path.glob('*.lance'))


@pytest.mark.parametrize('fingerprint', ['different-endpoint-model-v1', 'endpoint-model-v2'])
def test_fingerprint_isolates_provider_and_model(tmp_path, fingerprint):
    store = LanceVectorStore(tmp_path / 'vectors')
    first, second = Embedder(), Embedder(fingerprint, width=2)
    store.vectors(first, ['same'])
    assert store.vectors(second, ['same']) == [[4.0, 4.0]]
    assert second.calls == [['same']]
    assert len(lancedb.connect(str(store.path)).list_tables().tables) == 2


def test_changed_dimension_clears_old_namespace_then_retries(tmp_path):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    store.vectors(client, ['old'])
    client.width = 2
    with pytest.raises(DemoError, match='dimensions changed'):
        store.vectors(client, ['old', 'new'])
    assert store.vectors(client, ['old', 'new']) == [[3.0, 3.0], [3.0, 3.0]]
    assert len(lancedb.connect(str(store.path)).list_tables().tables) == 1


def test_legacy_sqlite_migrates_without_provider_calls(tmp_path):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE material_vectors (fingerprint TEXT, hash TEXT, vector TEXT)')
    db.execute('INSERT INTO material_vectors VALUES (?, ?, ?)',
               (client.fingerprint, text_hash('cached'), json.dumps([1.0, 2.0, 3.0])))
    assert store.vectors(client, ['cached', 'cached'], db) == [[1.0, 2.0, 3.0]] * 2
    assert client.calls == []
    assert store.vectors(client, ['cached']) == [[1.0, 2.0, 3.0]]
    assert client.calls == []


@pytest.mark.parametrize('bad', [[float('nan')], [float('inf')], [], [True]])
def test_invalid_provider_vectors_do_not_persist(tmp_path, bad):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    client.embed = lambda texts: [bad]
    with pytest.raises(DemoError, match='invalid vectors'):
        store.vectors(client, ['text'])
    assert lancedb.connect(str(store.path)).list_tables().tables == []


def test_mismatched_batch_dimensions_do_not_persist(tmp_path):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    client.embed = lambda texts: [[1.0], [1.0, 2.0]]
    with pytest.raises(DemoError, match='dimensions changed'):
        store.vectors(client, ['one', 'two'])
    assert lancedb.connect(str(store.path)).list_tables().tables == []


def test_changed_dimension_is_detected_for_disjoint_text(tmp_path):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    store.vectors(client, ['old'])
    client.width = 2
    with pytest.raises(DemoError, match='dimensions changed'):
        store.vectors(client, ['new'])
    assert store.vectors(client, ['new']) == [[3.0, 3.0]]


def test_invalid_legacy_cache_is_cleared_without_provider_call(tmp_path):
    store, client = LanceVectorStore(tmp_path / 'vectors'), Embedder()
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE material_vectors (fingerprint TEXT, hash TEXT, vector TEXT)')
    db.execute('INSERT INTO material_vectors VALUES (?, ?, ?)',
               (client.fingerprint, text_hash('bad'), '[NaN]'))
    with pytest.raises(DemoError, match='cached embedding index was invalid'):
        store.vectors(client, ['bad'], db)
    assert db.execute('SELECT count(*) FROM material_vectors').fetchone()[0] == 0
    assert client.calls == []
