"""Persist source profiles without claiming remote connectivity or storing credentials."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .registry import DemoError


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class CredentialConfig(StrictConfig):
    credential_ref: str = Field(default='', max_length=120, pattern=r'^$|^[A-Za-z_][A-Za-z0-9_]*$')


def validate_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Endpoint has an invalid port or host') from None
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Endpoint requires HTTP or HTTPS with no embedded credentials')
    if parsed.query or parsed.fragment or any(c.isspace() for c in value):
        raise ValueError('Endpoint cannot contain query parameters, fragments, or whitespace')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Endpoint port must be between 1 and 65535')
    return value.rstrip('/')


class LocalConfig(StrictConfig):
    pack_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_-]*$')


class IcebergConfig(CredentialConfig):
    catalog_uri: str = Field(min_length=1, max_length=1000)
    warehouse: str = Field(min_length=1, max_length=1000)
    namespace: str = Field(default='', max_length=160)

    _endpoint = field_validator('catalog_uri')(validate_endpoint)

    @field_validator('warehouse')
    @classmethod
    def warehouse_location(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {'s3', 's3a', 'abfs', 'abfss', 'gs', 'file', 'http', 'https'}:
            raise ValueError('Warehouse requires an object storage, file, or HTTP URI')
        if parsed.query or parsed.fragment or parsed.username or parsed.password or any(c.isspace() for c in value):
            raise ValueError('Warehouse URI cannot contain credentials, query parameters, or fragments')
        if parsed.scheme in {'http', 'https'}:
            validate_endpoint(value)
        if not parsed.path or (parsed.scheme != 'file' and not parsed.netloc):
            raise ValueError('Warehouse URI requires a storage path')
        return value


class TrinoConfig(CredentialConfig):
    endpoint: str = Field(min_length=1, max_length=1000)
    catalog: str = Field(min_length=1, max_length=160)
    schema_name: str = Field(alias='schema', min_length=1, max_length=160)
    username: str = Field(default='', max_length=160)
    _endpoint = field_validator('endpoint')(validate_endpoint)


class AtlasConfig(CredentialConfig):
    endpoint: str = Field(min_length=1, max_length=1000)
    _endpoint = field_validator('endpoint')(validate_endpoint)


CONFIG_TYPES = {'local': LocalConfig, 'iceberg': IcebergConfig, 'trino': TrinoConfig, 'atlas': AtlasConfig}


class ConnectionCreate(StrictConfig):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['local', 'iceberg', 'trino', 'atlas']
    description: str = Field(default='', max_length=1500)
    config: dict


class ConnectionUpdate(StrictConfig):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=1500)
    config: dict
    kind: Literal['local', 'iceberg', 'trino', 'atlas'] | None = None


def connection_schemas() -> dict:
    return {kind: model.model_json_schema() for kind, model in CONFIG_TYPES.items()}


class ConnectionStore:
    def __init__(self, state_root: Path, pack_ids, pack_metadata=None):
        self.path = Path(state_root).resolve() / 'connections.sqlite'
        pack_ids = tuple(pack_ids)
        self.pack_ids = set(pack_ids)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS connections (id TEXT PRIMARY KEY, content TEXT NOT NULL)')
            for pack_id in pack_ids:
                metadata = (pack_metadata or {}).get(pack_id, {})
                if pack_id in self.pack_ids:
                    record = {'id': pack_id, 'name': metadata.get('title', pack_id.capitalize() + ' sample'), 'kind': 'local',
                              'description': metadata.get('description', 'Built-in synthetic dataset connection'), 'config': {'pack_id': pack_id},
                              'revision': 1, 'status': 'ready', 'builtin': True}
                    conn.execute('INSERT OR IGNORE INTO connections VALUES (?, ?)', (pack_id, json.dumps(record)))

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def _config(self, kind, value):
        config = CONFIG_TYPES[kind].model_validate(value).model_dump(by_alias=True)
        if kind == 'local' and config['pack_id'] not in self.pack_ids:
            raise DemoError('Local connection must use a registered dataset pack')
        return config

    def list(self) -> dict:
        with self._connect() as conn:
            return {'items': [json.loads(row[0]) for row in conn.execute('SELECT content FROM connections ORDER BY rowid')]}

    def get(self, identifier: str) -> dict:
        with self._connect() as conn:
            row = conn.execute('SELECT content FROM connections WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise DemoError('Source connection not found')
        return json.loads(row[0])

    def create(self, payload: ConnectionCreate | dict) -> dict:
        payload = ConnectionCreate.model_validate(payload)
        config = self._config(payload.kind, payload.config)
        record = payload.model_dump() | {'id': 'source-' + uuid.uuid4().hex, 'config': config,
            'revision': 1, 'status': 'ready' if payload.kind == 'local' else 'configured', 'builtin': False}
        with self._connect() as conn:
            conn.execute('INSERT INTO connections VALUES (?, ?)', (record['id'], json.dumps(record)))
        return record

    def update(self, identifier: str, payload: ConnectionUpdate | dict) -> dict:
        payload = ConnectionUpdate.model_validate(payload)
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT content FROM connections WHERE id=?', (identifier,)).fetchone()
            if row is None:
                raise DemoError('Source connection not found')
            previous = json.loads(row[0])
            if payload.kind is not None and payload.kind != previous['kind']:
                raise DemoError('Source connection type cannot change after creation')
            if previous['revision'] != payload.revision:
                raise DemoError('Source connection changed; reload before saving')
            config = self._config(previous['kind'], payload.config)
            if previous['builtin'] and config != previous['config']:
                raise DemoError('Built-in connections must retain their registered dataset pack')
            record = previous | payload.model_dump(exclude={'revision', 'kind'}) | {'config': config, 'revision': payload.revision + 1}
            conn.execute('UPDATE connections SET content=? WHERE id=?', (json.dumps(record), identifier))
        return record
