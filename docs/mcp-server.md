# Helios MCP server

For the current local Semantic Hub workspace, use the [consumer MCP adapter](../apps/semantic-hub-mcp/README.md) and [API contract](semantic-hub-consumer-api.md).
The application described below serves the separate production artifact and authorization stack.

The MCP Application exposes Helios's governed semantic and data tools to the
Helios conversation client and to registered external agents. It speaks MCP
Python SDK 2.x Streamable HTTP with stateless JSON responses.

See [Talk to Your Data architecture](talk-to-your-data-architecture.md) for
the complete identity, LLM, authorization, and query flow.

## Cloudera AI Application

Create an Application with:

- script `helios/apps/helios/mcp/app.py`;
- a stable subdomain such as `helios-mcp`;
- the same standard PBJ Python 3.12 runtime used by the API;
- **Enable Unauthenticated Access** selected at the Cloudera gateway.

The last setting permits non-browser MCP protocol clients to reach the
Application. It does not make MCP anonymous: `/mcp` always requires the
configured bearer, and every tool requires a signed UI Principal or a
registered agent Principal. Missing bearer configuration returns 503.

The endpoints are:

```text
https://helios-mcp.<workbench-domain>/mcp
https://helios-mcp.<workbench-domain>/healthz
```

`/healthz` is public and returns readiness, version, model count, and metadata
repository status. The public `/` route returns only service endpoint
information so Cloudera root probes do not create authentication failures.
MCP protocol access at `/mcp` still requires the bearer and Principal context.

## Environment

Required on MCP:

```text
HELIOS_MCP_TOKEN=<random bearer credential>
HELIOS_MCP_DELEGATION_SECRET=<random value of at least 32 bytes>
HELIOS_MCP_ALLOWED_HOSTS=helios-mcp.<workbench-domain>
```

The API Application must receive the same token and delegation secret, plus:

```text
HELIOS_MCP_URL=https://helios-mcp.<workbench-domain>/mcp
HELIOS_MCP_TIMEOUT_SECONDS=180
```

The timeout is consumed by the API's server-side conversation client, not by
browser JavaScript or the MCP Application. It defaults to 45 seconds and must
be a positive number.

Configure `HELIOS_METADATA_DB`, `HELIOS_ROOT`, and `HELIOS_RUNS_DIR` only when
their project-persistent defaults are not correct. The API and MCP Applications
must resolve the same metadata grants and model artifacts.

For delegated queries, MCP also requires:

```text
IMPALA_HOST=<Virtual Warehouse JDBC host or URL>
WORKLOAD_USER=<approved Helios proxy account>
WORKLOAD_PASSWORD=<workload password>
IMPALA_PROXY_DELEGATION=true
```

The Virtual Warehouse must permit that account to proxy SSO subjects through
`doAs`, and Ranger must enforce the effective user. Helios verifies
`EFFECTIVE_USER()` before executing compiler-generated SQL. Leave
`IMPALA_PROXY_DELEGATION` false until this is proven in the target environment.

Test the two authentication stages independently from a new Workbench Session
that has the same project environment:

```bash
cd "$CDSW_PROJECT_DIR/helios"
python -m helios_core.engines.impala_diagnose \
  --delegated-user '<Cloudera SSO subject>'
```

The command prints no credential or SQL. If `service-account authentication`
fails with HTTP 401, use the CDW workload username and workload password—not
the Helios MCP bearer or an interactive browser password—and verify the host
and `httpPath` copied from the Virtual Warehouse JDBC configuration. If the
service account succeeds but `proxy delegation` fails, configure that workload
account as an authorized Impala proxy user for the SSO subject. A Talk request
performs the same distinction after a delegated HTTP 401 and returns either
`workload_authentication_failed` or `proxy_delegation_denied`.

No custom Cloudera Runtime is required for MCP. Install the pinned API
requirements into the project-local dependency directory as described in
`ui-deployment.md`.

## Authentication and model context

The Helios API sends:

```text
Authorization: Bearer <HELIOS_MCP_TOKEN>
X-Helios-Principal-Assertion: <short-lived signed assertion>
```

The assertion carries the API-authenticated Principal, organization, and
locked model. MCP verifies it and reloads current grants before every tool
authorization.

For a separately registered external agent, set:

```text
HELIOS_MCP_DEFAULT_PRINCIPAL=<issuer>:<subject>
```

The client then sends `X-Helios-Model-ID`. The configured Principal must exist
in normal Helios grant records. A shared bearer alone never grants access.

## Current tools

- `list_models()` — grant-filtered published model inventory.
- `discover_models(question, limit)` — discover authorized published models.
- `resolve_context(question, model)` — bounded definitions, dependencies, and a `bundle_id`.
- `compile_query(metrics, dimensions, filters, limit, engine, model, bundle_id)` — compile only the validated bundle.
- `run_query(metrics, dimensions, filters, limit, model, bundle_id)` — compile and execute with separate data authorization.

The conversation client exposes only these five tools.
Compilation and execution require a current bundle bound to caller, policy, session, and published release.
Missing or invalid bundles return `retrieval_bundle_required` or `retrieval_bundle_invalid`.
`describe_model`, `describe`, and `search_semantics` remain Python helpers, not registered agent tools.
The server separately exposes Atlas lineage and document/entity tools.
Document tools are excluded from this conversation workflow until source/model filtering is verified.

Published Ossie artifacts are authoritative; the model store rejects unpublished proposal fallback.
Compilation uses the shared compiler with the bounded model returned by retrieval validation.
See [indexed retrieval and budgets](semantic-retrieval.md) for the current contract and limitations.

Use metric names and field identifiers returned by `resolve_context`.
The typed request must stay inside that bundle's datasets, fields, metrics and relationships.
Legacy name normalization cannot authorize or add definitions outside the bundle.
Filters accept `column` or the equivalent `field` key, with `op` and `value`.
Preserve the returned datatype; use JSON numbers for numeric fields.
The compiler validates values before execution and rejects invalid combinations with `invalid_filter_value_type`.

Filters use objects such as:

```json
{
  "metrics": ["Store Sales Revenue"],
  "dimensions": ["sales.store.state"],
  "filters": [
    {"column": "sales.date.year", "op": "=", "value": 2001}
  ],
  "limit": 20,
  "model": "sales-model",
  "bundle_id": "REPLACE_WITH_RESOLVE_CONTEXT_BUNDLE_ID"
}
```

Models are re-read when the published artifact changes. Authorization grants
are loaded from metadata for the current Principal; a requested model that
does not match the locked context is rejected. Expected lookup, ambiguity, and
compiler failures return structured `{error, message, retryable}` tool results
rather than terminating the MCP session.