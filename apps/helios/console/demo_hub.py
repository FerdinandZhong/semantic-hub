"""Connection-scoped local model catalog; remote profiles never borrow fixtures."""
from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import urlencode

from helios_core.demo.connections import ConnectionStore
from helios_core.demo.registry import DemoError
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.document_facts import DocumentModelRegistry
import json


class DemoHub:
    def __init__(self, registry, state_root: Path, default_runtime):
        self.registry = registry = DocumentModelRegistry(registry, state_root)
        self.state_root = state_root
        self.default_source = default_runtime.pack.entry.id
        metadata = {}
        for entry in registry.entries.values():
            pack = registry.load(entry.id)
            metadata[entry.id] = {
                'title': entry.title,
                'description': ('Reviewed document-derived source' if entry.data_origin == 'document_evidence' else
                                'Built-in synthetic dataset connection' if pack.synthetic else
                                'Built-in public source-derived dataset connection'),
            }
        self.connections = ConnectionStore(state_root, registry.entries, metadata)
        source = self.connections.get(self.default_source)
        self._runtimes = {(source['id'], source['revision']): default_runtime}
        self._lock = threading.RLock()

    def create_document_model(self, item, payload):
        with self._lock:
            key = self.registry.create(item, payload)
            record = {'id': key, 'name': payload.title, 'description': 'Reviewed document-derived source; semantic publication pending.',
                      'kind': 'local', 'config': {'pack_id': key}, 'revision': 1, 'status': 'ready', 'builtin': False}
            self.connections.pack_ids.add(key)
            with self.connections._connect() as db:
                db.execute('INSERT OR IGNORE INTO connections VALUES (?,?)', (key, json.dumps(record)))
            return {'source': key, 'studio_url': '/demo/context?' + urlencode({'source': key}) + '#source'}

    def runtime(self, source_id):
        source = self.connections.get(source_id)
        if source['kind'] != 'local':
            raise DemoError('Import this connection’s source data before building or querying its semantic model')
        key = (source['id'], source['revision'])
        with self._lock:
            if key not in self._runtimes:
                # Builtin packs keep all pre-Hub drafts and immutable versions.
                # Added connections receive their own state, even for the same pack.
                state = self.state_root if source['builtin'] else self.state_root / 'connections' / source['id']
                self._runtimes[key] = DemoRuntime(self.registry.load(source['config']['pack_id']), state)
            return self._runtimes[key]

    def source(self, source_id):
        source = self.connections.get(source_id)
        suffix = '?' + urlencode({'source': source_id})
        item = source | {
            'studio_url': '/demo/context' + suffix,
            'query_url': '/demo/query' + suffix if source['kind'] == 'local' else None,
            'capabilities': {'studio': True, 'query': source['kind'] == 'local'},
            'model': None,
            'message': '',
        }
        if source['kind'] == 'local':
            runtime = self.runtime(source_id)
            view = runtime.workspace.view()
            definition = view['draft']['definition']
            versions = view['versions']
            status = ('published' if any(v.get('published') for v in versions) else 'reviewed' if versions
                      else 'draft' if view['draft']['revision'] else 'starter')
            item['model'] = {
                'title': definition['title'], 'description': definition['description'], 'status': status,
                'metric_count': len(definition['metrics']), 'table_count': len(runtime.pack.tables),
                'draft_revision': view['draft']['revision'], 'active_version': view['active_version'],
                'versions': versions, 'snapshot_sha256': runtime.pack.fingerprint,
                'source_name': runtime.pack.source_name,
                'generation_mode': runtime.pack.generation_mode,
                'synthetic': runtime.pack.synthetic,
            }
        else:
            item['message'] = ('Atlas supplies metadata and glossary terms. Pair it with a query source before SQL validation.'
                               if source['kind'] == 'atlas' else
                               'Connection profile saved. Source import is required before semantic authoring and SQL validation.')
        return item

    def catalog(self):
        return {
            'sources': [self.source(source['id']) for source in self.connections.list()['items']],
            'local_datasets': [{'id': entry.id, 'title': entry.title} for entry in self.registry.entries.values()],
            'default_source': self.default_source,
        }

    def close(self):
        with self._lock:
            for runtime in self._runtimes.values():
                runtime.close()
