# Semantic Hub MCP adapter

This package exposes twelve read-only MCP tools through the real MCP Python SDK 2.x.
The adapter calls the Semantic Hub HTTP API. It never reads the local demo state directory.
Stdio transport supports a CAI Agent Studio MCP subprocess configuration.

## Install from GitHub in Agent Studio

Use the same `uvx` subprocess pattern as the AML application.
The execution host needs Python 3.11+, Git, uv, and network access to GitHub and the package registry.
The host installs only the MCP adapter and its dependencies.
It connects to a separately running Semantic Hub consumer API.

Import [agent-studio.mcp.json](agent-studio.mcp.json), then set the consumer API URL. The local demo requires no consumer token.

```json
{
  "mcpServers": {
    "semantic-hub": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/FerdinandZhong/semantic-hub.git@5c0a376966ac838e27961b99e6fd839781a6f29b#subdirectory=apps/semantic-hub-mcp",
        "semantic-hub-mcp"
      ],
      "env": {
        "SEMANTIC_HUB_URL": "http://127.0.0.1:8096"
      }
    }
  }
}
```

Set the URL to the consumer API origin, without `/api/semantic-hub/v1` or `/docs`.
The default API port is 8086; this workspace uses 8096.
Use a reachable HTTPS URL for CAI. Its localhost is not your laptop.
The adapter uses stdio and does not host an HTTP MCP endpoint.

The supplied configuration pins the verified commit. Update it only after testing a newer commit.
A moving branch can use cached code. Run `uvx --refresh --from '<Git URL>' semantic-hub-mcp` to refresh it.
Do not place tokens in the Git URL, command arguments, or agent prompts.

### Local development

```sh
python -m pip install -e ./apps/semantic-hub-mcp
export SEMANTIC_HUB_URL=http://127.0.0.1:8096
semantic-hub-mcp
```

The adapter writes protocol messages to stdout and diagnostics to stderr.

## Tools and HTTP contract

All paths below start with `/api/semantic-hub/v1`.
The local demo sends no Authorization header.
If a hosted deployment requires a bearer, set optional `SEMANTIC_HUB_API_TOKEN`.
CAI `cdsw_v2_key` validation is planned for AMP packaging and is not implemented.

| MCP tool | HTTP request |
| --- | --- |
| `hub_status` | GET `/capabilities` |
| `list_semantic_models` | GET `/models?q=&limit=&offset=` |
| `get_semantic_model` | GET `/models/{model_id}` |
| `list_model_versions` | GET `/models/{model_id}/versions` |
| `get_model_version` | GET `/models/{model_id}/versions/{version}` |
| `get_model_lineage` | GET `/models/{model_id}/versions/{version}/graph` |
| `get_published_documents` | GET `/models/{model_id}/versions/{version}/documents` |
| `search_semantics` | POST `/search` |
| `resolve_semantic_context` | POST `/resolve` |
| `inspect_metric_coverage` | POST `/coverage` |
| `compile_semantic_query` | POST `/compile` |
| `query_sample_data` | POST `/query` |

Version, lineage, and document reads accept an optional `context_sha256` query parameter.
Supply the hash whenever available. Search accepts optional model, version, and hash filters.
Search defaults to `mode="keyword"` and limits results to 20.
Embedding search depends on the live capabilities response.
Model listing defaults to 20 entries and supports offsets; its maximum page size is 100.

Resolve requires `model_id`, `version`, `context_sha256`, and `query`.
It accepts an optional `metric` and `required_fields` list.
Coverage requires those three context identifiers, plus `metric` and `question`.
Compile and sample query require all three context identifiers, `bundle_id`, `question`, and a one-element `metrics` list.
Both accept optional `dimensions`, `filters`, and `limit` up to 100.
Each filter uses the backend's `field`, `op`, and `value` contract.
The adapter accepts up to three dimensions and twenty typed filters.
Filter lists contain at most 100 scalar values. Resolve accepts up to fifty required fields.
The MCP SDK advertises all argument schemas through tool discovery.

## Consumer workflow

1. Call `hub_status` to read current search and execution capabilities.
2. Discover a published model and version.
3. Preserve its `model_id`, `version`, and `context_sha256`.
4. Resolve the question and preserve the returned `bundle_id`.
5. Inspect temporal coverage. Separately check population, geography, units, aggregation, and missing fields.
6. Compile one metric into DuckDB SQL for local validation.
7. Use `query_sample_data` only when the hub enables local sample execution.

```text
Agent Studio -> MCP adapter -> Semantic Hub HTTP API -> Published catalog
     |                               |
     +-> Your engine tools           +-> DuckDB SQL / local sample validation
```

Sample execution can return `no_data` or `unsupported_scope` instead of rows.
Treat these statuses as results requiring review. Do not invent query results.
External agents may use published definitions with their own engine tools.
The compile endpoint validates DuckDB SQL only. It does not validate SQL for other engines.
No tool creates, edits, publishes, or deletes models.

Remote JSON responses pass through unchanged on successful HTTP requests.
HTTP errors return `ok: false` and an error with status and upstream JSON details.
Adapter configuration, connectivity, timeout, and malformed response failures have distinct machine codes.
Adapter startup never claims that the remote hub is healthy.

## Verify

```sh
python -m pip install -e './apps/semantic-hub-mcp[test]'
python -m pytest apps/semantic-hub-mcp/tests -q
```

Tests use mocked HTTP and real SDK discovery and dispatch.
They cover authentication forwarding, pinned context, bounds, URL encoding, and error behavior.
The stdio integration test starts a real MCP subprocess and a temporary localhost HTTP server.
Tests do not establish a live CAI deployment or remote hub connectivity.

Run the optional live check against an existing dedicated consumer API:

```sh
python apps/semantic-hub-mcp/scripts/check_live.py \
  --url http://127.0.0.1:8086 \
  --output /tmp/semantic-hub-mcp-verification.json
```

The check requires published `pharma_intelligence` version `v1.0` and enabled sample execution.
It uses a real MCP stdio client for discovery, keyword search, resolution, coverage, compilation, and sample execution.
It asserts `no_data` for the unavailable 1999–2020 cohort and 74.1 for the 2020–2024 cohort.
It makes no generation LLM calls or model writes. The token never appears in command arguments or output.
Use `--embedding` only when capabilities enable embedding search and you authorize a provider request.
This option adds one search against the pinned pharmaceutical version.

To verify the GitHub-installed package instead of the local source, add:

```sh
--package-source 'git+https://github.com/FerdinandZhong/semantic-hub.git@<commit>#subdirectory=apps/semantic-hub-mcp'
```

This starts `uvx` through the real MCP client. It does not inject the local package into `PYTHONPATH`.

The [GitHub installation report](../../docs/semantic-hub-github-mcp-verification.json) records the tested commit and twelve successful tool calls.
This verifies local stdio and HTTP execution, not deployment to CAI.
