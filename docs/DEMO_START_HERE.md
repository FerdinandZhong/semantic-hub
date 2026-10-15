# Start here: Semantic Hub

**External agent consumer milestone — 15 October 2026:** Semantic Hub now exposes a dedicated read-only consumer API and twelve MCP tools.
Published inventory, versions, definitions, metadata, ontology, lineage, frozen document evidence, keyword search, and configured embedding search are available.
Embedding vectors use Lance storage. Typed compilation and bounded sample execution require a pinned version and expiring context bundle.
The Playground remains a lightweight model-validation surface. External agents own advanced interpretation and their data-engine tools.
The [API contract](semantic-hub-consumer-api.md), [MCP package](../apps/semantic-hub-mcp/README.md), and [CAI workflow](semantic-hub-agent-studio-workflow.md) describe the handoff.
The [Chinese workflow](semantic-hub-agent-studio-workflow.zh-CN.md) provides the same demo setup.
Ten backend tests and twelve MCP tests passed. The [live MCP check](semantic-hub-mcp-verification.json) passed through actual stdio and HTTP, including OpenAI embeddings and 74.1% execution.
The consumer API is running locally on port 8096. Hosted CAI deployment and production identity integration remain unverified.
The lightweight Harness separately passed 7/7 pharma cases and 38/40 finance/power cases. Two Singapore-date interpretations remain imperfect.
These Harness limits do not affect deterministic MCP retrieval, compilation, or explicitly typed sample requests.
Next: deploy the consumer API to a CAI-reachable HTTPS address and rehearse the prepared workflow with a machine credential.

Originally prepared 10 October 2026; current navigation and status reviewed 14 October 2026.
This entry point covers the local demo and its implementation references.
See the [Playground agent architecture](playground-agent-architecture.md) for the official DeepSeek Harness integration and editable diagram.
Use the [pharmaceutical demo story](pharma-intelligence-demo-story.md) for a narrated presentation and exact UI steps.
It now contains two independent stories: page 14 evidence for an existing model, and pages 4–5 facts for a new model.
Both include reference SQL and published-version sample queries.
See the [Chinese version / 中文版](pharma-intelligence-demo-story.zh-CN.md) for Chinese presenter narration.
Use the [finance customer story](finance-customer-demo-story.md) for payment semantics, reviewed HSBC evidence, publication, and queries.
Use the [power customer story](power-customer-demo-story.md) for measured energy, quality rules, lineage, and queries.
Each story contains ten supported questions and ten unsupported-request checks.
The earlier synthetic finance document story is archived; its uploads were removed.
It includes plans, datasets, code references and static UI assets.
The runtime supplies a typed registry, local SQL execution, and a Semantic Hub landing page across local source models.
Open a source's details to inspect its connection and versions, then select **Open Studio**.
**Configure data sources** supports local datasets, Iceberg, Trino, and Atlas profiles.
Remote profiles still require import adapters before semantic authoring or execution.

The sidebar **Model configuration** page provides independent draft, playground/query, and optional embedding profiles.
Draft and playground profiles can inherit the launch configuration; embeddings default to disabled.

The [supporting-material library](supporting-materials.md) imports TXT/MD, PDF, DOCX, PNG, and JPEG documents across local source models.
The [visual workflow](visual-document-facts.md) extracts one to six selected physical pages from PDFs containing at most 32 pages.
GPT-4o proposes rows from images and scanned pages; human review creates a new typed fact source and semantic draft.
OpenAI text embeddings use local Lance-format storage.
See the [visual verification record](visual-document-verification.json) for acceptance progress.
The text-analysis path analyzes every extracted section, validates exact text citations, and proposes keyword or optional embedding links.
Visual quotations remain unverified until a reviewer checks the original page.
Reviewers approve selected links before applying cited evidence to a draft.
Archived attachments retain document revision, original checksum, target links, and review attribution.

Read [local runtime setup and boundaries](demo-runtime.md) for commands and explicit sample review.
The [local Semantic Studio and Hub](context-builder.md) support source inspection, canvas editing, SQL validation and version review.
Use the [reference SQL examples](demo-reference-sql.md) to validate the four starter metrics.
The fifth model, [pharmaceutical intelligence](pharma-intelligence.md), has six additional metrics and separate validation queries.
It uses curated public facts and remains separate from synthetic pharma batch quality.
Read the [documentation map and alignment review](DOCS_ALIGNMENT.md) for reused designs and remaining gaps.
The [illustrated builder walkthrough](walkthrough/semantic-builder/index.html) is an earlier capture; its screenshots predate the current Hub and document workflow.
Batch decisions apply to the exact saved revision. Publication and query activation remain separate actions.

The [Model playground](model-playground.md) now uses bounded retrieval and typed requests against published versions.
Execution requires an explicit run. AI can combine one reviewed metric with published document evidence; arbitrary SQL remains outside this flow.
Finance combined questions currently encounter relationship clarification; its prepared demo uses separate metric and document questions.

Read the [semantic foundation progress and consumer handoff](SEMANTIC_FOUNDATION_STATUS.md) for the current building and search status.
The [indexed retrieval implementation](semantic-retrieval.md) records the new agent tools, consumer export and measured latency.
It identifies the remaining adapters for UOB and Semantic Guardrails, including the distinction between context packages and Ossie documents.

## Required reading

1. [Reusable demo plan and confidence review](reusable-helios-demo-plan.md).
2. [Bounded semantic search and metadata use](semantic-retrieval-and-metadata-plan.md).
3. [Contribution guidelines and upstream milestones](demo-sector-contribution-plan.md).
4. [Sector datasets, provenance and commands](sector-demo-datasets.md).
5. [Earlier NL-to-SQL research review](demo-handoff/research/nl-to-sql-literature-review.md).

The earlier plan understated the importance of retrieval. Milestone 1B now makes it a mandatory acceptance gate.
Do not send the full catalog to the LLM, including through `describe_model`, tool results or conversation history.

## Assets in this repository

- `apps/helios-ds-generation/src/helios_ds/sector_demo/`: deterministic builders and public-source import adapters.
- `apps/helios-ds-generation/fixtures/sectors/v1/`: finance, manufacturing, pharma, power, and pharmaceutical intelligence CSV/document packs.
- `apps/helios-ds-generation/tests/test_sector_demo.py`: seven offline acceptance tests.
- `apps/helios-ds-generation/workbench/fetch_sector_sources.py`: public-source fetch command.
- `ui/sp-group-screenshot-samples/`: five standalone power-sector UI examples and content/browser checks.
- `docs/demo-handoff/reference/uob/app/`: selected query, metadata, retrieval and preparation code to adapt.
- `docs/demo-handoff/reference/uob/tests/`: selected behavior tests to adapt.
- `docs/demo-handoff/reference/uob/static/`: original workspace UI components and styling reference.
- `docs/demo-handoff/reference/uob/docs/`: design, architecture, API, metadata and hardening references.
- `docs/demo-handoff/reference/aml/`: combined document/structured-data evidence patterns.
- `docs/demo-handoff/reference-manifest.json`: source paths and copied-file checksums.

The reference source is intentionally not installed or runnable as another UOB application.
Adapt useful contracts into Helios's existing components.
Archived documents retain some original repository-relative links; use this entry point for the portable handoff paths.
No operator configuration, credentials, conversations or runtime caches are included.

## Existing Helios components to extend

- `apps/helios/console/main.py`: existing FastAPI console and routes.
- `apps/helios/console/conversation.py`: existing model/tool conversation loop.
- `apps/helios/mcp/server.py`: semantic search, compilation, execution, document evidence and entity claims.
- `apps/helios/console/trace_documents.py`: document-to-query evidence traces.
- `shared/helios_core/compiler/compiler.py`: semantic compiler.
- `shared/helios_core/index/evidence.py`: document index/search.

The compiler currently uses one fact dataset per request and inner joins.
The legacy MCP document tools authorize a model but do not pass that model into evidence-search filtering.
They remain disabled in the local demo; the new supporting-material matcher is a separate preparation workflow.
Implement explicit pack/index isolation before claiming cross-pack retrieval isolation.

## Original implementation sequence (historical)

Registry, local Studio, reviewed exports, and shared indexed retrieval now exist.
M2B published-model playground and M3A supporting-material preparation are complete locally.
M3B authorization-scoped passage queries and combined SQL/document answers remain open.
Use [current foundation status](SEMANTIC_FOUNDATION_STATUS.md) for remaining integration work.

1. Inspect current git status and local instructions. Preserve existing observability work and README changes.
2. Add the typed runtime pack registry and generic local SQL adapter.
3. Connect the shared query UI to the existing Helios console/conversation services.
4. Implement metadata indexing, bounded semantic bundles and enforced bundle binding before LLM query acceptance.
5. Extend reviewed semantic authoring and combined table/document queries.
6. Measure probing, verification and reviewed-memory improvements on held-out questions.
7. Validate Docker and browser behavior using the same pack contract.

Example acceptance: launch power, resolve “measured electricity consumption” to its approved metric, retrieve only required definitions and execute bounded SQL.
Then launch pharma and verify that no power definitions, documents or conversation memory appear.

## Current verification and limitations

Seven sector fixture tests passed before this handoff.
Four existing Helios compiler tests and three document-trace tests passed during the plan review.
Static power-page content and JavaScript checks passed.
The fixture catalog remains separate from the new runtime registry at `apps/helios/demo-packs.json`.
`start_demo.py` selects a pack and rejects mismatched review or saved-settings bindings.
Source semantic models remain drafts. Local context versions require explicit validation, review and activation.
The original four packs are source-informed synthetic.
The fifth pharmaceutical intelligence pack contains curated FDA/EFPIA public facts.
The new runtime page passed desktop and mobile browser checks for all four packs.
Original static-page export and logo embedding remain separate pending work.
A [local retrieval benchmark](semantic-retrieval.md#verification) now covers 80,000 fields and 40 labeled questions.
The [Model playground](model-playground.md) now interprets questions into bounded typed requests against published versions.

Focused material verification passed 19 parser tests, 13 library tests, and 11 API tests.
Supporting-material browser checks passed at 1440 and 390 pixels.
The earlier text-material regression run passed 141 backend tests. Live GPT-4o analysis produced six cited statements; text-embedding-3-small matching found finance and manufacturing candidates. Repeated matching made zero embedding calls. These checks do not establish production acceptance.
Next work covers registry and UOB/Guardrails adapters, independent model IDs, authorized passage queries, retrieval evaluation, and live source imports.
Bounded image/scanned-PDF extraction and reviewed fact-source creation now work locally.
The final regression passed 207 tests, including the corrected pharmaceutical pack.
Live OpenAI image/PDF extraction and Lance reuse passed. Desktop/mobile workflow checks also passed.
Enterprise identity, general extraction accuracy, combined answers, and downstream deployment acceptance remain open.

Use an explicit `HELIOS_ROOT` for older compiler tests that assume a pre-monorepo fixture path.
Use `-p no:cacheprovider` when running tests against a read-only checkout.
Do not commit, push or deploy unless requested.
