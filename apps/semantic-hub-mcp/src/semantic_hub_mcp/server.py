"""MCP tools backed exclusively by the remote Semantic Hub HTTP API."""

from __future__ import annotations

import argparse
import os
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlsplit

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

SearchLimit = Annotated[int, Field(ge=1, le=20)]
QueryLimit = Annotated[int, Field(ge=1, le=100)]
PageLimit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0)]
FieldName = Annotated[str, Field(min_length=1, max_length=260)]
OneMetric = Annotated[list[FieldName], Field(min_length=1, max_length=1)]
Dimensions = Annotated[list[FieldName], Field(max_length=3)]
RequiredFields = Annotated[list[FieldName], Field(max_length=50)]
Scalar = Annotated[str, Field(max_length=2000)] | int | float | bool
FilterValues = Annotated[list[Scalar], Field(max_length=100)]


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: FieldName
    op: Literal["=", "!=", "<>", ">", ">=", "<", "<=", "in", "not in", "between", "like", "is null", "is not null"]
    value: Scalar | FilterValues | None = None


Filters = Annotated[list[QueryFilter], Field(max_length=20)]


def payload(values: dict[str, Any]) -> dict[str, Any]:
    """Convert validated filter objects without forwarding closure variables."""
    return {
        k: [item.model_dump() if isinstance(item, BaseModel) else item for item in v] if isinstance(v, list) else v
        for k, v in values.items() if k != "hub" and v is not None
    }


class HubClient:
    def __init__(self, url: str, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self.url = url.rstrip("/")
        self.token = token
        self.transport = transport

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            return {"ok": False, "error": {"code": "adapter_configuration_error", "message": "Set SEMANTIC_HUB_URL to a server origin."}}
        try:
            async with httpx.AsyncClient(timeout=30, transport=self.transport, follow_redirects=False) as client:
                response = await client.request(method, self.url + "/api/semantic-hub/v1" + path, headers={"Authorization": "Bearer " + self.token} if self.token else {}, **kwargs)
            try:
                body = response.json()
            except ValueError:
                body = None
            if not response.is_success:
                return {"ok": False, "error": {"code": "hub_http_error", "status": response.status_code, "message": "Semantic Hub rejected the request.", "details": body}}
            if not isinstance(body, dict):
                return {"ok": False, "error": {"code": "invalid_hub_response", "message": "Semantic Hub did not return a JSON object."}}
            return body
        except httpx.TimeoutException:
            return {"ok": False, "error": {"code": "hub_timeout", "message": "Semantic Hub request timed out."}}
        except httpx.RequestError:
            return {"ok": False, "error": {"code": "hub_unreachable", "message": "Semantic Hub could not be reached."}}


def create_server(client: HubClient | None = None) -> MCPServer:
    hub = client or HubClient(os.getenv("SEMANTIC_HUB_URL", ""),
                             os.getenv("SEMANTIC_HUB_API_TOKEN") or os.getenv("CDSW_APIV2_KEY", ""))
    server = MCPServer("Semantic Hub", instructions="Read hub_status first. Use published versions and preserve model_id, version, context_sha256, and bundle_id from server responses. Inspect temporal coverage before compilation. The agent must separately check population, geography, units, and aggregation. Compilation returns DuckDB SQL for local validation. External agents may use published definitions with their own engine tools. query_sample_data only executes bounded local sample data when the hub enables it. No write or publication tools exist.")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)

    def version_path(model_id: str, version: str) -> str:
        return f"/models/{quote(model_id, safe='')}/versions/{quote(version, safe='')}"

    def context_params(context_sha256: str | None) -> dict[str, str]:
        return {"context_sha256": context_sha256} if context_sha256 else {}

    @server.tool(annotations=read_only)
    async def hub_status() -> dict[str, Any]:
        """Read live remote capabilities, execution availability, and API status. Never infer health from adapter availability."""
        return await hub.request("GET", "/capabilities")

    @server.tool(annotations=read_only)
    async def list_semantic_models(q: str = "", limit: PageLimit = 20, offset: Offset = 0) -> dict[str, Any]:
        """List published semantic models with bounded pagination and optional text filtering."""
        return await hub.request("GET", "/models", params={"q": q, "limit": limit, "offset": offset})

    @server.tool(annotations=read_only)
    async def get_semantic_model(model_id: str) -> dict[str, Any]:
        """Read one semantic model's published metadata."""
        return await hub.request("GET", f"/models/{quote(model_id, safe='')}")

    @server.tool(annotations=read_only)
    async def list_model_versions(model_id: str) -> dict[str, Any]:
        """List published versions and immutable context hashes for a model."""
        return await hub.request("GET", f"/models/{quote(model_id, safe='')}/versions")

    @server.tool(annotations=read_only)
    async def get_model_version(model_id: str, version: str, context_sha256: str | None = None) -> dict[str, Any]:
        """Read a published version. Supply its context hash to detect changed context."""
        return await hub.request("GET", version_path(model_id, version), params=context_params(context_sha256))

    @server.tool(annotations=read_only)
    async def search_semantics(query: str, model_id: str | None = None, version: str | None = None, context_sha256: str | None = None, mode: Literal["keyword", "embedding"] = "keyword", limit: SearchLimit = 10) -> dict[str, Any]:
        """Search published semantics. Check hub_status before requesting embedding search."""
        return await hub.request("POST", "/search", json=payload(locals()))

    @server.tool(annotations=read_only)
    async def resolve_semantic_context(model_id: str, version: str, context_sha256: str, query: str, metric: str | None = None, required_fields: RequiredFields | None = None) -> dict[str, Any]:
        """Resolve a question to a published semantic bundle; preserve the returned bundle_id."""
        return await hub.request("POST", "/resolve", json=payload(locals()))

    @server.tool(annotations=read_only)
    async def inspect_metric_coverage(model_id: str, version: str, context_sha256: str, metric: str, question: str) -> dict[str, Any]:
        """Check temporal coverage before compilation. The agent must separately check population, geography, units, and aggregation."""
        return await hub.request("POST", "/coverage", json=payload(locals()))

    @server.tool(annotations=read_only)
    async def get_model_lineage(model_id: str, version: str, context_sha256: str | None = None) -> dict[str, Any]:
        """Read published metric, field, table, and relationship lineage."""
        return await hub.request("GET", version_path(model_id, version) + "/graph", params=context_params(context_sha256))

    @server.tool(annotations=read_only)
    async def get_published_documents(model_id: str, version: str, context_sha256: str | None = None) -> dict[str, Any]:
        """Read documents attached to the selected published model version."""
        return await hub.request("GET", version_path(model_id, version) + "/documents", params=context_params(context_sha256))

    @server.tool(annotations=read_only)
    async def compile_semantic_query(model_id: str, version: str, context_sha256: str, bundle_id: str, question: str, metrics: OneMetric, dimensions: Dimensions | None = None, filters: Filters | None = None, limit: QueryLimit = 100) -> dict[str, Any]:
        """Compile one metric into bounded DuckDB SQL for local validation. External agents may use published definitions with their own engine tools."""
        return await hub.request("POST", "/compile", json=payload(locals()))

    @server.tool(annotations=read_only)
    async def query_sample_data(model_id: str, version: str, context_sha256: str, bundle_id: str, question: str, metrics: OneMetric, dimensions: Dimensions | None = None, filters: Filters | None = None, limit: QueryLimit = 100) -> dict[str, Any]:
        """Run a bounded query against demo sample data only. Requires sample execution capability from hub_status."""
        return await hub.request("POST", "/query", json=payload(locals()))

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
