# Observability semantic context

The `observability_semantic_context` branch adds an initial metadata-to-context extension.
It provides a Python library and CLI under `helios_core.observability`.
It does not change existing SQL discovery, Ossie compilation, console routes or MCP tools.
NiFi REST discovery is deferred.

## Implemented scope

| Component | Collected context |
| --- | --- |
| Elasticsearch | Scoped index field names, types, searchability, aggregation support and type conflicts. |
| Kibana | The same Elasticsearch metadata through its fixed console proxy; no UI scraping. |
| Prometheus | Metric names, help descriptions, reported types, units and metadata conflicts. |
| Grafana | Legacy dashboard API panel titles, descriptions, display units and bounded query examples, including nested panels. |
| Draft generation | Metadata-backed descriptions and optional LLM description/alias suggestions. |
| Publication | Explicit operator confirmation, per-item review, unique version, private immutable file and SHA-256 pin. |
| Retrieval | Deterministic token matching against reviewed definitions and aliases. |

```text
Explicit source configuration
             |
  bounded metadata collection
             |
 draft context + optional suggestions
             |
  selected items + reviewed meanings
             |
 immutable release + external checksum pin
             |
   context retrieval for native tools
```

## Setup and discovery

Use the existing Helios runtime's `httpx` and `pydantic` dependencies.
From the repository root, set `PYTHONPATH=shared`.
Save an untracked operator configuration under `state/observability/`:

```json
{
  "sources": [
    {"name": "logs", "kind": "kibana", "url": "http://OBSERVABILITY_HOST:5601", "index": "uob-logs-*", "limit": 150},
    {"name": "metrics", "kind": "prometheus", "url": "http://OBSERVABILITY_HOST:9090", "limit": 100}
  ]
}
```

Replace the hostname with the configured service address.
Add Grafana separately after its dashboard credentials are available:

```json
{"name": "dashboards", "kind": "grafana", "url": "https://GRAFANA_HOST", "token_env": "OBS_GRAFANA_TOKEN", "limit": 50}
```

Credentials use `username_env`, `password_env` or `token_env` references.
The CLI rejects inline credentials.
Credentials never enter snapshots or releases.
TLS verification stays enabled; `ca_bundle` can reference a trusted certificate file.

```bash
PYTHONPATH=shared python -m helios_core.observability discover \
  --config state/observability/sources.json \
  --output state/observability/draft.json
```

Add `--propose` to use the existing Helios inference configuration.
The LLM may suggest descriptions and aliases only.
It cannot change discovered metadata or approve items.
No inference endpoint is required for deterministic draft generation.

Collectors use read-only GET requests except Kibana's POST transport for fixed GET metadata queries.
Each response is limited to 2 MB; timeouts and source inventories are bounded.
Grafana collection checks a 60-second deadline between requests.
A final in-flight request can extend that deadline by its configured timeout.
An unavailable source fails discovery visibly; configure optional sources in separate runs.

## Review and publication

1. Inspect source provenance and inventory-limit notes in the draft.
2. Remove items outside the intended serving scope.
3. Edit each selected item's description and aliases.
4. Investigate unknown metric types, empty units and schema conflicts.
5. Set `reviewed` to `true` for each selected item.
6. Publish with a reviewer name, version and explicit confirmation.

```bash
PYTHONPATH=shared python -m helios_core.observability publish \
  --draft state/observability/draft.json \
  --directory state/observability/releases \
  --reviewer YOUR_REVIEWER_NAME --version obs-v1 --confirm
```

Keep the printed SHA-256 value outside the release envelope as the serving configuration pin.
An existing version cannot be overwritten.
Changing a release document invalidates the checksum.
Reviewer names are operator attestations, not separately authenticated identities.
The workflow does not provide Helios console RBAC or tenant isolation.

```bash
PYTHONPATH=shared python -m helios_core.observability search \
  --release state/observability/releases/obs-v1.json \
  --sha256 YOUR_REVIEWED_SHA256 --question "error code"
```

Python consumers call `load_release(path, expected_sha256)` before `search(document, question)`.
Consumers must enforce their own source permissions and current capabilities.
Context is descriptive evidence, not permission to execute a query.
No raw events are stored or sent to the proposal model by these collectors.

## Query integration boundary

The context schema is `helios.observability.context.v1`, separate from Ossie SQL models.
Prometheus tools execute PromQL; Elasticsearch tools execute validated native searches and aggregations.
Grafana panel query examples remain untrusted and non-executable.
Display units may reflect Grafana transformations rather than native metric units.
An unknown metric type must not silently become a counter or gauge.
An empty reported unit must not become a percentage through name inference.
Metadata discovery does not prove retention, live field coverage or query completeness.

Both observability paths can consume the context after UOB integration is implemented.
Exact lookup uses verified field mappings and preserves retrieved messages.
Statistical analysis uses verified aggregation fields and metric definitions.
The current extension does not execute either path or generate chart values.

## Verification and remaining work

```bash
PYTHONPATH=shared python -m pytest apps/helios/tests/test_observability_context.py -q
```

The focused tests cover metadata collectors, auth, source/index validation, bounded payloads,
conflicts, redaction, draft suggestions, review gates, immutable publication and checksum tampering.

Remaining work:

- Add console authoring/review and authorized API/MCP exposure.
- Add bounded label/series discovery, recording rules, Grafana variables/thresholds and Kibana saved-object enrichment.
- Add bounded log profiling or reviewed extraction rules when metadata does not establish field meaning.
- Add source refresh comparison and approval invalidation when relevant mappings change.
- Integrate pinned context retrieval with UOB LangGraph and source capability validation.
- Implement native exact lookup and statistical tools under the UOB development plan.
- Add Atlas bindings when required; defer NiFi discovery.

The existing warehouse profiler/proposer cannot accept these records without an adapter.
This module reuses the Helios inference client and proposal/review/publication pattern without treating telemetry as SQL tables.

## Verification — 6 October 2026

- 18 focused observability tests passed in the local Python environment.
- 29 tests passed when including existing artifact and reviewer regression tests.
- The CLI collected a live draft from the supplied Kibana and Prometheus host.
- The draft contains 95 log fields and 100 metric definitions.
- The metric inventory is explicitly marked as potentially truncated.
- No live draft was approved or activated.
- Grafana metadata access remains blocked by HTTP 401 pending credentials.
- Live LLM suggestions, console/MCP integration and UOB consumption remain unverified.
