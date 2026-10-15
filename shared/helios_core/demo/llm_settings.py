"""Independent model settings with environment references or encrypted local API keys."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from cryptography.fernet import Fernet, InvalidToken

from helios_core.llm import LLMClient, llm_from_env
from .connections import validate_endpoint
from .embeddings import EmbeddingClient
from .registry import DemoError

Purpose = Literal['draft', 'query', 'embedding']
Mode = Literal['inherited', 'disabled', 'openai-compatible']


class LLMProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    mode: Mode = 'inherited'
    model: str = Field(default='gpt-4o', min_length=1, max_length=160)
    base_url: str = Field(default='https://api.openai.com/v1', min_length=1, max_length=1000)
    credential_ref: str = Field(default='INFERENCE_TOKEN', min_length=1, max_length=120,
                                pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    credential_mode: Literal['environment', 'api_key'] = 'environment'
    @field_validator('base_url')
    @classmethod
    def model_endpoint(cls,value):
        value=validate_endpoint(value)
        parsed=urlsplit(value)
        if parsed.hostname=='api.openai.com' and parsed.path in ('','/'):
            return value.rstrip('/')+'/v1'
        return value

    @field_validator('model')
    @classmethod
    def nonblank_model(cls, value):
        if not value.strip() or any(char in value for char in '\r\n\x00'):
            raise ValueError('Model must be a nonempty model identifier')
        return value.strip()


class LLMSettingsSave(LLMProfile):
    purpose: Purpose
    revision: int = Field(ge=0)
    api_key: SecretStr | None = Field(default=None, exclude=True)
    clear_api_key: bool = Field(default=False, exclude=True)

    @field_validator('api_key')
    @classmethod
    def valid_api_key(cls, value):
        if value is None:
            return value
        key=value.get_secret_value().strip()
        if len(key)>8192 or any(char.isspace() or ord(char)<32 for char in key):
            raise ValueError('API key must contain no whitespace and at most 8192 characters')
        return SecretStr(key) if key else None

    @model_validator(mode='after')
    def credential_choice(self):
        if self.api_key and (self.mode!='openai-compatible' or self.credential_mode!='api_key' or self.clear_api_key):
            raise ValueError('Select API key authentication before setting a key; do not set and remove it together')
        return self

    @model_validator(mode='before')
    @classmethod
    def purpose_defaults(cls, value):
        if isinstance(value, dict) and value.get('purpose') == 'embedding':
            return {'mode': 'disabled', 'model': 'text-embedding-3-small'} | value
        return value


class LLMSettings:
    def __init__(self, state_root: Path):
        self.path = Path(state_root).resolve() / 'llm-settings.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS llm_settings (purpose TEXT PRIMARY KEY, revision INTEGER NOT NULL, content TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS llm_credentials (purpose TEXT PRIMARY KEY, ciphertext BLOB NOT NULL)')

    def _cipher(self, create=False):
        directory=self.path.parent/'.model-secrets'
        key_path=directory/'key'
        if create:
            directory.mkdir(mode=0o700,exist_ok=True)
            directory.chmod(0o700)
            try:
                fd=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(Fernet.generate_key())
        try:
            return Fernet(key_path.read_bytes())
        except (OSError,ValueError):
            raise DemoError('The local credential store is unavailable. Restore its key file or enter a new API key.') from None

    def _saved_key(self,purpose):
        with self._connect() as conn:
            row=conn.execute('SELECT ciphertext FROM llm_credentials WHERE purpose=?',(purpose,)).fetchone()
        if not row:return None
        try:
            return self._cipher().decrypt(row[0]).decode()
        except (InvalidToken,UnicodeError):
            raise DemoError('The saved API key cannot be read. Enter a replacement key.') from None

    def _credential(self,purpose,profile):
        return self._saved_key(purpose) if profile.credential_mode=='api_key' else os.environ.get(profile.credential_ref)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def _stored(self, purpose):
        if purpose not in ('draft', 'query', 'embedding'):
            raise DemoError('Unknown LLM purpose')
        with self._connect() as conn:
            row = conn.execute('SELECT revision, content FROM llm_settings WHERE purpose=?', (purpose,)).fetchone()
        return (row[0], LLMProfile.model_validate(json.loads(row[1]))) if row else (0, LLMProfile(mode='disabled', model='text-embedding-3-small') if purpose == 'embedding' else LLMProfile())

    def client(self, purpose: Purpose, fallback_factory=None):
        _, profile = self._stored(purpose)
        if profile.mode == 'disabled':
            return None
        if profile.mode == 'inherited':
            inherited = (fallback_factory or llm_from_env)()
            if purpose != 'embedding':
                return inherited
            if inherited is None or getattr(inherited, 'provider', '') not in ('openai', 'mistral'):
                return None
            if not getattr(inherited, 'api_key', None) or not getattr(inherited, 'base_url', None):
                return None
            try:
                return EmbeddingClient(profile.model, inherited.api_key, inherited.base_url)
            except ValueError:
                return None
        credential = self._credential(purpose,profile)
        if not credential:
            return None
        return EmbeddingClient(profile.model, credential, profile.base_url) if purpose == 'embedding' else LLMClient('openai', profile.model, credential, profile.base_url)

    def _public(self, purpose, fallback_factory):
        revision, profile = self._stored(purpose)
        inherited = self.client(purpose, fallback_factory) if profile.mode == 'inherited' else None
        with self._connect() as conn:
            saved_key=conn.execute('SELECT 1 FROM llm_credentials WHERE purpose=?',(purpose,)).fetchone() is not None
        try:
            credential_ready=bool(self._credential(purpose,profile)) if profile.mode=='openai-compatible' else False
        except DemoError:
            credential_ready=False
        ready = bool(inherited) if profile.mode == 'inherited' else profile.mode == 'openai-compatible' and credential_ready
        readiness = ('disabled' if profile.mode == 'disabled' else 'ready' if ready else
                     'inherited_unavailable' if profile.mode == 'inherited' else 'missing_credential')
        public = profile.model_dump() | {'purpose': purpose, 'revision': revision, 'configured': ready, 'has_saved_api_key':saved_key,
            'ready': ready, 'readiness': readiness,
            'provider': getattr(inherited, 'provider', None) if profile.mode == 'inherited' else 'openai' if profile.mode == 'openai-compatible' else None,
            'source': 'environment' if profile.mode == 'inherited' else 'disabled' if profile.mode == 'disabled' else 'settings'}
        if profile.mode == 'inherited' and inherited is None:
            public['model'] = profile.model if purpose == 'embedding' else ''
            public['base_url'] = ''
        if inherited is not None:
            public['model'] = getattr(inherited, 'model', '')
            public['base_url'] = getattr(inherited, 'base_url', None) or ''
            # Environment-derived client URLs are not persisted. Hide malformed or secret-bearing URLs.
            if public['base_url']:
                try:
                    public['base_url'] = validate_endpoint(public['base_url'])
                except ValueError:
                    public['base_url'] = ''
        return public

    def view(self, fallback_factory=None):
        return {'profiles': {purpose: self._public(purpose, fallback_factory) for purpose in ('draft', 'query', 'embedding')}}

    def save(self, payload: LLMSettingsSave | dict, fallback_factory=None):
        payload = LLMSettingsSave.model_validate(payload)
        profile = LLMProfile.model_validate(payload.model_dump(exclude={'purpose', 'revision'}))
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT revision FROM llm_settings WHERE purpose=?', (payload.purpose,)).fetchone()
            revision = row[0] if row else 0
            if revision != payload.revision:
                raise DemoError('LLM settings changed; reload before saving')
            if payload.clear_api_key:
                conn.execute('DELETE FROM llm_credentials WHERE purpose=?',(payload.purpose,))
            elif payload.api_key:
                encrypted=self._cipher(create=True).encrypt(payload.api_key.get_secret_value().encode())
                conn.execute('INSERT INTO llm_credentials VALUES (?,?) ON CONFLICT(purpose) DO UPDATE SET ciphertext=excluded.ciphertext',
                             (payload.purpose,encrypted))
            conn.execute('INSERT INTO llm_settings VALUES (?, ?, ?) ON CONFLICT(purpose) DO UPDATE SET revision=excluded.revision,content=excluded.content',
                         (payload.purpose, revision + 1, json.dumps(profile.model_dump())))
        return self.view(fallback_factory)
