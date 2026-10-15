"""Consumer contracts and agent scope binding, without live services."""
from dataclasses import replace

import pytest

from helios_core.retrieval.service import (
    RetrievalError, RetrievalService, Scope, digest, export_studio_release,
)


def document():
    def expr(sql):
        return {"dialects": [{"dialect": "ANSI_SQL", "expression": sql}]}
    return {"name": "sales", "version": "0.1", "datasets": [
        {"name": "sales", "source": "warehouse.sales", "fields": [
            {"name": "amount", "expression": expr("amount"), "datatype": "Decimal"},
            {"name": "secret", "expression": expr("secret"), "datatype": "Decimal"},
        ]}], "metrics": [{"name": "revenue", "expression": expr("SUM(sales.amount)")}],
    }


def registered(service=None):
    service = service or RetrievalService()
    manifest = service.register("sales", "v1", document(),
        publication={"status": "published", "source": "test", "reference": "release-v1"})
    scope = Scope("alice", "policy-v1", {"sales": manifest["release_id"]},
                  {"sales": frozenset({"sales.amount"})}, "session-1/query")
    return service, scope, manifest


def test_bundle_compiles_only_retrieved_definitions():
    service, scope, manifest = registered()
    resolved = service.resolve_context("revenue", scope)
    assert resolved["status"] == "ready"
    model = service.validate_request(resolved["bundle_id"], scope, {"metrics": ["revenue"]})
    assert set(model.datasets["sales"].fields) == {"amount"}
    assert manifest["document_sha256"] == digest(document())
    for bad in [{"measures": ["sales.secret"]}, {"metrics": ["revenue"], "via": {"x": "hidden"}},
                {"metrics": ["revenue"], "order_by": ["secret"]},
                {"metrics": ["revenue"], "sql": "SELECT 1"}]:
        with pytest.raises(RetrievalError, match="outside"):
            service.validate_request(resolved["bundle_id"], scope, bad)


def test_cache_is_immutable_and_scoped():
    service, scope, _ = registered()
    first = service.resolve_context("revenue", scope)
    first["bundle"]["datasets"].clear()
    second = service.resolve_context("revenue", scope)
    assert second["evidence"]["cache_hit"]
    assert second["bundle"]["datasets"]
    for other in [replace(scope, principal_id="bob"), replace(scope, policy_revision="p2"),
                  replace(scope, context="session-2/query"),
                  replace(scope, allowed_fields={"sales": frozenset()})]:
        with pytest.raises(RetrievalError, match="scope"):
            service.validate_request(second["bundle_id"], other, {"metrics": ["revenue"]})
    assert service.resolve_context("revenue", replace(scope, allowed_fields={"sales": frozenset()}))["status"] == "needs_clarification"


def test_expired_evicted_and_wrong_model_bundles_rejected(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("helios_core.retrieval.service.time.monotonic", lambda: clock[0])
    service, scope, _ = registered(RetrievalService(ttl_seconds=5, max_bundles=1))
    first = service.resolve_context("revenue", scope)
    with pytest.raises(RetrievalError):
        service.validate_request(first["bundle_id"], scope, {"metrics": ["revenue"]}, model="other")
    clock[0] = 16
    with pytest.raises(RetrievalError, match="expired"):
        service.validate_request(first["bundle_id"], scope, {"metrics": ["revenue"]})
    second = service.resolve_context("revenue", scope)
    assert second["bundle_id"] != first["bundle_id"]
    with pytest.raises(RetrievalError):
        service.validate_request(first["bundle_id"], scope, {"metrics": ["revenue"]})


def test_publication_and_release_pins():
    service, scope, manifest = registered()
    with pytest.raises(RetrievalError, match="published"):
        service.register("x", "v1", document(), publication={"status": "draft"})
    changed = document()
    changed["description"] = "Updated"
    with pytest.raises(RetrievalError, match="overwritten"):
        service.register("sales", "v1", changed, publication=manifest["publication"])
    next_manifest = service.register("sales", "v2", document(), publication=manifest["publication"], context_sha256="newcontext")
    assert manifest["document_sha256"] == next_manifest["document_sha256"]
    assert manifest["release_id"] != next_manifest["release_id"]
    resolved = service.resolve_context("revenue", scope)
    changed_scope = replace(scope, releases={"sales": next_manifest["release_id"]})
    with pytest.raises(RetrievalError):
        service.validate_request(resolved["bundle_id"], changed_scope, {"metrics": ["revenue"]})


def test_discovery_clarifies_across_models_and_does_not_return_denied_models():
    service, scope, manifest = registered()
    other = service.register("other", "v1", document(), publication=manifest["publication"])
    both = replace(scope, releases=scope.releases | {"other": other["release_id"]},
                   allowed_fields=scope.allowed_fields | {"other": None})
    result = service.resolve_context("revenue", both)
    assert result["status"] == "needs_clarification"
    assert {m["model_id"] for m in result["models"]} == {"sales", "other"}
    assert [m["model_id"] for m in service.discover("revenue", scope)] == ["sales"]
    with pytest.raises(RetrievalError):
        service.resolve_context("revenue", scope, model="other")


def test_studio_export_requires_publication_and_preserves_both_hashes(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.helios.console.demo import demo_router
    from test_demo_context import pack, validated, approve_items, review_request, publish
    from helios_core.demo.runtime import DemoRuntime
    runtime = DemoRuntime(pack(), tmp_path)
    try:
        app = FastAPI()
        app.state.demo_runtime = runtime
        app.include_router(demo_router)
        client = TestClient(app)
        validated(runtime)
        approve_items(runtime)
        runtime.workspace.review(review_request(runtime))
        with pytest.raises(RetrievalError, match="Publish"):
            export_studio_release(runtime.workspace, "v1")
        assert client.get("/demo/api/context/export", params={"version": "v1"}).status_code == 409
        publish(runtime)
        exported = export_studio_release(runtime.workspace, "v1")
        response = client.get("/demo/api/context/export", params={"version": "v1"})
        assert response.status_code == 200
        assert response.json() == exported
        assert exported["manifest"]["document_sha256"] == digest(exported["document"])
        assert exported["manifest"]["context_sha256"] == exported["context"]["context_sha256"]
        assert exported["manifest"]["document_sha256"] != exported["manifest"]["context_sha256"]
        assert exported["context"]["definition"]["metrics"]
        service = RetrievalService()
        manifest = exported["manifest"]
        registered_manifest = service.register(manifest["model_id"], manifest["release_version"], exported["document"],
                                              publication=manifest["publication"], context_sha256=manifest["context_sha256"])
        assert registered_manifest["release_id"] == manifest["release_id"]
    finally:
        runtime.close()


def test_explicit_fields_keep_scope_and_separate_cache_entries():
    service, scope, _ = registered()
    minimal = service.resolve_context('revenue secret', scope, metric='revenue', required_fields=[])
    assert minimal['status'] == 'ready'
    assert [f['name'] for f in minimal['bundle']['datasets'][0]['fields']] == ['amount']
    denied = service.resolve_context('revenue', scope, metric='revenue', required_fields=['sales.secret'])
    assert denied['status'] == 'needs_clarification'
    unknown = service.resolve_context('revenue', scope, metric='revenue', required_fields=['sales.missing'])
    assert unknown['status'] == 'needs_clarification'
    broader = replace(scope, allowed_fields={'sales': None})
    explicit = service.resolve_context('revenue', broader, metric='revenue', required_fields=['sales.secret'])
    assert {f['name'] for f in explicit['bundle']['datasets'][0]['fields']} == {'amount', 'secret'}
    assert explicit['bundle_id'] != minimal['bundle_id']
