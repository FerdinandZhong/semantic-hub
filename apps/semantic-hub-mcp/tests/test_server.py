import asyncio
import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from semantic_hub_mcp.server import HubClient, create_server


def run(coro):
    return asyncio.run(coro)


def test_sdk_discovery_and_read_only_contract():
    server = create_server(HubClient("https://hub.example", "secret"))
    tools = run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "hub_status", "list_semantic_models", "get_semantic_model", "list_model_versions",
        "get_model_version", "search_semantics", "resolve_semantic_context", "inspect_metric_coverage",
        "get_model_lineage", "get_published_documents", "compile_semantic_query", "query_sample_data",
    }
    assert all(tool.annotations.read_only_hint for tool in tools)
    search = next(tool for tool in tools if tool.name == "search_semantics")
    assert search.input_schema["properties"]["limit"]["maximum"] == 20


def test_sdk_dispatch_forwards_auth_and_pinned_context():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "bundle_id": "bundle-a"})

    server = create_server(HubClient("https://hub.example", "secret", httpx.MockTransport(handler)))
    result = run(server.call_tool("resolve_semantic_context", {
        "model_id": "sales", "version": "v1", "context_sha256": "abc", "query": "revenue",
    }))
    assert not result.is_error
    request = seen[0]
    assert request.url.path == "/api/semantic-hub/v1/resolve"
    assert request.headers["authorization"] == "Bearer secret"
    assert json.loads(request.content) == {"model_id": "sales", "version": "v1", "context_sha256": "abc", "query": "revenue"}


def test_invalid_query_limit_does_not_call_http():
    seen = []
    server = create_server(HubClient("https://hub.example", "secret", httpx.MockTransport(lambda request: seen.append(request))))
    with pytest.raises(ToolError):
        run(server.call_tool("search_semantics", {"query": "revenue", "limit": 21}))
    assert seen == []


def test_remote_errors_preserve_machine_details():
    client = HubClient("https://hub.example", "secret", httpx.MockTransport(lambda request: httpx.Response(409, json={"error": {"code": "context_mismatch"}})))
    result = run(client.request("GET", "/capabilities"))
    assert result["ok"] is False
    assert result["error"]["status"] == 409
    assert result["error"]["details"]["error"]["code"] == "context_mismatch"


def test_configuration_and_connectivity_never_report_health():
    assert run(HubClient("", "").request("GET", "/capabilities"))["error"]["code"] == "adapter_configuration_error"

    def handler(request):
        raise httpx.ConnectError("secret internal address", request=request)

    result = run(HubClient("https://hub.example", "secret", httpx.MockTransport(handler)).request("GET", "/capabilities"))
    assert result["error"]["code"] == "hub_unreachable"
    assert "secret" not in json.dumps(result)


def test_paths_and_context_query_parameters():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    server = create_server(HubClient("https://hub.example", "secret", httpx.MockTransport(handler)))
    run(server.call_tool("get_model_lineage", {"model_id": "sales model", "version": "v1", "context_sha256": "abc"}))
    assert seen[0].url.raw_path == b"/api/semantic-hub/v1/models/sales%20model/versions/v1/graph?context_sha256=abc"


@pytest.mark.parametrize("changes", [
    {"dimensions": ["field"] * 4},
    {"filters": [{"field": "period", "op": "=", "value": 2024}] * 21},
    {"filters": [{"field": "period", "op": "execute", "value": "sql"}]},
    {"filters": [{"field": "period", "op": "in", "value": list(range(101))}]},
])
def test_typed_query_bounds_reject_before_http(changes):
    server = create_server(HubClient("https://hub.example", "secret"))
    query = {"model_id": "pharma", "version": "v1", "context_sha256": "abc", "bundle_id": "b", "question": "sales", "metrics": ["sales"], **changes}
    with pytest.raises(ToolError):
        run(server.call_tool("compile_semantic_query", query))


def test_typed_filters_serialize_as_http_objects():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"status": "ready"})

    server = create_server(HubClient("https://hub.example", "secret", httpx.MockTransport(handler)))
    run(server.call_tool("compile_semantic_query", {"model_id": "pharma", "version": "v1", "context_sha256": "abc", "bundle_id": "b", "question": "sales", "metrics": ["sales"], "filters": [{"field": "period", "op": "=", "value": 2024}]}))
    assert json.loads(seen[0].content)["filters"] == [{"field": "period", "op": "=", "value": 2024}]


def test_local_api_without_token_omits_authorization():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"service": "Semantic Hub"})
    result = run(HubClient("http://127.0.0.1:8096", "", httpx.MockTransport(handler)).request("GET", "/capabilities"))
    assert result["service"] == "Semantic Hub"
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize('explicit,expected', [('', 'cai-test-key'), ('standalone-key', 'standalone-key')])
def test_cai_ingress_credential_fallback(monkeypatch, explicit, expected):
    import semantic_hub_mcp.server as module
    captured = []
    original = module.HubClient
    def capture(url, token):
        captured.append((url, token))
        return original(url, token)
    monkeypatch.setattr(module, 'HubClient', capture)
    monkeypatch.setenv('SEMANTIC_HUB_URL', 'https://hub.example')
    monkeypatch.setenv('CDSW_APIV2_KEY', 'cai-test-key')
    monkeypatch.setenv('SEMANTIC_HUB_API_TOKEN', explicit)
    create_server()
    assert captured == [('https://hub.example', expected)]
