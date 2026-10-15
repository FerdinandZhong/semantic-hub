"""Bounded metadata collectors. No raw event payloads or NiFi REST discovery."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class DiscoveryError(RuntimeError):
    """A safe error that omits credentials, response bodies and request URLs."""


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    kind: Literal["elasticsearch", "kibana", "prometheus", "grafana"]
    url: str
    index: str = ""
    username: str = Field(default="", repr=False, exclude=True)
    password: SecretStr = Field(default=SecretStr(""), exclude=True)
    token: SecretStr = Field(default=SecretStr(""), exclude=True)
    limit: int = Field(default=100, ge=1, le=200)
    timeout: float = Field(default=10, ge=1, le=30)
    ca_bundle: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Use an HTTP(S) base URL without credentials or query parameters")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_index(self):
        if self.kind in {"elasticsearch", "kibana"}:
            if (not re.fullmatch(r"[a-zA-Z0-9_.\-*]+", self.index)
                    or self.index in {"*", "_all", ".", ".."}):
                raise ValueError("Configure a scoped log index pattern")
        return self


def safe_text(value, limit=1000):
    text = str(value or "")[:limit]
    text = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[redacted]", text)
    text = re.sub(r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+",
                  r"\1[redacted]", text)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", text)


def _identifier(source, name):
    return hashlib.sha256(f"{source}\0{name}".encode()).hexdigest()[:24]


def _item(source, kind, name, properties, description=""):
    return {"id": _identifier(source.name, name), "source": source.name, "kind": kind,
            "technical_name": safe_text(name, 300), "properties": properties,
            "description": safe_text(description), "aliases": [], "reviewed": False}


class _Collector:
    def __init__(self, source, transport):
        self.source = source
        self.deadline = time.monotonic() + 60
        self.client = httpx.Client(
            timeout=source.timeout, follow_redirects=False,
            verify=source.ca_bundle or True, transport=transport,
            auth=(source.username, source.password.get_secret_value()) if source.username else None,
            headers={"Authorization": "Bearer " + source.token.get_secret_value()}
            if source.token.get_secret_value() else {},
        )

    def get(self, path, **params):
        if time.monotonic() >= self.deadline:
            raise DiscoveryError(f"{self.source.name}: discovery deadline exceeded")
        method, headers = "GET", {}
        if self.source.kind == "kibana":
            path = path.lstrip("/")
            if params:
                path += "?" + str(httpx.QueryParams(params))
            params = {"path": path, "method": "GET"}
            path, method, headers = "/api/console/proxy", "POST", {"kbn-xsrf": "helios-discovery"}
        try:
            with self.client.stream(method, self.source.url + path,
                                    params=params, headers=headers) as response:
                if not response.is_success:
                    raise DiscoveryError(f"{self.source.name}: metadata API returned HTTP {response.status_code}")
                payload = bytearray()
                for part in response.iter_bytes():
                    payload.extend(part)
                    if len(payload) > 2_000_000:
                        raise DiscoveryError(f"{self.source.name}: metadata exceeded the 2 MB limit")
                return json.loads(payload)
        except DiscoveryError:
            raise
        except (httpx.HTTPError, ValueError):
            raise DiscoveryError(f"{self.source.name}: metadata API unavailable or invalid") from None

    def collect(self):
        source = self.source
        items, notes = [], []
        if source.kind in {"elasticsearch", "kibana"}:
            fields = self.get('/' + quote(source.index, safe='*.-_') + '/_field_caps', fields='*').get('fields')
            if not isinstance(fields, dict):
                raise DiscoveryError(f"{source.name}: missing field capabilities")
            reserved = {'_id', '_index', '_source', '_version', '_seq_no', '_primary_term',
                        '_ignored', '_ignored_source', '_field_names', '_routing', '_inference_fields'}
            visible = [(name, value) for name, value in sorted(fields.items()) if name not in reserved]
            for name, variants in visible[:source.limit]:
                if not isinstance(variants, dict) or not variants:
                    raise DiscoveryError(f"{source.name}: invalid field capabilities")
                properties = {"types": sorted(variants),
                    "searchable": all(v.get('searchable', False) for v in variants.values()),
                    "aggregatable": all(v.get('aggregatable', False) for v in variants.values()),
                    "type_conflict": len(variants) != 1}
                items.append(_item(source, 'log_field', name, properties,
                                   f"Discovered log field {name}; business meaning requires review."))
            notes.append(f"{len(visible)} visible fields; {len(items)} collected. No log messages were sampled.")
            if len(visible) > source.limit:
                notes.append("Field inventory is truncated by the configured limit.")
        elif source.kind == 'prometheus':
            doc = self.get('/api/v1/metadata', limit=source.limit)
            if doc.get('status') != 'success' or not isinstance(doc.get('data'), dict):
                raise DiscoveryError(f"{source.name}: invalid Prometheus metadata")
            for name, entries in sorted(doc['data'].items())[:source.limit]:
                if not isinstance(entries, list) or not entries:
                    raise DiscoveryError(f"{source.name}: invalid metric metadata")
                types = sorted({safe_text(e.get('type', 'unknown'), 50) for e in entries})
                units = sorted({safe_text(e.get('unit', ''), 50) for e in entries})
                help_text = '; '.join(sorted({safe_text(e.get('help', '')) for e in entries}))
                items.append(_item(source, 'metric', name,
                    {"types": types, "units": units, "type_conflict": len(types) != 1,
                     "unit_conflict": len(units) != 1}, help_text))
            notes.append("Metadata has no per-target label inventory; labels and series require separate bounded discovery.")
            if len(items) >= source.limit:
                notes.append("Metric inventory may be truncated by the configured limit.")
        else:
            listing = self.get('/api/search', type='dash-db', limit=source.limit)
            if not isinstance(listing, list):
                raise DiscoveryError(f"{source.name}: invalid Grafana dashboard inventory")
            for dashboard in listing[:source.limit]:
                if len(items) >= source.limit:
                    break
                uid = str(dashboard.get('uid', ''))
                if not uid or len(uid) > 100:
                    continue
                doc = self.get('/api/dashboards/uid/' + quote(uid, safe='')).get('dashboard', {})
                def panels(entries):
                    for panel in entries:
                        yield panel
                        yield from panels(panel.get('panels', []))
                for panel in panels(doc.get('panels', [])):
                    if len(items) >= source.limit:
                        break
                    name = f"{uid}:{panel.get('id', 'unknown')}"
                    fields = panel.get('fieldConfig', {}).get('defaults', {})
                    queries = [safe_text(t.get('expr', t.get('query', '')), 1500)
                               for t in panel.get('targets', [])[:10]]
                    items.append(_item(source, 'dashboard_panel', name,
                        {"dashboard_uid": uid, "dashboard_title": safe_text(doc.get('title')),
                         "panel_title": safe_text(panel.get('title')), "display_unit": safe_text(fields.get('unit'), 80),
                         "query_examples": queries, "executable": False}, panel.get('description', '')))
            notes.append("Panel queries are untrusted examples, not approved executable templates. Display units may include transformations.")
            if len(listing) >= source.limit or len(items) >= source.limit:
                notes.append("Dashboard or panel inventory may be truncated by the configured limit.")
        return items, notes


def discover(sources: list[Source], *, transport=None):
    """Collect metadata from explicit operator-configured endpoints without fallback."""
    if not sources or len(sources) > 8 or len({s.name for s in sources}) != len(sources):
        raise ValueError("Configure one to eight sources with unique names")
    snapshot = {"schema": "helios.observability.discovery.v1",
                "collected_at": datetime.now(timezone.utc).isoformat(), "sources": [], "items": []}
    for source in sources:
        collector = _Collector(source, transport)
        try:
            items, notes = collector.collect()
        except (KeyError, TypeError, AttributeError):
            raise DiscoveryError(f"{source.name}: unexpected metadata structure") from None
        finally:
            collector.client.close()
        snapshot['sources'].append({"name": source.name, "kind": source.kind,
            "url": source.url, "index": source.index, "notes": notes})
        snapshot['items'].extend(items)
    return snapshot
