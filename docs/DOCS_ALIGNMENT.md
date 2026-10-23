# Documentation alignment and reuse review

Reviewed: 13 October 2026. Scope: this Helios working tree and materials under `docs/`.

**The main architecture is aligned, but not every documented capability is integrated into local Studio.**
The repository contains current implementation guides, older design proposals, separate subsystem runbooks, and preserved evidence.
Their completion states must not be combined into one product claim.

## Current end-to-end story

```text
Hub source → Studio proposal/edit → validate → item review → immutable version
                   |                                           |
          document/record canvas                        publish + export
                                                               |
                                            consumer adoption adapter (open)
                                                               |
                                            bounded retrieval → agent query
```

The [Model playground](model-playground.md) interprets questions into bounded typed requests against published versions.
It retrieves relevant definitions, shows SQL evidence, and requires an explicit run.
The [supporting-material library](supporting-materials.md) prepares reviewed document links and applies them to drafts.
Its optional embeddings rank proposed links; combined SQL/document answers remain open.
The shared retrieval service and authenticated MCP query loop exist independently.
Local publication does not automatically register the release in that MCP store.

## Material-to-implementation map

| Materials | How they are used | Alignment or remaining work |
| --- | --- | --- |
| [Demo entry point](DEMO_START_HERE.md), [runtime](demo-runtime.md), [builder](context-builder.md) | Current local operating instructions | Updated Hub/query routes, document workflow, reference SQL, review and pagination guidance |
| [Supporting materials](supporting-materials.md), [Model playground](model-playground.md) | Completed M3A document preparation and M2B published-model query flow | Cited analysis, optional embedding matching, review, provenance, and bounded typed execution; scoped passage answers remain M3B |
| [Foundation status](SEMANTIC_FOUNDATION_STATUS.md) | Consumer contract and implementation boundaries | Local building and exports exist; downstream adoption remains separate |
| [Reusable demo plan](reusable-helios-demo-plan.md), [contribution plan](demo-sector-contribution-plan.md) | Ownership, pack isolation, milestones and acceptance | Registry, Studio and retrieval delivered locally; original milestone text now carries explicit historical context |
| [Retrieval plan](semantic-retrieval-and-metadata-plan.md), [implementation](semantic-retrieval.md), [benchmark](retrieval-benchmark.json) | Offline indexing, lexical ranking, dependencies, scoped cache, token budgets | Shared FTS5 semantic retrieval exists; supporting-material matching adds optional embeddings separately; no many-model production performance claim |
| [Sector datasets](sector-demo-datasets.md), [reference SQL](demo-reference-sql.md) | Four typed local fixtures and reproducible starter validation | Synthetic fixtures; public-source import acceptance remains separate |
| [Artifact assessment](builder-artifact-assessment.md), [builder validation](builder-validation.json) | Recorded artifact-quality checks and test evidence | Dated local evidence; not proof of enterprise ontology correctness or current production deployment |
| [Proposal](builtin/helios-compat/console-propose.md), [review](builtin/helios-compat/console-review.md), [runs](builtin/helios-compat/console-runs.md), [two-table walkthrough](builtin/helios-compat/helios-walkthrough.md) | Harvest/profile/propose/review concepts and evidence-first authoring | Discovery-run UI differs from local Studio; scope notes added; legacy flat artifact path identified |
| [Model artifacts](../external/helios/docs/model-artifacts.md) | Stable model identity and immutable published revisions | Authenticated artifact store differs from Studio SQLite releases; adoption adapter still needed |
| [Model graph API](builtin/helios-compat/model-graph-api.md) | Graph projection and authorization contract | React graph API is separate from local source graph and document canvas composition |
| [Ontology authoring](builtin/helios-compat/ontology-authoring.md), [burndown](../external/helios/docs/ontology-burndown.md), [deployment](../external/helios/docs/ontology-deployment.md) | Reuse graph/mapping types and draft/validate/publish concepts | Studio emits source-structure proposals; LinkML operation editor, copilot, trial crawl and ontology activation are not delivered by Studio |
| [Crawler analysis](../external/helios/docs/crawler-analysis.md), [guide](../external/helios/docs/crawler-guide.md), [burndown](../external/helios/docs/crawler-burndown.md), [configurable plan](../external/helios/docs/crawler-configurable.md) | Existing extraction, entity resolution, claim and provenance mechanisms | Separate crawler code exists; the shared material parser supports text PDF and DOCX without invoking it; OCR remains external |
| [Without a lakehouse](../external/helios/docs/helios-without-a-lakehouse.md) | Document-first architecture proposal | Unlinked attachments provide context, not a complete documents-only entity/claim platform |
| [MCP server](builtin/helios-compat/mcp-server.md), [Talk architecture](builtin/helios-compat/talk-to-your-data-architecture.md) | Governed query tools, bounded loop and result provenance | Updated obsolete tool lists and proposal fallback claims; bundle enforcement now documented |
| [Security](builtin/helios-compat/SECURITY_ARCHITECTURE.md), [operational metadata](builtin/helios-compat/operational-metadata.md), [database runbook](../external/helios/docs/helios-metadata-database.md) | Identity/resource/data boundaries, state and audit requirements | Local reviewer names remain attribution only; API owns audit retention cleanup; do not infer enterprise identity from local review |
| [UI backend contract](builtin/helios-compat/ui-backend-contract.md), [networking](builtin/helios-compat/ui-api-networking.md), [deployment](builtin/helios-compat/ui-deployment.md), [migration](builtin/helios-compat/legacy-ui-migration.md) | Authenticated React/API boundary and deployment design | Corrected pre-monorepo paths; local Jinja/JS Studio remains separate; old runtime build files are absent from this checkout |
| [Observability context](observability-semantic-context.md) | Existing reviewed dictionaries and native-tool context | Separate package; not a local Studio source type or SQL semantic index |
| [DS generation](../external/helios/docs/helios-ds-burndown.md), [DS evaluation](../external/helios/docs/helios-ds-evaluation.md), [ADR 0001](../external/helios/docs/adr/0001-helios-ds-review-edit-approve.md) | Reproducible assets, review lineage and evaluation isolation | Generator review is distinct from semantic release approval; deferred generator tasks stay deferred |
| [UOB design](demo-handoff/reference/uob/docs/DESIGN.md), [architecture](demo-handoff/reference/uob/docs/architecture.md), [API](demo-handoff/reference/uob/docs/component-api.md) | Source-scoped preparation, compact UI and connector boundaries | Adapted concepts, not an installed second UOB app; Cloudera/blue local design is the later accepted direction |
| [UOB foundation](demo-handoff/reference/uob/docs/FINANCIAL_FOUNDATION.md), [hardening](demo-handoff/reference/uob/docs/HELIOS_HARDENING_PLAN.md), archived `app/`, `tests/`, `static/` | Retrieval, caller binding, financial fixtures and workflow references | Shared retrieval adapts the bounded-contract approach; UOB routing/settings are not imported into Helios core |
| [AML investigation](demo-handoff/reference/aml/semantic_investigation.md), [controls](demo-handoff/reference/aml/kyc_semantic_controls.md), [audit example](demo-handoff/reference/aml/kyc_audit_and_multimodal_demo.md) | Separate source facts, document assertions, conflicts and retained evidence | Reused evidence principles; AML controls, scoring, OCR and regulation-specific workflows are not part of local Studio |
| [NL-to-SQL review](demo-handoff/research/nl-to-sql-literature-review.md) | Bounded context, explicit verification and evidence-supported repair goals | Retrieval and deterministic checks exist; query-time probing, reviewed memory, targeted repair and held-out improvement evaluation remain open |
| [Overview slides](../external/helios/docs/Helios-Overview.pptx), [deck notes](Helios-Overview-notes.md), [walkthrough assets](walkthrough/README.md) | Product explanation and historical demonstrations | Deck MCP slides and earlier UI captures need refresh before presenting them as current behavior |
| [Reference manifest](demo-handoff/reference-manifest.json), [package manifest](demo-handoff/package-manifest.json) | Provenance for the original copied handoff | Archived copies retain original hashes; package manifest remains a historical baseline, not a current release manifest |

## Concrete implementation evidence

The map above was checked against these source boundaries:

- [Runtime registry](../shared/helios_core/demo/registry.py) and [typed local engine](../shared/helios_core/demo/local.py).
- [Source connections](../shared/helios_core/demo/connections.py) and [Hub routes](../apps/helios/console/demo_hub.py).
- [Context validation and release gates](../shared/helios_core/demo/context.py).
- [Supporting-material library](../shared/helios_core/demo/materials.py) and [bounded document parser](../shared/helios_core/demo/document_parser.py).
- [Builder artifacts and document keys](../shared/helios_core/demo/builder_artifacts.py).
- [Studio navigation and review](../apps/helios/console/static/demo-context.js) and [canvas](../apps/helios/console/static/demo-canvas.js).
- [Retrieval index](../shared/helios_core/retrieval/index.py), [service](../shared/helios_core/retrieval/service.py), [MCP](../apps/helios/mcp/server.py), and [conversation tool allowlist](../apps/helios/console/conversation.py).
- [Existing crawler](../apps/helios/crawler/crawl.py), [ontology parser](../shared/helios_core/ontology/parser.py), and [source mappings](../shared/helios_core/ontology/mapping.py).

This audit inspected source and local artifacts; it did not deploy the separate enterprise services.
It did not revalidate external papers, benchmark citations, or sibling applications' current deployments.

## Highest-priority unused capabilities

1. Connect published Studio packages to the authenticated model registry and consumer adapters.
2. Establish independent model IDs; local models currently use source-connection identity.
3. Enforce document model/source/caller scope before enabling M3B combined SQL and passage answers.
4. Reuse crawler provenance and extraction through a bounded Studio adapter, rather than duplicating crawler logic.
5. Treat enterprise ontology authoring as a separate increment using the existing LinkML and mapping services.
6. Implement the remote Iceberg, Trino, and Atlas import adapters behind the existing connection profiles.
7. Evaluate authorized passage retrieval and hybrid matching recall before claiming retrieval improvements or production scale.
8. Evaluate query-time probing, repair and reviewed memory on held-out questions before claiming agent improvements.

Optional reference-query generation is also a UX follow-up, not an implemented approval bypass.
Generated verification SQL must retain provenance and human review because it can repeat the original metric error.

## Checks and preserved evidence

- All four SQL examples executed against local serving fixtures with the documented results.
- All 47 archived reference files matched `reference-manifest.json` during the audit.
- The original package manifest contains 139 entries. Three evolving plan files already differed before this documentation update.
- Those files were `DEMO_START_HERE.md`, `reusable-helios-demo-plan.md`, and `semantic-retrieval-and-metadata-plan.md`.
- The manifest was preserved rather than rewritten to conceal changes after the handoff.
- Earlier screenshots, reports, the PDF and the deck retain their historical evidence status.
- Current supporting-material checks passed 19 parser, 13 library, and 11 API tests.
- Supporting-material browser checks passed at 1440 and 390 pixels.
- The final regression run passed 141 backend tests. Live GPT-4o analysis produced six cited statements; text-embedding-3-small matching found finance and manufacturing candidates. Repeated matching made zero embedding calls. These checks do not establish production acceptance.
- The approval dialog layout was checked at 1440, 768 and 390 pixels without submitting a decision.

The docs now distinguish reusable design inputs from features that actually run in the local demo.
Future release evidence should identify a reviewed commit or package hash, not rely on this mutable working-tree audit.
