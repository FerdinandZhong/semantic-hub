"""Framework-independent agent context service.

Only trusted application adapters construct Scope and register publication evidence.
Neither operation is an agent tool. Bundles are process-local, bounded and expiring.
"""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from helios_core.compiler import Compiler, SemanticRequest
from helios_core.ossie import SemanticModel
from .index import Clarification, SemanticIndex


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class RetrievalError(ValueError):
    """Safe failure at the application boundary."""


@dataclass(frozen=True)
class Scope:
    principal_id: str
    policy_revision: str
    releases: dict[str, str]
    allowed_fields: dict[str, frozenset[str] | None]
    context: str = ""

    def fingerprint(self):
        if not self.principal_id or not self.policy_revision:
            raise RetrievalError("Trusted caller and policy bindings are required")
        if set(self.releases) != set(self.allowed_fields):
            raise RetrievalError("Every adopted model requires an explicit field scope")
        return digest({
            "principal": self.principal_id, "policy": self.policy_revision,
            "releases": self.releases, "context": self.context,
            "fields": {key: None if value is None else sorted(value)
                       for key, value in self.allowed_fields.items()},
        })


class RetrievalService:
    def __init__(self, token_counter: Callable[[str], int] | None = None,
                 ttl_seconds: float = 300, max_bundles: int = 256):
        if ttl_seconds <= 0 or max_bundles <= 0:
            raise ValueError("Positive cache limits are required")
        self.token_counter = token_counter
        self.ttl_seconds = ttl_seconds
        self.max_bundles = max_bundles
        self._releases = {}
        self._versions = {}
        self._bundles = OrderedDict()
        self._cache = OrderedDict()
        self._lock = threading.RLock()

    def register(self, model_id, release_version, document, *, publication,
                 context_sha256=None):
        """Register verified publication evidence supplied by a trusted adapter."""
        if (not model_id or not release_version or publication.get("status") != "published"
                or not publication.get("source") or not publication.get("reference")):
            raise RetrievalError("A published release and its provenance are required")
        sha = digest(document)
        release_id = digest([model_id, release_version, sha, context_sha256])
        key = (model_id, release_id)
        version_key = (model_id, release_version)
        with self._lock:
            if version_key in self._versions and self._versions[version_key] != release_id:
                raise RetrievalError("A release version cannot be overwritten")
            if key in self._releases:
                existing = self._releases[key][0]
                if existing["context_sha256"] != context_sha256:
                    raise RetrievalError("Conflicting context provenance for this release")
                return copy.deepcopy(existing)
            index = SemanticIndex(document)
            manifest = {
                "contract_version": "helios.semantic-release.v1",
                "model_id": model_id, "release_version": release_version,
                "specification_version": document.get("version"),
                "document_sha256": sha, "context_sha256": context_sha256,
                "release_id": release_id,
                "publication": copy.deepcopy(publication),
            }
            self._releases[key] = (manifest, index)
            self._versions[version_key] = release_id
            return copy.deepcopy(manifest)

    def inventory(self, scope):
        scope.fingerprint()
        with self._lock:
            return [copy.deepcopy(self._releases[(model, sha)][0])
                    for model, sha in scope.releases.items()
                    if (model, sha) in self._releases]

    def _selected(self, scope, model):
        if model not in scope.releases:
            raise RetrievalError("Model is outside the adopted release scope")
        value = self._releases.get((model, scope.releases[model]))
        if value is None:
            raise RetrievalError("Adopted release is unavailable; refresh the application binding")
        return value

    def discover(self, question, scope, limit=5):
        """Search only explicitly adopted models; no unreviewed fallback."""
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise RetrievalError("Supply a question between 1 and 4000 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise RetrievalError("Discovery limit must be between 1 and 20")
        scope.fingerprint()
        found = []
        with self._lock:
            for model in scope.releases:
                manifest, index = self._selected(scope, model)
                matches = index.search(question, allowed_fields=scope.allowed_fields[model], limit=3)
                if matches:
                    found.append({"model_id": model, "release_version": manifest["release_version"],
                                  "matches": matches})
        # Scores from independent BM25 corpora are not comparable. Never auto-select
        # a model by comparing these scores across releases.
        return found[:limit]

    def resolve_context(self, question, scope, model=None, metric=None, required_fields=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise RetrievalError("Supply a question between 1 and 4000 characters")
        fingerprint = scope.fingerprint()
        with self._lock:
            if model is None:
                if len(scope.releases) == 1:
                    model = next(iter(scope.releases))
                else:
                    choices = self.discover(question, scope)
                    if len(choices) != 1:
                        return {"status": "needs_clarification", "question":
                                "Select a published model matching the requested business meaning.",
                                "models": choices}
                    model = choices[0]["model_id"]
            manifest, index = self._selected(scope, model)
            cache_key = digest([question, model, metric, required_fields, fingerprint])
            now = time.monotonic()
            cached_id = self._cache.get(cache_key)
            cached = self._bundles.get(cached_id)
            if cached and cached["expires"] > now:
                self._bundles.move_to_end(cached_id)
                result = copy.deepcopy(cached["response"])
                result["evidence"]["cache_hit"] = True
                return result
            try:
                resolved = index.bundle(question, allowed_fields=scope.allowed_fields[model],
                                        metric=metric, token_counter=self.token_counter, required_fields=required_fields)
            except Clarification as exc:
                return {"status": "needs_clarification", "question": str(exc)}
            bundle = resolved["document"]
            bundle_id = secrets.token_urlsafe(24)
            evidence = copy.deepcopy(resolved["evidence"])
            evidence.update({"policy_revision": scope.policy_revision,
                             "bundle_sha256": digest(bundle), "cache_hit": False,
                             "expires_in_seconds": self.ttl_seconds})
            response = {"status": "ready", "bundle_id": bundle_id, "bundle": bundle,
                        "evidence": evidence, "manifest": copy.deepcopy(manifest)}
            self._bundles[bundle_id] = {"scope": fingerprint, "model": model,
                "expires": now + self.ttl_seconds, "response": copy.deepcopy(response)}
            self._cache[cache_key] = bundle_id
            while len(self._bundles) > self.max_bundles:
                self._bundles.popitem(last=False)
            while len(self._cache) > self.max_bundles:
                self._cache.popitem(last=False)
            return response

    def validate_request(self, bundle_id, scope, request, model=None):
        """Recheck scope and return the only model permitted for compilation."""
        with self._lock:
            saved = self._bundles.get(bundle_id)
            if (saved is None or saved["expires"] <= time.monotonic()
                    or saved["scope"] != scope.fingerprint()
                    or (model is not None and saved["model"] != model)):
                raise RetrievalError("Bundle is missing, expired or outside the current scope; retrieve again")
            self._selected(scope, saved["model"])
            document = copy.deepcopy(saved["response"]["bundle"])
        try:
            if set(request) - {"metrics", "measures", "dimensions", "filters", "via", "order_by", "limit", "dataset"}:
                raise ValueError("Unknown request attribute")
            bounded = SemanticModel(document)
            typed = SemanticRequest.from_dict(request)
            if typed.dataset and typed.dataset not in bounded.datasets:
                raise ValueError("Unavailable dataset")
            if any(name not in bounded.relationships for name in typed.via.values()):
                raise ValueError("Unavailable relationship")
            for ref in typed.order_by:
                name = ref.lstrip("-")
                try:
                    bounded.metric(name)
                except KeyError:
                    bounded.field(name)
            Compiler(bounded).plan(typed)
            return bounded
        except Exception:
            raise RetrievalError("Request references invalid definitions or definitions outside the bundle") from None


def export_studio_release(workspace, version):
    """Bridge Studio to consumer files without exposing its SQLite database."""
    from helios_core.demo.builder_artifacts import BuilderArtifacts
    release = workspace.release(version)
    # Require actual publication, including for legacy contexts accepted by the UI.
    with workspace.connection() as connection:
        row = connection.execute(
            "SELECT context_sha256, published_at FROM publications WHERE version=?", (version,)
        ).fetchone()
    if row is None or row[0] != release["context_sha256"]:
        raise RetrievalError("Publish this reviewed version before consumer export")
    document_sha256 = digest(release["document"])
    return {
        "manifest": {
            "contract_version": "helios.semantic-release.v1",
            "model_id": release["pack_id"], "release_version": release["version"],
            "specification_version": release["document"].get("version"),
            "document_sha256": document_sha256,
            "context_sha256": release["context_sha256"],
            "release_id": digest([release["pack_id"], release["version"],
                                  document_sha256, release["context_sha256"]]),
            "publication": {"status": "published", "source": "helios-local-studio",
                            "reference": version, "published_at": row[1]},
            "source_snapshot_sha256": release["snapshot_sha256"],
        },
        "document": copy.deepcopy(release["document"]),
        "context": release,
        "artifacts": copy.deepcopy(release["artifacts"]) if "artifacts" in release else BuilderArtifacts(workspace).bundle(
            release["definition"], release["document"], version,
            release.get("item_review", []),
        ),
    }
