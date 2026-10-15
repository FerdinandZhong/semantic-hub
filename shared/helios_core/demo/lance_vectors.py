"""Local Lance-format embedding cache with provider and dimension isolation."""
from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path

from .registry import DemoError

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def valid_vector(vector) -> bool:
    return (isinstance(vector, list) and 0 < len(vector) <= 8192
            and all(type(value) in (int, float) and math.isfinite(value) for value in vector))


class LanceVectorStore:
    """Persist one fixed-size Lance table per provider fingerprint and dimension.

    SQLite is read only for migration, except invalid legacy namespaces are cleared.
    New embeddings live exclusively in Lance. Duplicate text retains one row.
    """

    def __init__(self, path):
        self.path = Path(path)
        with _LOCKS_GUARD:
            self.lock = _LOCKS.setdefault(str(self.path.resolve()), threading.RLock())

    def _connect(self):
        import lancedb
        return lancedb.connect(str(self.path))

    @staticmethod
    def _prefix(fingerprint):
        return 'embeddings_' + text_hash(fingerprint) + '_d'

    def _tables(self, db, fingerprint):
        prefix = self._prefix(fingerprint)
        names = []
        token = None
        while True:
            page = db.list_tables(page_token=token)
            names.extend(name for name in page.tables if name.startswith(prefix))
            token = page.page_token
            if token is None:
                return names

    def _clear(self, db, fingerprint, legacy_db):
        for name in self._tables(db, fingerprint):
            db.drop_table(name)
        if legacy_db is not None:
            legacy_db.execute('DELETE FROM material_vectors WHERE fingerprint=?', (fingerprint,))
            legacy_db.commit()

    def _put(self, db, client, texts, vectors):
        import pyarrow as pa
        dimension = len(next(iter(vectors.values())))
        name = self._prefix(client.fingerprint) + str(dimension)
        schema = pa.schema([
            ('text_sha256', pa.string()), ('fingerprint', pa.string()),
            ('text', pa.string()), ('model', pa.string()), ('endpoint', pa.string()),
            ('dimension', pa.int32()), ('vector', pa.list_(pa.float64(), dimension)),
        ])
        table = db.create_table(name, schema=schema, exist_ok=True)
        rows = [{'text_sha256': key, 'fingerprint': client.fingerprint,
                 'text': texts[key], 'model': str(getattr(client, 'model', '')),
                 'endpoint': str(getattr(client, 'base_url', getattr(client, 'endpoint', ''))),
                 'dimension': dimension, 'vector': vector}
                for key, vector in vectors.items()]
        table.merge_insert('text_sha256').when_not_matched_insert_all().execute(
            pa.Table.from_pylist(rows, schema=schema))

    def vectors(self, client, texts, legacy_db=None):
        """Return ordered vectors, migrate old cache rows, and embed only missing text."""
        if not texts:
            return []
        with self.lock:
            db = self._connect()
            hashes = [text_hash(text) for text in texts]
            by_hash = dict(zip(hashes, texts))
            cached = {}
            stored_dimensions = set()
            for name in self._tables(db, client.fingerprint):
                table = db.open_table(name)
                stored_dimensions.add(table.schema.field('vector').type.list_size)
                # Keys are generated hexadecimal SHA256 values, never user SQL.
                keys = ','.join("'" + key + "'" for key in by_hash)
                for row in table.search().where(f'text_sha256 IN ({keys})').limit(len(by_hash)).to_list():
                    cached[row['text_sha256']] = row['vector']
            migrated = {}
            if legacy_db is not None:
                for key in by_hash:
                    if key in cached:
                        continue
                    row = legacy_db.execute(
                        'SELECT vector FROM material_vectors WHERE fingerprint=? AND hash=?',
                        (client.fingerprint, key)).fetchone()
                    if row:
                        try:
                            migrated[key] = json.loads(row[0])
                        except (ValueError, TypeError):
                            migrated[key] = None
            cached.update(migrated)
            dimensions = stored_dimensions | {len(v) for v in cached.values() if valid_vector(v)}
            if any(not valid_vector(v) for v in cached.values()) or len(dimensions) > 1:
                self._clear(db, client.fingerprint, legacy_db)
                raise DemoError('The cached embedding index was invalid and has been cleared. Retry matching.')
            expected = next(iter(dimensions)) if dimensions else None
            if migrated:
                self._put(db, client, by_hash, migrated)
            missing = [key for key in by_hash if key not in cached]
            for offset in range(0, len(missing), 32):
                batch = missing[offset:offset + 32]
                output = client.embed([by_hash[key] for key in batch])
                if not isinstance(output, list) or len(output) != len(batch):
                    raise DemoError('The embedding provider returned an invalid batch.')
                if any(not valid_vector(v) for v in output):
                    raise DemoError('The embedding provider returned invalid vectors.')
                dimensions = {len(v) for v in output}
                if len(dimensions) != 1 or (expected is not None and expected not in dimensions):
                    self._clear(db, client.fingerprint, legacy_db)
                    raise DemoError('Embedding dimensions changed. The old index was cleared; retry with a stable model.')
                expected = next(iter(dimensions))
                created = dict(zip(batch, output))
                self._put(db, client, by_hash, created)
                cached.update(created)
            return [cached[key] for key in hashes]
