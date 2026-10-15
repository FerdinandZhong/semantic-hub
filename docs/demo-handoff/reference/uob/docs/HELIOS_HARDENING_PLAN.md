# Helios hardening plan for the UOB demo

Reviewed: 8 October 2026. Status: foundation starter implemented; hardening milestones remain planned.

Update: the [metadata and financial foundation starter](FINANCIAL_FOUNDATION.md) is now implemented.
The active sibling branch was fast-forwarded to upstream `316f5d8` with its observability extension preserved.
Application caller controls and lexical retrieval are implemented on 9 October. Database enforcement acceptance, scoped conversations and sandbox analytics remain pending.

## Decision

Prioritize caller authorization and metadata retrieval before expanding log drill-down.
Keep Helios for approved Ossie definitions, semantic validation and compilation.
Add the missing controls around the demo's execution path.
Reuse reviewed sibling components where their interfaces and enforcement match this demo.

The discussion identifies valid architectural risks.
However, the current sibling checkout already contains authorization and semantic search components.
The demo does not use those components for its banking query path.
Do not describe missing demo integration as proof that every Helios deployment lacks these features.

## Assessment and evidence

The supplied discussion contains citation placeholders without linked source material.
Treat its claims as review inputs, not independently verified meeting quotations.
This assessment uses the inspected local source at sibling revision `83ac412` plus its working tree.
The observability extension remains uncommitted in that sibling checkout.
Source presence does not establish deployed enforcement or successful live acceptance.

| Concern | Finding in this demo | Finding in the sibling checkout | Consequence |
| --- | --- | --- | --- |
| User permissions | Optional shared workspace token; shared Trino connection; no verified caller identity reaches the database. | Resource authorization, physical-data policy and delegated Impala execution exist. | Integrate identity and policy into every demo data path. Validate Trino enforcement separately. |
| Full metadata prompts | Banking planning serializes the entire approved document, then rejects context above 40,000 characters. | MCP exposes lexical `search_semantics`. Observability retrieves selected definitions. | Add authorization-filtered retrieval for banking and bound dependency expansion. |
| Session context | Each LangGraph request starts fresh; no conversation ID or durable checkpointer exists. | Signed delegation can carry session and semantic revision identifiers. This alone does not prove coherent conversation memory. | Add explicit, scoped conversation state and release pinning. |
| Post-retrieval analytics | Python already computes log/metric findings and charts. There is no general analytics sandbox, forecasting or persisted analysis workflow. | The inspected query tool compiles and returns warehouse results. | Extend bounded analysis only after identity and retrieval controls. |

The demo does not hardcode a root/admin Trino username.
It accepts the operator's configured username; its actual database grants were not inspected.
Therefore, the root/admin credential claim remains unverified for this instance.
The verified problem is missing per-caller enforcement.

The inspected MCP semantic-search entry point checks model-level semantic access.
That check alone does not prove table, field or row policy filtering for every returned definition.
The demo integration must test those boundaries explicitly.

The demo planner selects typed semantic requests; Helios compiles SQL.
The planner does not directly supply arbitrary SQL for execution.
SELECT validation, approved source checks and result limits reduce execution risk.
They do not enforce user-specific row or column access.

Relevant source:

- [Demo authentication and routes](app/main.py)
- [Demo full-model planner context](app/planner.py)
- [Demo compilation and shared Trino execution](app/semantics.py)
- [Demo source discovery and preview](app/source_workflow.py)
- [Demo reference-query validation](app/semantic_workflow.py)
- [Request-local graph](app/orchestration.py)
- [Existing computed analytics](app/analysis.py)
- [Helios authorization](../../helios/shared/helios_core/authz/permissions.py)
- [Helios physical-data authorization boundary](../../helios/shared/helios_core/data_authorization.py)
- [Helios semantic search and delegated query execution](../../helios/apps/helios/mcp/server.py)
- [Helios delegated Impala engine](../../helios/shared/helios_core/engines/impala.py)
- [Existing operational context retrieval](../../helios/shared/helios_core/observability/context.py)

## Target architecture

```text
Verified caller + question + conversation
                    |
        authorize model and metadata scope
                    |
     retrieve relevant semantic definitions
                    |
       expand approved dependencies within budget
                    |
            typed semantic planning
                    |
     Helios compile + SQL/resource authorization
                    |
       database-enforced caller access
                    |
      bounded results + computed analytics
                    |
      approved output + scoped conversation state
```

The shared release provides consistent knowledge across conversations.
Each conversation stores only its selected context and explicit follow-up state.
Authorization applies before metadata reaches a model and again before source execution.
Operational and banking releases remain separate unless reviewed mappings connect them.

## M1 — Authorized, bounded semantic query

Application retrieval and caller controls are implemented. Database enforcement and preparation adapters remain required for M1 acceptance.
Deliver identity enforcement and metadata retrieval together before claiming secure multi-user operation.

### M1a. Caller and execution boundary

1. Add a server-verified caller context with subject, permitted sources, model scope and policy revision.
2. Obtain identity from the trusted authentication boundary; reject caller names supplied as ordinary query fields.
3. Reuse Helios action/resource policy contracts where practical.
4. Add a Trino authorization adapter that can confirm database enforcement for the mapped caller.
5. Deny multi-user live execution when that adapter cannot confirm enforcement.
6. Apply authorization to discovery, previews, profiles, semantic inspection, compilation and reference-query validation.
7. Restrict model activation, connection settings and release publication to explicitly authorized operators.
8. Record the caller, permitted assets, policy decision, release hash and execution identity in sanitized audit records.

Do not treat a Trino username header alone as verified delegation.
Validate the deployed authentication, delegation and database access-control configuration together.
Helios's Impala delegation implementation does not automatically provide Trino delegation.
An optional Impala route would require an explicit scope decision; retain Trino for this demo.

A single-operator demonstration may use a restricted, read-only service account.
Label that mode clearly; it does not demonstrate user-level isolation.
Do not silently fall back to that account when caller delegation fails.
Do not infer account safety from its name or from SELECT-only application checks.

Acceptance:

- Two verified test principals have different source and field permissions.
- Each principal receives only permitted metadata and source results.
- Denied requests never invoke planning or execution for restricted resources.
- Database integration tests prove the effective identity and actual row/column restrictions where configured.
- Settings, previews and reference validation cannot bypass the same boundary.
- Missing identity, unavailable enforcement and forged identity inputs fail closed.

Policy fixtures prove application behavior only.
Database integration evidence is required before claiming platform enforcement.

### M1b. Semantic metadata retrieval

1. Build a release-versioned index over datasets, fields, metrics, aliases and relationship descriptions.
2. Filter eligible metadata by caller permissions before ranking candidates.
3. Reuse Helios search concepts through a small adapter; avoid importing the MCP server and its runtime globals.
4. Start with deterministic lexical ranking; add semantic retrieval only if measured recall requires it.
5. Expand selected metrics into required fields, source datasets and approved join relationships.
6. Include filters, dimensions and types needed for compilation.
7. Send the selected semantic bundle to the planner instead of the complete document.
8. Validate requested identifiers against the selected bundle and current permissions before compilation.
9. Recheck compiled physical resources and policy before execution.
10. Display retrieved definitions, selection reasons, release identity and context size in the execution trace.

Keep the complete approved document server-side for integrity checks and compiler compatibility.
Do not copy only matching descriptions and lose metric expressions or join keys.
Permission-sensitive metadata must not enter prompts, browser responses, caches or audit output without authorization.
No-match or ambiguous retrieval must request clarification rather than send the full model.

Initial configurable limits:

- Five source datasets and 100 fields per planning bundle.
- At most 24,000 serialized context characters, within the existing 40,000-character rejection boundary.
- Dependency expansion must fit all limits; otherwise, request a narrower question.
- Cache keys include caller scope, policy revision, source binding and release hash.
- Release or permission changes invalidate affected cache entries.

These are proposed demo limits, not measured model token capacities.
Record serialized size and label token estimates when an exact tokenizer is unavailable.

Acceptance:

- Generate an isolated catalog with 2,000 tables and 40 fields per table.
- Use at least 40 reviewed questions covering aliases, metrics, joins, ambiguity and denied resources.
- Target at least 95% required-definition recall on answerable questions.
- Require zero restricted definitions in planner input or returned explanations.
- Require every planning bundle to fit the configured limits.
- Record retrieval latency, prompt size and query correctness against the full-model baseline on small comparable cases.
- Target warm-index retrieval p95 below 500 ms on the documented development machine.
- Test cold indexing separately and report its time and memory use.

Latency and recall figures are acceptance targets; they have not been measured.
Retrieval quality must preserve correct compilation and source-reference results.
An empty or truncated bundle is not a successful optimization.

## M2 — Scoped multi-turn context and evidence navigation

1. Add server-issued conversation identifiers bound to the verified caller.
2. Store release hashes, selected definitions, filters, time scope and prior result references.
3. Resolve follow-ups such as “same period for the other service” into explicit typed changes.
4. Reauthorize every turn; a conversation does not preserve revoked access.
5. Pin semantic revisions and disclose newer releases before explicit context refresh.
6. Bound conversation size, lifetime and retained turns.
7. Persist structured state when restart continuity is required; avoid storing credentials or unrestricted raw logs.
8. Apply result-reference expiry and invalidate references after source or permission changes.

Use common approved releases across conversations to avoid knowledge fragmentation.
Keep each conversation's task state separate to avoid mixing unrelated questions.
Raw chat history must not become the only query-state representation.

Integrate the previous evidence-navigation milestone here.
Add document-ID lookup, bounded pagination and aggregate-to-log drill-down using authorized result references.
Keep optional surrounding events visibly separate from exact matches.
A browser-supplied result ID must not grant access to another caller's result.

Acceptance:

- Multi-turn fixtures preserve intended filters and explain explicit changes.
- Another principal cannot read or reuse the conversation or result references.
- Revocation prevents replay of earlier results and retrieval caches.
- Release refresh cannot silently change a previous answer's semantic basis.
- Independent reference results verify drill-down counts and original-event identity.

## M3 — Controlled post-retrieval analytics

Advanced analytics extends the demo's product scope beyond semantic compilation.
Its absence does not invalidate Helios as a semantic model and compiler component.

Extend the existing computed findings before introducing model-generated programs.
Start with approved methods such as trend comparison, missingness checks and bounded correlation.
Each method declares input types, minimum samples, units and statistical limitations.
Require explicit user selection or a validated typed analysis plan.

For Python analytics, add a separate execution boundary with enforced containment.
The current FastAPI process is not a security sandbox.
Use an isolated worker with denied network egress, bounded CPU/memory/time and restricted temporary storage.
Pass only authorized, bounded input through server-controlled references.
Permit only approved analysis templates in the first increment.
Do not enable arbitrary model-written Python as an incidental extension.

Define the data-egress policy explicitly.
Raw analytical inputs stay inside the approved execution boundary.
Only approved summaries and artifacts may reach the browser or an inference endpoint.
The current finding-ranking step sends computed fact text to the configured model.
Disable that transmission when the selected data policy prohibits result-derived model input.
Metadata also requires classification before transmission to external inference.

Forecasting follows method validation and backtesting.
Display sample sufficiency, uncertainty and holdout performance before presenting predictions.
Reject forecasting when evidence is insufficient.

Optional persistence saves authorized result artifacts, method version, source scope and semantic release identity.
Use explicit save actions, access checks, retention and deletion rules.
Persistence writes only to approved application storage; source systems remain read-only.

Acceptance:

- Independent reference calculations verify approved methods.
- Worker tests reject network access and terminate excessive resource use.
- Result-derived data cannot reach prohibited model endpoints.
- Artifact reads, saves and deletions enforce caller permissions.
- Invalid methods and insufficient samples return explanations without invented analysis.

## Delivery and verification order

1. Implement M1a contracts, verified identity and deny-by-default execution adapters.
2. Implement M1b retrieval, dependency closure and scale fixtures.
3. Run the existing regression suite and new authorization/retrieval tests.
4. Complete platform identity and live query reconciliation before multi-user claims.
5. Implement M2 conversation state and evidence navigation.
6. Implement M3 approved analytics and enforced worker containment.
7. Run isolated browser workflows and verify visible restrictions and context selection.
8. Rebuild and smoke-test the deployment image after acceptance.

Live connectivity and browser execution remain open acceptance gates.
Their earlier failures do not prevent fixture-based implementation.
No new live acceptance or scale benchmark ran during this assessment.
At assessment time, the last backend result was 122 passing tests from the preceding increment.
The subsequent foundation starter passed 132 tests; its evidence is recorded in VERIFICATION.md.

## Ownership and scope

The demo owns request identity integration, orchestration, Trino enforcement adapters, conversation state and evidence UI.
Helios supplies approved semantic definitions, reusable policy contracts and compilation.
Shared retrieval utilities should move upstream only after the adapter boundary is tested.
No sibling code was changed by this assessment.

Update architecture.md for implemented data flows and trust boundaries.
Update component-api.md for implemented identity, retrieval and conversation contracts.
Update user-guide.md for supported workflows and visible restrictions.
Update development.md, TODO.md, IMPLEMENTED_DEMO.md and VERIFICATION.md with actual implementation evidence.
Keep proposed controls distinct from completed capabilities and RFP acceptance.
