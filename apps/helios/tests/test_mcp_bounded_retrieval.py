"""MCP retrieval adapters preserve trusted caller and bounded query state."""
from types import SimpleNamespace

import pytest

from apps.helios.mcp import server
from helios_core.identity import Principal, PrincipalKind
from helios_core.ossie import SemanticModel


@pytest.fixture
def trusted_adapter(monkeypatch):
    caller = server.MCPCaller(Principal("test", "alice", PrincipalKind.HUMAN), "sales", "acme", session_id="session-a")
    model = SimpleNamespace(id="sales", organization_id="acme")
    token = server._caller_context.set(caller)
    monkeypatch.setattr(server, "_authorized_tool", lambda action, requested: (caller, model, None))
    monkeypatch.setattr(server.metadata_repository, "grants_for_principal", lambda principal: [])
    full = SemanticModel({"name": "sales", "datasets": [], "metrics": [], "relationships": []})
    monkeypatch.setattr(server.store, "load", lambda name: ({"name": name, "status": "published", "path": "/published/sales.json"}, full))
    yield caller, model, full
    server._caller_context.reset(token)


def test_missing_bundle_fails_before_compilation_and_execution(trusted_adapter, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("query dependencies must not run without a bundle")
    monkeypatch.setattr(server, "_compile_semantic", forbidden)
    monkeypatch.setattr(server, "impala_config", forbidden)
    assert server.compile_query([])["error"] == "retrieval_bundle_required"
    assert server.run_query([])["error"] == "retrieval_bundle_required"


def test_compile_uses_bounded_model_and_trusted_scope(trusted_adapter, monkeypatch):
    caller, authorized, full = trusted_adapter
    bounded = SemanticModel({"name": "bounded", "datasets": [], "metrics": [], "relationships": []})
    captured = {}
    class Retrieval:
        def register(self, model_id, release, document, **kwargs):
            assert kwargs["publication"]["status"] == "published"
            return {"release_id": "release-hash"}
        def validate_request(self, bundle_id, scope, request, model=None):
            captured.update(bundle_id=bundle_id, scope=scope, request=request)
            assert model == authorized.id
            return bounded
    monkeypatch.setattr(server, "retrieval_service", Retrieval())
    def compile_model(model, *args):
        assert model is bounded
        return {"sql": "SELECT 1"}, set()
    monkeypatch.setattr(server, "_compile_semantic", compile_model)
    assert server.compile_query([], bundle_id="bundle-a") == {"sql": "SELECT 1"}
    assert captured["scope"].principal_id == caller.principal.id
    assert captured["scope"].releases == {"sales": "release-hash"}
    assert captured["scope"].allowed_fields == {"sales": None}
    assert "session-a" in captured["scope"].context


def test_invalid_bundle_never_reaches_warehouse(trusted_adapter, monkeypatch):
    def invalid(*args):
        raise ValueError("expired bundle")
    monkeypatch.setattr(server, "_bounded_model", invalid)
    monkeypatch.setattr(server, "impala_config", lambda: pytest.fail("warehouse must not run"))
    assert server.run_query([], bundle_id="expired")["error"] == "retrieval_bundle_invalid"


def test_proposal_fallback_is_disabled(monkeypatch):
    monkeypatch.setattr(server.artifact_store, "published_model_ids", lambda: [])
    monkeypatch.setattr(server.runstore, "list_runs", lambda: pytest.fail("unreviewed proposals must not be loaded"))
    assert server.ModelStore().sources() == []


def test_real_bundle_roundtrip_preserves_authorization(trusted_adapter, monkeypatch):
    from helios_core.retrieval.service import RetrievalService
    document = {
        "name": "Sales", "datasets": [{"name": "orders", "source": "warehouse.orders", "fields": [
            {"name": "amount", "datatype": "Decimal", "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "amount"}]}, "dimension": {"is_time": False}}
        ]}], "relationships": [], "metrics": [{"name": "Revenue", "datatype": "Decimal", "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": "SUM(orders.amount)"}]}}]
    }
    monkeypatch.setattr(server.store, "load", lambda name: ({"name": name, "status": "published", "path": "/published/sales.json"}, SemanticModel(document)))
    monkeypatch.setattr(server, "retrieval_service", RetrievalService())
    resolved = server.resolve_context("Revenue")
    assert resolved["status"] == "ready"
    compiled = server.compile_query(["Revenue"], bundle_id=resolved["bundle_id"])
    assert "SUM" in compiled["sql"]
    # A different trusted session cannot reuse the same bundle.
    caller = trusted_adapter[0]
    token = server._caller_context.set(server.MCPCaller(caller.principal, "sales", "acme", session_id="session-b"))
    monkeypatch.setattr(server, "_authorized_tool", lambda action, requested: (server._caller_context.get(), trusted_adapter[1], None))
    try:
        assert server.compile_query(["Revenue"], bundle_id=resolved["bundle_id"])["error"] == "retrieval_bundle_invalid"
    finally:
        server._caller_context.reset(token)


def test_startup_warm_indexes_isolates_invalid_models(trusted_adapter, monkeypatch):
    full = trusted_adapter[2]
    monkeypatch.setattr(server.store, "sources", lambda: [{"name": "sales"}, {"name": "invalid"}])
    def load(name):
        assert server._caller_context.get() is None
        if name == "invalid":
            raise ValueError("invalid metadata")
        return {"name": name, "status": "published", "path": "/published/sales.json"}, full
    monkeypatch.setattr(server.store, "load", load)
    calls = []
    class Retrieval:
        def register(self, *args, **kwargs):
            calls.append(args)
            return {"release_id": "sales-release"}
    monkeypatch.setattr(server, "retrieval_service", Retrieval())
    assert server.prepare_published_indexes() == {"warm": 1, "failed": 1}
    assert server.prepare_published_indexes() == {"warm": 1, "failed": 1}
    assert len(calls) == 1
    assert server._caller_context.get() is trusted_adapter[0]


def test_discovery_filters_models_before_loading_or_ranking(trusted_adapter, monkeypatch):
    caller, model, full = trusted_adapter
    monkeypatch.setattr(server.store, "sources", lambda: [{"name": "sales"}, {"name": "finance"}])
    def authorize(action, requested):
        if requested == "finance":
            return None, None, {"error": "authorization_denied"}
        return caller, model, None
    monkeypatch.setattr(server, "_authorized_tool", authorize)
    def load(name):
        assert name == "sales"
        return {"name": name, "status": "published", "path": "/published/sales.json"}, full
    monkeypatch.setattr(server.store, "load", load)
    class Retrieval:
        def register(self, *args, **kwargs):
            return {"release_id": "sales-release"}
        def discover(self, question, scope, limit):
            assert scope.releases == {"sales": "sales-release"}
            assert scope.principal_id == caller.principal.id
            return [{"model_id": "sales"}]
    monkeypatch.setattr(server, "retrieval_service", Retrieval())
    assert server.discover_models("Revenue") == {"models": [{"model_id": "sales"}]}
