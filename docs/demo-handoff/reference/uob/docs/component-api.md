# Component and API reference

Source of truth: [main.py](demo/app/main.py), [contracts.py](demo/app/contracts.py) and [management.py](demo/app/management.py). Paths below are relative to the application origin. Swagger/ReDoc pages are disabled.

## Authentication and errors

When `APP_API_TOKEN` is set, protected routes require `Authorization: Bearer <token>`. Configuration mutations/tests also reject a supplied Origin whose host differs from the request Host. This is shared workspace authentication, not separate administrator RBAC. `/healthz` and static UI delivery are public.

Expect 401 for missing/invalid workspace authentication, 403 for rejected configuration Origin, 422 for invalid input, 429 when the query concurrency limit is reached, and 503 for handled connection/semantic failures. Response errors use either FastAPI `detail` or route-specific `error`; clients should handle both.

## Endpoints

| Method and path | Contract |
| --- | --- |
| GET `/healthz` | Process liveness: `{"status":"ok"}`; not a target readiness check. |
| GET `/api/config` | Planner/active model, configuration indicators, source links and available tool descriptions. |
| GET `/api/connections` | Source health results and configured/unverified semantic/Trino indicators. |
| POST `/api/query` | Execute a typed query; contract below. |
| GET `/api/settings` | Grouped connections and model registrations with masked secrets. |
| POST `/api/settings/connections/{group}` | Save allowed settings for `nifi`, `observability` or `data`. |
| POST `/api/settings/connections/{group}/test` | Test saved group settings; returns `targets` with names, states and optional details. |
| POST `/api/models` | Create/edit model registration. |
| POST `/api/models/{identifier}/{action}` | `test`, `activate` or `delete`; test makes a small planning request. |
| GET `/api/semantics` | Inspect configured approved model. |
| POST `/api/semantics/compile` | Compile a semantic-request object; returns SQL, model metadata and `executed:false`. |

## Query request

```json
{"tab":"nifi","question":"Show flow status","mode":"sample","source":"auto","minutes":60}
```

`tab` is `nifi`, `observability` or `data`; question length is 3–1500 characters; mode defaults to `live`; source is `auto`, `kibana`, `opensearch` or `prometheus`; minutes is 5–1440 (default 60). Extra fields are rejected.

Successful responses include `trace_id`, `timestamp`, `mode`, `planner`, `tool`, `summary`, `steps` and `elapsed_ms`, plus tool-specific evidence such as `rows`, `source`, `query`, `scope` or `model`. Do not assume all tools return the same evidence columns. Handled connection errors return 503 with `error`, trace information and `sample_fallback:false`.

Allowed plan tools are `nifi_status`, `nifi_bulletins`, `nifi_processors`, `logs`, `metrics`, `semantic_describe` and `semantic_query`. Metric choices are `up`, `cpu`, `memory` and `scrape_duration`. No arbitrary SQL or arbitrary execution endpoint is accepted through the query plan.

## Configuration contracts

Connection field allowlists are defined by `GROUPS` in management.py. Unknown fields are rejected. For secret API fields, `null` preserves a saved value and `""` clears it; the UI maps an empty field to preserve unless its clear checkbox is selected. Reads expose `{ "configured": true/false }` rather than secret values. Saved connection fields override environment defaults.

Model registration accepts `name`, `base_url`, `model`, optional `api_key`, and `id` when editing. The base URL must be HTTP(S) without embedded credentials, query or fragment. `api_key:null` preserves the existing key. Model reads include `key_configured` and `active`, never the key itself. Activating a model changes planning for subsequent requests; deleting the active model returns to guided mode.

## Semantic integration

File models require the configured approved file/hash. AlloyDB uses the registry schema and publishing helper under `demo/scripts/`; a configured AlloyDB source takes precedence over file mode. Helios model validation precedes compilation; SQL validation precedes Trino execution. Inspection/compile endpoints use the configured real model even when the UI query mode is Sample preview.

The compile request is the Helios semantic-request object, not the outer `/api/query` envelope. Use the dashboard preview and the approved model's measures/dimensions to build it; arbitrary domain field names are not a stable application API.

## Sources and semantic preparation APIs

Column, preview and profile discovery responses include additive `metadata` with schema `uob.metadata.inventory.v1`.
It contains explicit mode, dataset source identity, fields with technical provenance and limitations.
Existing response fields remain available.
Current discovery returns `enrichment: null`; no Atlas requests occur through this endpoint.
The internal Atlas adapter requires an authorized caller and an explicit GUID/qualified-name source mapping before invocation.

| Method and path | Contract |
| --- | --- |
| POST `/api/sources/discover` | Explicit sample/live mode; action catalogs, schemas, tables, columns, preview or profile; optional catalog/schema/table identifiers. |
| GET `/api/semantic-workspace` | Saved drafts and immutable releases; excludes connection credentials. |
| POST `/api/semantic-workspace/drafts` | Source selection, model name, business context, column meanings and one aggregate metric. |
| POST `/api/semantic-workspace/drafts/{identifier}` | Expected revision plus edited context/meanings/metric; increments revision and clears validation. |
| POST `/api/semantic-workspace/drafts/{identifier}/validate` | Expected revision and reference SQL; compiles/executes the metric and compares results. |
| POST `/api/semantic-workspace/drafts/{identifier}/publish` | Expected revision, new release version, reviewer name and explicit review confirmation. |
| POST `/api/semantic-workspace/releases/{identifier}/activate` | Activates a reviewed live release as the workspace's pinned local model. |

All POST routes use the operator authentication and supplied-Origin check.
Stale revisions, duplicate releases and failed publication gates return 409.
Missing review confirmation or column meanings return 422.
Source, schema or compilation failures return controlled 503 responses without sample fallback.

Draft creation requires `mode`, `catalog`, `schema`, `table`, `name`, `context`, `meanings` and `metric`.
Context contains grain, units, time_rule, inclusion and exclusion.
Metric contains name, source column, description and aggregate: sum, avg, count, min or max.
Unknown request keys are rejected.
Validate requests contain `revision` and `reference_sql`; reference queries follow the existing SQL source/function restrictions.
Result column names must match; numerical representations are normalized before comparison.
Sample releases cannot be activated for live queries.
Validation returns comparison rows for review, but the registry stores only SQL and summary evidence.

## LangGraph query contracts — implemented 7 October 2026

`GET /api/config` includes `orchestration: "langgraph"`.
Existing relative-window requests remain valid.
Observability accepts `observability_path`: auto, events, summary or exact.
Optional `time_range` contains ISO `start`, ISO `end` and an IANA `timezone` (default UTC).
Optional `exact_time` contains ISO `timestamp` and IANA `timezone` (default UTC).
Ranges are half-open, strictly ordered and bounded to 24 hours.
Exact precision follows the timestamp's fractional digits, with a maximum of six digits.
Named-zone DST ambiguity and nonexistent local times require an explicit offset.
Conflicting time selectors or exact Prometheus requests return 422.

```json
{"tab":"observability","question":"Show the exact error","mode":"live","source":"kibana","observability_path":"exact","exact_time":{"timestamp":"2026-10-06T09:42:18.417","timezone":"Asia/Singapore"}}
```

Ambiguous natural-language times return HTTP 200 with `status: "needs_clarification"` before querying sources.
Successful responses preserve existing fields and add `orchestration`, `intent`, `findings`, `charts`, `limitations`, `citations`, `window` and `budget`.
A combined log/metric request can include `follow_up` evidence.
The normalized window records UTC bounds, display timezone, precision and exclusive end semantics.
Exact rows include source index/document identifiers, timestamp, message and a redaction flag.
Exact matches are limited to 50; total matches and truncation remain visible.
Source timestamp precision can reject narrower intervals rather than manufacture precision.
Statistics expose window counts, matching counts, histograms and available category totals.
Partial results suppress unsupported ratios and category partitions.
Chart types are line, bar and pie, with at most 200 points per chart.
The model cannot supply chart values.

Plans additionally accept `log_intent`, `group_by` and optional `follow_up_metric`.
Grouping choices are error_code, severity and service; metric choices remain allowlisted.
Budgets allow two tools, six source requests and two model calls within 75 seconds.
No conversation identifier, pagination cursor, arbitrary query DSL or document-ID request is accepted in this increment.
Model tests validate connectivity plus one typed query plan; they do not execute the proposed NiFi query.
Errors distinguish endpoint HTTP rejection, timeout, transport failure and invalid query-plan JSON.
No error includes the raw provider response or saved API key.


## Model request compatibility — 7 October 2026

Planning and explanation share `app/model_client.py` request construction.
GPT-5 and supported o-series model names use `max_completion_tokens` and omit `temperature`.
GPT-5.1, GPT-5.2 and GPT-5.4 use `reasoning_effort: "none"` for short typed responses.
Other endpoint models start with the existing `max_tokens` and temperature settings.
Both stages negotiate compatibility on explicit HTTP 400 unsupported-parameter responses.
The adapter switches between `max_tokens` and `max_completion_tokens` at most once per stage.
It can remove explicitly rejected `temperature` or `reasoning_effort` settings.
Each stage permits at most four HTTP attempts within its existing total deadline.
Planning retains 20 seconds; finding selection retains 10 seconds.
Authentication, quota, transport and unrelated request failures do not trigger compatibility retries.
Completion-token limits remain unchanged when switching parameter names.
The response budget distinguishes two logical `model_calls` from at most eight `model_http_requests`.
Budgets remain 700 completion tokens for planning and 300 for finding selection.
HTTP 400 responses expose only allowlisted rejected parameter names, never raw provider text.
Truncated planning responses report the completion-token limit explicitly.
Provider compatibility remains model-specific; this fix verifies the saved GPT-5.4 registration.

## Grafana basic authentication — 7 October 2026

Observability settings accept `grafana_user` and secret `grafana_password` alongside `grafana_token`.
Environment defaults are `GRAFANA_USER` and `GRAFANA_PASSWORD`; no credentials are built into source code.
The settings API returns a configured flag for the password and supports preserve/clear semantics.
A nonempty token takes precedence; basic credentials are then omitted from Helios source configuration.
Without a token, the adapter passes basic credentials to the existing Helios metadata collector.
Credential changes participate in source binding and can invalidate an active Grafana context release.

## Saved context review API — 7 October 2026

Observability discovery returns a saved draft with HTTP 200 when metadata discovery succeeds but optional AI suggestions fail.
The draft includes `suggestion_error` with a safe explanation.
Its definitions retain source meanings; partial AI suggestions are discarded.
Publication and activation remain explicit operations.
Missing active models still fail before discovery when suggestions are requested.
Source discovery failures still return controlled errors without sample fallback.

`POST /api/observability-context/drafts/{identifier}/review` saves progress with operator auth and the existing Origin check.
Request fields are `revision`, `items`, optional `reviewer` and optional `version`.
Each item accepts `id`, `description`, `aliases`, `included`, `reviewed` and `warnings_acknowledged`.
An empty description is permitted in a pending draft; aliases retain count and length limits.
Unknown IDs, duplicate IDs, source-property edits and provenance overrides are rejected.
Stale revisions or changed source bindings return 409 without overwriting saved progress.
The response includes the incremented revision, original document and separate `review` states keyed by definition ID.
Each review state exposes server-derived provenance and issues with blocking/warning severity.
Edits to meaning or aliases reset reviewed status and warning acknowledgement regardless of client flags.
Missing meanings and source-reported type/unit conflicts block review completion.
Missing metric type/unit and suspicious thread-panel byte units are warnings requiring acknowledgement.
These checks do not prove semantic correctness or detect every unit inconsistency.

`POST .../publish` now also accepts revision/version/reviewer/confirmed without an `items` array.
That form publishes only included definitions from saved review state.
Every included definition must be reviewed with blockers resolved and warnings acknowledged.
The existing explicit-items contract remains accepted for backward compatibility.
Live activation remains a separate endpoint and requires a valid source-bound release.
No Helios library files changed in this review increment.

Observability description suggestions use the demo shared Chat Completions compatibility adapter through `DescriptionModel.complete_json`. Helios still supplies discovery, metadata validation and proposal rules from the sibling checkout. Each batch has a 30-second deadline; the proposal budget is 180 seconds and 40 batches. Missing active models fail before metadata discovery. Suggestions remain unreviewed drafts.

## Observability dictionary response — 9 October 2026

Completed observability queries include `operational_context` in both modes.
Its `schema` is `uob.observability.dictionary.v1`.
`version` is `native-v1` unless an activated reviewed release contributes its version and `sha256`.
`metrics` contains relevant application definitions, including the validated metric and any metric follow-up.
`log_fields` describes application evidence fields for log plans.
`items` contains up to ten matching, projected definitions from a reviewed release.
`scope` and `notes` explain provenance and source limits.

Application metric definitions contain `id`, `source`, `origin`, `description`, `unit`, `metric_type`, `labels`, `input_metrics`, `aliases`, `aggregation` and `limits`.
Reviewed metric entries expose supplied units/types and report missing values without inference.
They do not expose raw dashboard queries or supply executable expressions.
Primary metric responses also include `metric_definition` and `window`.
Live metric responses include the requested `step_seconds` for evaluation-gap checks.
These fields are additive; existing response fields remain supported.

## Banking caller and retrieval contracts — 9 October 2026

When `WORKSPACE_ACCESS_POLICY_FILE` is set, API credentials resolve through the server policy.
The policy schema is `uob.access.v1`, with `revision` and a `principals` array.
Each principal contains `subject`, `role`, `token_sha256`, `model_sha256` and `fields`.
Roles are `operator` or `analyst`; `fields` maps exact physical source paths to allowed field names.
Wildcard fields, duplicate identities, duplicate token hashes and invalid hashes are rejected.
The shared application token cannot substitute for a caller credential in this mode.
Missing or invalid credentials return 401; invalid policy files return 503.
Management endpoints return 403 for analysts.
Ordinary query payloads cannot set caller identity; unknown fields remain rejected.

Banking results add `semantic_retrieval`: `release_sha256`, `policy_revision`, `sources`, `method`, `matches`, context counts and `limits`.
Matches expose permitted names, kinds and lexical scores.
No-match and ambiguous retrieval returns `status: needs_clarification` without invoking the planner.
The complete semantic release hash remains in `model`; its retrieved subset does not become a published release.
`GET /api/semantics` returns at most 100 permitted definition rows.
`POST /api/semantics/compile` compiles permitted definitions and executes nothing.

Trusted server integration can provide `create_app(..., platform=adapter)`.
The adapter implements `authorize(settings, caller, sources)` and `execute(settings, sql, caller)`.
Authorization returns `PlatformDecision` with allowed status, confirmed identity enforcement and the effective subject.
The effective subject must equal the verified caller.
The adapter must enforce that identity against the database and preserve row/column controls during execution.
An application assertion or fixture is not evidence of database enforcement.
The installed default returns denial; no browser option enables an allow decision.

## Financial sample contracts

`SAMPLE_FINANCE_DIR` is a server environment setting. The browser cannot change it.
`GET /api/config` and `GET /api/semantic-workspace` expose `sample_finance_available` without a filesystem path.
Financial sample discovery exposes six tables under `iceberg.synthetic_finance`.
Preview and profile use at most 50 actual fixture rows.
Validation evidence includes `fixture_sha256` and the compiler label `Helios / offline synthetic DuckDB`.

`POST /api/semantic-workspace/releases/{identifier}/select-sample` requires operator authentication.
It accepts only sample releases bound to the configured fixture checksum.
It returns `sample_active` and `live_settings_changed: false`.
The selected identifier persists in the workspace store and appears in its GET response.
The existing live activation route continues to reject sample releases.

Sample banking queries use the selected release when the artifact is configured.
Missing selection and unsupported questions return `needs_clarification` without execution.
Successful results include compiled logical SQL, release identity, retrieval evidence and fixture checksum.
Monetary result values are decimal strings. Counts are integers.
Sample queries report zero model calls and zero source requests.
