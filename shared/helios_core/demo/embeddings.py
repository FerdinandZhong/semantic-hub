"""Bounded OpenAI-compatible embeddings with credential-safe failures."""
from __future__ import annotations

import hashlib
import json
import math

import httpx

from .connections import validate_endpoint
from helios_core.llm import LLMError, LLMTimeoutError


class EmbeddingClient:
    provider = 'openai'
    max_batch = 128
    max_text_chars = 16000
    max_total_chars = 256000
    max_dimensions = 8192

    def __init__(self, model: str, api_key: str, base_url: str, timeout: float = 30):
        self.model = model
        self.api_key = api_key
        self.base_url = validate_endpoint(base_url).rstrip('/')
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 120:
            raise ValueError('Embedding timeout must be between 0 and 120 seconds')
        self.timeout = timeout
        self.fingerprint = hashlib.sha256(json.dumps(
            {'endpoint': self.base_url, 'model': model}, sort_keys=True).encode()).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or not 1 <= len(texts) <= self.max_batch:
            raise LLMError('Embedding input must contain between 1 and 128 texts')
        if any(not isinstance(text, str) or not text.strip() or len(text) > self.max_text_chars for text in texts):
            raise LLMError('Embedding texts must be nonempty and at most 16000 characters')
        if sum(map(len, texts)) > self.max_total_chars:
            raise LLMError('Embedding batch exceeds the input limit')
        try:
            response = httpx.post(self.base_url + '/embeddings',
                headers={'Authorization': 'Bearer ' + self.api_key, 'content-type': 'application/json'},
                json={'model': self.model, 'input': texts, 'encoding_format': 'float'},
                timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10)))
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException:
            raise LLMTimeoutError('Embedding provider timed out') from None
        except httpx.HTTPStatusError as exc:
            raise LLMError(f'Embedding provider returned HTTP {exc.response.status_code}') from None
        except httpx.HTTPError:
            raise LLMError('Embedding provider request failed') from None
        except (ValueError, TypeError):
            raise LLMError('Embedding provider returned invalid JSON') from None
        try:
            data = body['data']
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError()
            vectors = [None] * len(texts)
            dimension = None
            for item in data:
                index = item['index']
                vector = item['embedding']
                if type(index) is not int or not 0 <= index < len(texts) or vectors[index] is not None:
                    raise ValueError()
                if not isinstance(vector, list) or not 1 <= len(vector) <= self.max_dimensions:
                    raise ValueError()
                if dimension is not None and len(vector) != dimension:
                    raise ValueError()
                if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
                    raise ValueError()
                dimension = len(vector)
                vectors[index] = [float(value) for value in vector]
            return vectors
        except (KeyError, TypeError, ValueError, OverflowError):
            raise LLMError('Embedding provider returned invalid vectors') from None

    def ping(self) -> bool:
        return bool(self.embed(['Semantic Hub connection test']))
