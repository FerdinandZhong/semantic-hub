# Implementation architecture and data flow

This document describes the current demo. The [solution proposal](proposal/solution_design.md) describes the broader seven-layer banking architecture and P0–P9 delivery pipeline.

## Runtime

A single Python/FastAPI process serves static HTML/CSS/JavaScript and REST APIs. The browser calls the same origin. Server-side connectors reach configured data and inference services. The registry stores shared operator settings in `demo/runtime/settings.json` (or `WORKSPACE_SETTINGS_FILE`), with masked secret responses and file mode 0600. Use a single application worker for the current file-backed registry.

## Query flow

1. The browser submits tab, question, mode, source and time range.
2. The API checks the optional workspace token and limits concurrent queries to four.
3. Sample mode loads synthetic fixtures without outbound queries. Live Data Understanding first loads its approved semantic model.
4. The guided or configured LLM planner selects a typed allowlisted operation.
5. NiFi REST, log search or Prometheus tools execute bounded read-only requests. Semantic requests compile with Helios and pass SQL checks before Trino execution.
6. LangGraph computes findings and charts, validates evidence, and returns source details, trace stages and elapsed time. Connection failures return 503 with no sample fallback.

The planning LLM receives the question, available tools and approved semantic definitions where relevant; raw result/log payloads are not sent for free-form summarization.

```text
Browser -> FastAPI authentication and query limits
                    |
          +---------+----------+
          |                    |
      Sample mode          Live planner
          |                    |
   Synthetic fixtures    Typed tool plan
                               |
                  +------------+--------------+
                  |            |              |
               NiFi REST   Logs / metrics   Approved model
                  |            |              |
                  |            |         Helios compiler
                  |            |              |
                  |            |         SQL validation
                  |            |              |
                  |            |             Trino
                  +------------+--------------+
                               |
                   Evidence summary and trace
                               |
                            Browser
```

## Components

| Module | Responsibility |
| --- | --- |
| `app/main.py` | Routes, authentication, middleware, concurrency and execution coordination. |
| `app/config.py` | Environment defaults and settings object. |
| `app/management.py` | Persistent connections, models, activation and secret masking. |
| `app/contracts.py` / `planner.py` | Typed inputs, tool plans and guided/LLM selection. |
| `app/connectors.py` | Bounded source queries, health checks and redaction. |
| `app/semantics.py` | Approved file/AlloyDB model loading, validation, Helios compilation and Trino execution. |
| `app/answers.py` / `samples.py` | Deterministic summaries and explicit synthetic fixtures. |
| `static/` | Dashboard and configuration/model dialogs. |

## Semantic and observability boundaries

AlloyDB JSONB stores an approved Ossie model, not an executable query engine. Helios compiles its definitions; Trino executes the resulting SELECT over approved tables. The demo enforces row/table/function restrictions. Broader document/vector retrieval is planned separately.

Kibana accesses Elasticsearch logs; OpenSearch is a separate backend. Prometheus supplies metrics; Grafana provides drill-down links. OTLP ports ingest telemetry and are not query endpoints. Object storage archives are not directly queried by Kibana.

## Deployment and trust

Python/CAI uses `start_app.py`; Docker packages the demo and persists registry settings in a named volume. Runtime credentials remain server-side. APIs support an optional bearer token and settings writes check supplied Origin against Host. These controls do not implement individual operator roles, end-user source delegation or multi-tenant isolation. Production policy integration remains proposed work.

The current demo has no durable approval engine or action-writing tools. External-source ACLs, full document provenance and Agent Studio execution belong to the wider architecture. See [component-api.md](component-api.md) for concrete endpoints.

## Source discovery and semantic preparation

Source discovery now returns a normalized metadata inventory from the same bounded column query.
The inventory records technical provenance and keeps business review separate from schema facts.
The optional Atlas adapter reads explicitly mapped entities and extracts selected glossary labels and classifications.
It is not wired to a live route and does not grant access permissions.
The offline financial fixture pack supplies independently generated tables and a draft Ossie model.
See [financial foundation](demo/FINANCIAL_FOUNDATION.md) for implemented boundaries and next integration steps.

```text
Running application
  +-- Sources -> Trino metadata -> bounded preview/profile
  +-- Build semantic context -> draft -> reference comparison
  |                                      |
  |                                      v
  |                            reviewed immutable release
  |                                      |
  |                                explicit activation
  |                                      |
  +-- Existing query tabs <---- approved file + pinned hash
```

`source_workflow.py` performs read-only discovery and returns at most 100 names or 50 preview rows.
Profiles describe the returned sample; they do not certify whole-table quality or key uniqueness.
`semantic_workflow.py` stores drafts, revisions, review evidence and immutable releases beside the settings registry.
Source operations use the configured Trino service identity.
The workflow uses shared operator authentication; reviewer names are attestations, not separately authenticated roles.

Live validation uses the real Helios compiler and an independently reviewed reference SELECT.
It rejects empty, mismatched or row-limit-sized results.
Draft edits clear validation; changed source/ compiler settings require validation again.
Schema checks run before validation, publication and activation.
Existing queries keep their current approved model until an operator activates a new live release.
Activation writes a pinned local release file and explicitly clears the AlloyDB override.
The new publisher does not write releases into AlloyDB; the existing AlloyDB reader and CLI publisher remain available.

Initial scope is one table/view and one aggregate metric per draft.
Business rules are review context, not generated WHERE filters; select a prepared view that enforces those rules.
Sample comparison uses synthetic rows and a local SQL preview, not Helios/live-source acceptance.
Stored validation contains SQL and summary evidence; returned comparison rows are displayed without persisting their payloads.

## UOB application shell

The browser loads `static/ui.js` for local workspace-page navigation.
The page finder uses the existing page controls and does not call data-source APIs.
UOB branding and navigation icons use inline vector markup.
All source-query and semantic-release contracts remain as documented above.

## Implemented LangGraph orchestration — 7 October 2026

LangGraph coordinates all three query tabs inside the existing FastAPI process.
Each request uses fresh graph state; there is no durable conversation memory or checkpointer.
Sample mode remains offline, including planning, follow-up tools and explanation.

```text
Intent -> Context -> Plan -> Validate -> Execute -> Analyze
   |                    |                             |
   +---- Clarify -------+                    optional metric follow-up
                |                                     |
                +---------------- Explain <- supported findings
                                     |
                             Output validation -> Answer and evidence
```

Native log tools use configured-source field capabilities, exact timestamp intervals and backend aggregations.
Exact lookup returns at most 50 matches with source identifiers, preserved multiline messages and marked redactions.
It never silently expands the timestamp interval; pagination and document-ID lookup remain pending.
Summary queries use complete-window counts and histograms, rather than extrapolating from displayed examples.
Category responses include missing values, other counts and aggregation uncertainty.
Prometheus summaries report finite samples, units, instances and latest sample timestamps.

The planner selects typed tools and one optional metric follow-up after logs.
Execution allows two tool calls and six source HTTP requests within a 75-second request deadline.
Planning and explanation use at most two logical model calls with 700 and 300 completion-token limits.
Each stage can negotiate unsupported parameters through at most four HTTP attempts within its existing deadline.
The graph reports actual model HTTP attempts separately; the overall 75-second deadline remains unchanged.
The planning context is limited to 40,000 characters.
The explanation model can select supported finding IDs; it cannot generate numerical evidence or arbitrary prose.
Raw log messages are not sent to that model.
Invalid explanation selection retains computed findings with a visible trace notice.
Source or planning failures remain visible and never trigger sample fallback.
Remote LangSmith tracing is disabled for graph execution.

Charts and findings render inside the existing Answer & evidence window.
Line charts show trends; bars compare categories; explicit pie requests require a verified category partition.
The existing navigation and Execution context panel remain in place.
Operational definitions remain separate from banking semantics unless reviewed shared mappings exist.
Inference activation, aggregate-to-log drill-down, conversation history and durable recovery remain pending.

## Implemented Helios operational context adapter

`observability_context.py` imports `helios_core.observability` from the customized checkout.
The configured directory contains `shared/helios_core/observability`.
Keep operational and SQL integrations on the same checkout per application process.

```text
Saved source settings -> Helios metadata discovery -> context draft
                                                       |
                              selected meanings + explicit review
                                                       |
                                 immutable release + pinned checksum
                                                       |
                                            explicit live activation
                                                       |
                         source binding + checksum -> token retrieval
                                                       |
                           observability planner + displayed evidence
```

The workspace stores draft metadata and release pins beside the settings registry.
Source endpoint, identity and credential changes invalidate the serving binding.
Metadata source-schema refresh and invalidation remain future work.
Publication does not change active context; synthetic releases cannot activate live serving.
Only selected descriptions and aliases can be edited through the API.
Discovered properties remain server-owned evidence.

An activated context release contributes up to ten matching metric definitions or essential log fields to live observability planning.
The response exposes its version, checksum, retrieved definitions and source limitations.
Without an active release, application metric definitions and log field contracts still explain the native tools.
A configured but invalid active release returns a visible failure rather than silently dropping context.
Sample querying never loads live context or calls a proposal model.
Optional live description suggestions use the shared active inference endpoint through Helios.
Native query tools and LangGraph now consume this context; findings and chart values remain computed evidence.

## Saved observability review — 7 October 2026

Optional AI suggestions run after successful metadata discovery.
If suggestions fail, the application saves the discovered metadata with a safe `suggestion_error` notice.
It discards partial suggestions and leaves review, publication and activation to the operator.
Source discovery failures remain errors; this recovery does not introduce synthetic evidence.

The demo imports the sibling Helios checkout directly; it does not vendor a second observability library.
Helios owns metadata discovery, immutable release approval/publication and definition retrieval.
The application owns filtering, selection, editable review progress and release inclusion.

```text
Sibling Helios discovery -> Immutable discovered metadata
                                      |
                         Application review state + revisions
                                      |
                         Reviewed included definitions only
                                      |
                         Helios approval -> release -> activation
```

The review adapter preserves original metadata and stores editable meanings separately.
Existing drafts gain default pending/excluded review state when opened; their source documents remain unchanged.
Meaning or alias edits reset review and warning acknowledgement.
Publication through saved review rejects pending included definitions and unresolved blocking issues.
Warnings require explicit acknowledgement during group review.
Source-binding checks and optimistic revisions remain enforced on saves and publication.
The legacy explicit-items publication contract remains supported for existing clients.
This shared operator workflow does not establish individual reviewer identities or delegated RBAC.
Review reuse across discoveries and reusable selection rules remain future work.

## Observability dictionary — 9 October 2026

Observability uses metric meanings and essential log fields rather than a banking table model.
The application dictionary defines four native tools: availability, CPU, memory and scrape duration.
Each definition includes units, type, expected labels, aggregation rules and interpretation limits.
Helios retrieves reviewed source meanings from the activated release.
The serving projection excludes dashboard panels, nonessential log fields and raw discovery properties.
Existing releases and their checksum checks remain intact.

```text
Question + source -> relevant application definitions + matching reviewed meanings
                                      |
                          typed plan + fixed native expression
                                      |
                          bounded read-only source request
                                      |
                          numeric checks -> findings + definitions
```

Reviewed descriptions cannot change executable PromQL.
CPU uses Prometheus counter rates before averaging cores.
Analysis excludes non-finite values, invalid metric values and samples outside the selected interval.
Returned evaluation gaps and incomplete interval coverage produce limitations.
These checks do not audit every underlying scrape or establish exporter completeness.
Sample mode uses application definitions and synthetic observations without loading an active release.
Atlas remains optional for the separate banking foundation; observability does not require Atlas.

## Banking retrieval and caller boundary — 9 October 2026

Banking planning now receives a retrieved Ossie bundle rather than the full approved document.
The complete release stays server-side for checksum validation and release identity.
A server-owned policy maps opaque bearer credentials to subjects, roles, release hashes and exact physical field scopes.
The optional policy loads through `WORKSPACE_ACCESS_POLICY_FILE`; it is not editable through browser settings.
Policy-enabled analysts can query banking definitions and compile within their permitted scope.
Operator endpoints reject analyst credentials before accessing settings, drafts or discovery.
The existing operator runtime remains in single-operator mode until a policy is configured.

```text
Verified credential -> release-bound permitted fields
                                |
                    lexical candidates + dependency closure
                                |
                    bounded bundle -> typed request
                                |
                    Helios validation + compilation
                                |
                    verified platform decision -> execution adapter
```

Retrieval includes metric inputs, computed-field dependencies and required permitted join keys.
Parallel relationships require one reviewed default or clarification.
No-match, tied metric candidates and oversized bundles request clarification before planning.
Limits are five datasets, 100 fields and 24,000 serialized context characters.
No retrieval cache is installed; policy and release changes cannot reuse a cached prompt.
Execution rechecks policy content and platform identity before compilation and immediately before execution.
The boundary reuses Helios `DataPolicy` and `Principal` contracts.
Its default platform adapter denies execution.
No shared Trino account substitutes for a denied or unavailable caller adapter.
Policy-enabled live preparation and reference validation remain disabled until equivalent adapters exist.
Atlas search and database-enforced row/column acceptance remain future integration work.

## Offline financial execution

`SAMPLE_FINANCE_DIR` selects a prebuilt, checksummed synthetic DuckDB artifact.
Without this setting, the existing teaching preview remains available.
Sample release selection uses `sample_active` in the semantic workspace store.
It does not modify the active live model or connection settings.
Validation, publication, selection and querying verify the fixture binding.

```text
Prepared synthetic database -> discover columns -> review Ossie draft
                                                     |
                                                     v
                                     Helios/reference reconciliation
                                                     |
                                                     v
                                      Publish -> select sample release
                                                     |
                                                     v
Question -> bounded semantic retrieval -> offline typed plan
                                                     |
                                                     v
                         Helios SQL -> SQL allowlist -> read-only DuckDB
                                                     |
                                                     v
                                      Decimal results + execution evidence
```

The adapter checks logical `iceberg.synthetic_finance` paths before removing the catalog for DuckDB.
It preserves the schema and translates the Trino SQL dialect through SQLGlot.
Execution disables external access, limits memory to 256 MB, interrupts after ten seconds and returns at most 100 rows.
Decimal results use strings to preserve monetary precision.
The sample planner supports one prepared payments table and one reviewed sum metric.
It also supports payment counts, one grouping, one jurisdiction filter and an inclusive booking-date range.
It requires clarification for unsupported meanings or filters.

The bundle builder copies Helios package source, schemas and license files.
It excludes repository settings, evaluation labels and independent reference results from the serving image.
Live requests retain the caller-enforced adapter boundary. They cannot use this sample adapter.
