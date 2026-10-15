# Reusable Helios semantic and query demo

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

**Playground Harness increment — 15 October 2026:** The query coordinator now uses the official DeepSeek Harness SDK with the existing GPT-4o configuration.
Skills, bounded tools, and release-scoped audit memory are separate modules.
Server checks cover exact cohort pairs and typed dates. Missing periods return no data without a query plan.
The [architecture and diagram](playground-agent-architecture.md) describe the implemented flow and its limits.
Use the linked Harness acceptance reports for current results; the previous forty-case report below describes the earlier planner.
Next: enterprise authorization, operational retention, durable jobs, and downstream agent integration.


**Finance and power customer acceptance — 15 October 2026:** Two customer stories now include ten supported queries and ten unsupported requests each.
The [finance story](finance-customer-demo-story.md) uses synthetic payments with reviewed HSBC field evidence.
The [power story](power-customer-demo-story.md) explains measured energy, quality exclusions, Singapore dates, and meter lineage.
The 52-test regression suite passed. Four focused tests also passed in the refreshed local environment.
All forty live GPT-4o cases passed: twenty SQL results matched independent references, and twenty unsupported requests returned clarification without plans.
The [verification](customer-query-verification.json) records the exact questions, SQL, outputs, and limitations.
Planning now selects explicit fields before dependency retrieval, preventing unrelated finance keywords from introducing ambiguous joins.
Compiler-generated DATE literals execute through a narrow local-engine allowance. Arbitrary casts remain blocked.
These checks used temporary releases. Live drafts, reviews, publications, and document links were not modified.
The HSBC document questions remain optional rehearsals outside this forty-case acceptance set.

Updated: 15 October 2026. Status: local M2B and M3A completed; a local M3B document-answer increment is implemented. Enterprise authorization, cross-model answers, and consumer integration remain open.

**Finance evidence preparation:** [English](finance-unstructured-demo-story.md) and [Chinese](finance-unstructured-demo-story.zh-CN.md) guides now cover synthetic payment definitions, FX evidence, a settlement memo, and an image chart.
The local library now contains the original HSBC guide; the synthetic finance PDF/PNG uploads were removed at the user's request.
Use the [real finance source guide](finance-real-document-sources.md) for the active document demo. Existing finance source records, drafts, and versions were preserved.
Isolated publication and saved-metric reconciliation passed. Explicit-field planning now fixes unrelated finance join expansion. Rehearse combined document questions against the exact approved passages.

**Supporting-material UX update:** Page analysis now precedes two independent model actions.
Users can create a semantic model and attach evidence from the same results.
Repeat extraction automatically creates a document revision, preserving earlier reviews and models.
Matching can use analyzed pages or all extracted text. English and Chinese demo instructions follow this flow.

The current [pharmaceutical demonstration](pharma-intelligence-demo-story.md) has two independent stories, also available in Chinese.
Page 14 supplies reviewed scope evidence for an existing model; pages 4–5 create a separate nine-observation source.
Prepared SQL covers six existing metrics and ten document-derived metrics.
The isolated run checks validation, publication, and saved-metric execution for both stories.
Removing authoring-only seed metadata from generated serving models fixes the publication-to-playground handoff for these sources.
Live user approvals and publication remain presenter actions. Published linked-passage answers are available; combined one-metric/document answers are now implemented locally. General cross-model answers remain M3B work.
The registry, typed local adapter, Semantic Studio, and published-model playground are implemented locally.
The [supporting-material library](supporting-materials.md) adds revisioned documents, cited analysis, reviewed matching, and draft attachments.
The [pharmaceutical intelligence increment](pharma-intelligence.md) adds a fifth model and a unified Studio document workflow.
The [visual-document increment](visual-document-facts.md) adds reviewed image/scanned-PDF fact sources and embedded Lance vector storage.
See its [verification record](visual-document-verification.json) for acceptance progress.
See the [Model playground](model-playground.md) for the completed published-version query flow.
See [runtime setup and verification](demo-runtime.md); the broader milestones below remain the roadmap.
See [semantic foundation progress and consumer handoff](SEMANTIC_FOUNDATION_STATUS.md) for building, search and downstream integration status.
This plan extends the existing sector contribution and hardening plan.
The target is one reusable Helios application with selectable sector packs and a shared UI.
The earlier literature-search skill invocation applied only to the research task.
This revision reviews implementation feasibility against the local source.

## User requirements and ownership

1. Build reviewed semantic context for structured data and document-derived information.
2. Combine numerical results and document evidence in one query answer.
3. Reuse the workspace's visual design with a query-focused demo mode.
4. Select the synthetic dataset when launching the application.
5. Improve the agent workflow using the previously reviewed NL-to-SQL research.

Helios owns reusable semantic models, compilation and framework-independent query contracts.
Extend the existing Helios console with an optional demo presentation mode.
Its application owns presentation, pack selection and the orchestration of SQL and document retrieval.
Reuse existing MCP tools and conversation services behind the new interface.
Document ingestion adapters supply extracted content and provenance.
Helios compilation does not itself read PDFs or perform OCR.
Keep customer-specific workflows and optional platform integrations behind adapters.
The UOB application remains a consumer of reviewed Helios releases.
Do not maintain independently modified copies of the core.

```text
Selected dataset pack
        |
        v
Tables + documents -> entity links + reviewed definitions -> pinned release
                                                               |
                                                               v
Query UI -> relevant context -> clarify / probe -> Helios compile + validate
                                                               |
                                      +------------------------+------------------+
                                      |                                           |
                                 Bounded SQL                              Document retrieval
                                      |                                           |
                                      +------------------------+------------------+
                                                               |
                                                               v
                                                  Answer + source evidence
```

## Structured and document semantics

Structured models define entities, keys, grain, metrics, units, dates, filters and reviewed joins.
Extend the current single-table preparation workflow to reviewed multi-table models.
Do not treat free-text inclusion rules as executable SQL filters.
Validate that the actual compiled candidate applies required business rules.

Documents need stable document, version, page and chunk identifiers.
Retain original assets and checksums alongside extracted text.
Map document concepts to canonical structured entity identifiers.
Retain mapping evidence and review status. Ambiguous matches require review.

Use two complementary query paths:

- SQL joins approved document-derived assertion tables with operational tables for numeric or relational questions.
- Document retrieval supplies source passages for explanations and source-linked evidence.

An assertion includes entity ID, concept, typed value, unit, validity dates and source references.
It also includes extraction status and review status.
Conflicting assertions remain visible. Unknown values do not become confirmed facts.
Approved assertions can have an Ossie model. Raw document text remains in a retrieval index.
Ossie supplies structured semantics; the application links those semantics to the document evidence contract.
Do not assume Ossie already defines a complete document ontology or retrieval workflow.

Example: retrieve a batch's assay result through SQL and its deviation explanation from a linked report.
An asset query can combine torque measurements with a maintenance note through the same asset ID.
Power initially uses structured meter readings. Document support can follow when a suitable utility corpus exists.

## Reuse from AML

The actual sibling path is `../anti_money_laundry_blueprint`.
Its semantic investigation uses scoped inputs, pinned knowledge releases, canonical identifiers and retained source evidence.
Its KYC controls distinguish candidate evidence, conflicts, unavailable inputs and confirmed configured-control outcomes.
Reuse these contracts and testing ideas rather than its complete risk-scoring or investigation workflow.

Reference files:

- `docs/semantic_investigation.md`
- `docs/kyc_semantic_controls.md`
- `docs/kyc_audit_and_multimodal_demo.md`
- `semantic/aml_semantic_model.ossie.yaml`

AML-specific policies and legal applicability remain outside the generic Helios demo.
A simpler semantic layer can support the AML walkthrough without defining the new reusable layer's full scope.

## Query-focused UI

Reuse the existing shell, compact panels, navigation patterns, question area, charts and execution evidence.
The current local UI lands on Semantic Hub, following the later user-approved design.
Open source connection details and versions there, then enter Studio for that source.
The Model playground interprets source-specific questions into bounded typed requests against a published version.
It shows SQL evidence and requires an explicit run.
Connection configuration lives inside the Hub.
Model configuration provides three independent profiles: drafting, playground/query, and supporting-material embeddings.
NiFi and Observability are optional modules outside the initial Helios query demo.
Keep the running UOB application's existing modules intact.

Brand, title, example questions, source labels and units come from the selected pack.
Show the dataset, mode and pinned semantic version prominently.
Use one generic UI with configurable branding, including SP Group.
Preserve explicit sample labels and visible source failures.
No sample pack implies live acceptance or production authorization.

## Dataset pack and startup contract

Extend the staged fixture catalog into a validated runtime dataset registry.
Each entry declares its identifier, serving root, source manifest, document root and semantic releases.
It also declares the SQL adapter, retrieval adapter, branding, example questions and timezone.
Keep reference answers and evaluation labels outside runtime lookup roots.

Implemented launcher syntax; explicit sample review is required before execution:

```sh
python start_demo.py --dataset power --ui-mode query
python start_demo.py --dataset manufacturing --ui-mode query
```

Docker uses the same registry and launcher through environment variables or entrypoint arguments.
Mount a versioned dataset pack as read-only storage.
Startup selects one pack and validates paths, schemas, release hashes and required adapters.
Sample query execution uses a prepared local DuckDB database.
Remote lakehouse adapters use an explicit configured source and retain live authorization checks.

Explicit startup selection takes precedence over saved defaults.
Reject saved settings that bind a different dataset or semantic release.
Namespace drafts, releases, conversations, indexes and reviewed experience by dataset and version.
Changing packs starts a fresh scoped context. Never merge finance memory into power queries.
Do not turn the draft fixtures into approved releases automatically.
Provide separate preparation and reviewed sample-query stages.

## Research recovered for this task

The earlier review is `../gel_data_query_pilot/docs/nl_to_sql_literature_review.md`, updated 7 October 2026.
It covers AgentSM, SQLAgent, PV-SQL, ReEx-SQL, MIRA, ReToolSQL, DualSQL and complementary ReViSQL findings.
Academic MCP search tools are unavailable in this session.
The skill's preflight passed PubMed, CrossRef and arXiv endpoint checks.
Primary arXiv abstracts for the three priority papers were retrieved again on 10 October 2026.
No experiment was reproduced during this task.

1. [AgentSM](https://arxiv.org/abs/2601.15709): reuse structured execution experience to guide later questions.
2. [PV-SQL](https://arxiv.org/abs/2604.17653): probe specific database uncertainties and verify an explicit constraint checklist.
3. [MIRA](https://arxiv.org/abs/2608.06950): activate focused repair memory only when current evidence supports it.

These mechanisms motivate our design. They do not establish enterprise correctness or our demo's accuracy.
Scope reviewed experience by dataset, source snapshot, semantic release and authorization policy.
Review successful traces before publishing them as reusable examples.
Keep held-out questions and evaluation truth outside example retrieval.
Do not add reinforcement training as a dependency for the first reusable demo.

## Agent workflow

Extend the existing Helios conversation loop with typed tool contracts. Additional specialist agents require measured benefit.
Port useful validation and evidence-rendering behavior from UOB after checking equivalent Helios behavior.
Reuse this workspace's bounded retrieval, semantic requests, checksums, SQL checks and evidence rendering.
Replace finance-specific planning with dataset-independent contracts.

1. Resolve the selected dataset and current caller scope.
2. Retrieve relevant approved definitions and required join dependencies.
3. Clarify ambiguous metrics, entities, time windows or document mappings.
4. Use bounded read-only probes when a specific uncertainty remains.
5. Produce a typed semantic request within the supported Ossie scope.
6. Compile with Helios and validate objects, joins, filters, grain and execution limits.
7. Execute through a bounded source adapter and retain the result evidence.
8. Retrieve linked document passages when the question needs them.
   Document-first questions retrieve entity keys before compilation, then validate those keys against the selected model.
9. Apply a limited evidence-supported repair when a verified defect is found.
10. Render results and cite source evidence. Stop visibly when evidence is insufficient.

An executable query is not proof of semantic correctness.
Validate numbers against execution results instead of accepting model-generated values.
Bind candidate identifiers to SQL, dataset, session, source snapshot, policy and semantic version.
Revalidate these bindings before execution.
Set independent limits for context, probes, tool calls, execution time, rows and repair attempts.
Document-derived text is evidence, not an instruction to tools.

## Reviewed implementation sequence

| Milestone | Status reviewed on 13 October 2026 |
| --- | --- |
| 0: Baseline and integration contract | Source baseline inspected; consumer manifest/export implemented; release freeze and downstream adoption remain open |
| 1A: Registry and shared query UI | Implemented locally across five packs; original four source fingerprints preserved |
| 1B: Bounded semantic retrieval | Shared indexed core and MCP bindings tested locally; consumer adoption and production acceptance remain open. See [implementation](semantic-retrieval.md). |
| 2: Semantic preparation | Structured local authoring, canvas, validation, review and version controls implemented; broader document and enterprise integration remain open |
| M2B: Published-model playground | Completed locally: pinned retrieval, typed interpretation, explicit execution, SQL evidence, and read-only query graph |
| M3A: Supporting-material preparation | Completed locally: TXT/MD, text PDF, DOCX, complete cited analysis, keyword/embedding matching, batch review, draft application, and archived provenance |
| M3A.1: Public pharmaceutical evidence and unified Studio flow | Implemented locally: eight tables, six metrics, source briefs, targeted matching, exact quotation recovery, and explicit AI drafting from attached evidence |
| M3A.2: Visual facts and Lance storage | Implemented locally: selected-page GPT-4o extraction, reviewed typed source creation, semantic drafts, and local Lance tables; local provider and browser checks passed |
| M3B: Combined evidence answers | Partial: local published passage answers implemented and tested; one-metric SQL/document synthesis now implemented; enterprise ACLs and cross-model synthesis remain open |
| 4: Agent improvement | Open; no held-out improvement claim |
| 5: Portable acceptance | Local browser checks complete for this increment; Studio Docker refresh and downstream deployment acceptance remain open |

0. **Baseline and integration contract:** inventory existing console/MCP paths, freeze the Helios revision and define pack boundaries.
1A. **Dataset registry and query UI:** select all four packs at startup and execute one reviewed aggregate per pack.
1B. **Bounded semantic retrieval:** index metadata, retrieve relevant definitions and dependencies, enforce token budgets and bind compilation to the retrieved context.
    This is required before multi-sector LLM-query acceptance. See [the retrieval contract](semantic-retrieval-and-metadata-plan.md).
2. **Reusable semantic preparation:** author multiple metrics and reviewed many-to-one joins; validate compiled business rules.
3. **Combined evidence:** import manufacturing and pharma documents into the existing evidence contract and demonstrate both query directions.
4. **Agent improvement:** add bounded probes and explicit verification, then evaluate reviewed experience and targeted repair separately.
5. **Portable acceptance:** complete browser and Docker checks with the same registry, mounts, release hashes and reference questions.

Add launcher and container configuration during milestone 1; reserve full deployment acceptance for milestone 5.
Prepare each increment as an upstream Helios change. Upstream integration is ongoing work, not a final rewrite.
Rebuild the UOB snapshot only after relevant Helios changes pass compatibility checks.

The original milestone sequence above remains the historical roadmap.
M3A now extracts line locations for TXT/Markdown, page locations for text PDFs, and paragraph/table-row locations for DOCX.
It matches source-connected local models, metrics, fields, tables, and ontology/glossary concepts.
Reviewers approve selected links before applying them to a draft; Studio validation and publication remain separate.
Scanned PDFs now support GPT-4o extraction from one to six selected physical pages, within a 32-page PDF limit.
Reviewed observations can create a new typed fact source and semantic draft.
Remote source imports and enterprise identity remain open.

The legacy MCP document index remains unscoped by model in its evidence call and disabled in the local demo.

M3B now provides local release-bound passage retrieval. Enterprise document authorization must precede broader combined answers.
Then deliver structured queries with linked passages and document searches whose entity keys become validated SQL filters.
The visual increment already creates reviewed document-derived assertion tables as separate local sources.
Cross-source identity mapping and supported joins remain separate integration work.
Do not require general OCR, arbitrary extraction or automatic entity resolution for the first combined demo.

The current compiler permits one fact dataset per request and emits inner joins.
Begin with reviewed many-to-one paths. Check unmatched keys and duplicated joins explicitly.
Questions spanning several fact datasets need separate bounded queries and a reviewed combination rule.
Outer joins, unrestricted cross-fact aggregation and arbitrary document joins require separate compiler work.

Existing staged fixture tests are a foundation, not acceptance for these new milestones.
Maintain useful incremental demos after each milestone.

## Next implementation increment

The document workflow now connects upload, cited analysis, reviewed model links, canvas evidence, and AI proposal generation.
The completed local visual increment renders original pages and proposes chart/table observations through GPT-4o.
Explicit reviewer correction and approval precede creation of immutable typed fact sources and semantic drafts.
Rows retain units, periods, populations, denominators, source quotations, and uncertainty.
OpenAI text embeddings rank extracted text in local Lance tables.
The final regression passed 207 tests, including the corrected pharmaceutical pack.
Live OpenAI checks passed for the FDA image, its image-only PDF, and EFPIA page 4. Desktop/mobile workflow checks also passed.
General extraction accuracy, enterprise identity, and downstream integration remain unverified.

1. Connect published Studio packages to the authenticated registry and compatible UOB/Guardrails consumer adapters.
2. Give semantic models stable IDs independent of source connections; local model identity currently follows the connection ID.
3. Implement caller/model/source-scoped passage queries and test isolation before combined answers.
4. Evaluate retrieval recall, citation validity, missing evidence, and document/structured-data disagreement on held-out questions.
5. Implement live Iceberg, Trino, and Atlas imports behind the configured source profiles.

M3A verification passed 19 parser, 13 library, and 11 API tests.
Supporting-material desktop/mobile checks passed at 1440 and 390 pixels.
The final regression run passed 141 backend tests. Live GPT-4o analysis produced six cited statements; text-embedding-3-small matching found finance and manufacturing candidates. Repeated matching made zero embedding calls. These checks do not establish production acceptance.

M3A.1 passed a separate 123-test regression run after adding the pharmaceutical model and citation repairs.
The original EFPIA PDF produced 53 exact-cited claims across 30 sections with GPT-4o.
The trial brief produced six cited claims, two evidence links, and a six-metric AI proposal using the attached document.
All live checks used isolated test state. See [increment evidence](pharma-intelligence-verification.json).

## Acceptance gates

Every pack must launch without changes to application source.
A selected pack must never read another pack's index, model, memory or evaluation truth.
Queries must handle joins, date boundaries, missing values and ambiguous terms correctly.
Manufacturing and pharma answers must combine a structured result with a cited original document location.
Unsupported semantic requests must clarify or stop rather than fall through to unrestricted SQL.

Compare schema-only, approved semantics, semantics plus verification, and reviewed-memory configurations on the same held-out questions.
Freeze the model, dataset snapshot, semantic release and memory library for each comparison.
Report correctness, precision with coverage, appropriate clarification, repair regressions, latency and tool/token budgets.
Test citation validity and document/structured-data disagreement separately from SQL accuracy.
Verify local and container results against independent references.
Browser checks must cover both desktop and mobile layouts.

## Feasibility and confidence review — 10 October 2026 (historical)

The following findings record the original baseline.
Current MCP tools and delivered retrieval behavior are described in [semantic-retrieval.md](semantic-retrieval.md).

Overall confidence is **80%** for the bounded reusable demo described here.
Confidence for the first local milestone is **90%**.
These are engineering judgments about implementation feasibility, not measured success probabilities or query-accuracy targets.
They assume writable Helios access and a runtime that can execute browser/container acceptance checks.

| Workstream | Confidence | Evidence and remaining uncertainty |
| --- | --- | --- |
| Startup dataset registry and shared query UI | High, 90% | Four generated packs and an existing FastAPI console provide the foundation. Generic loading and planning still need implementation. |
| Reviewed structured semantic preparation | High, 80% | Helios supports metrics and relationship paths. UOB authoring currently supports one table and one metric. |
| Combined table/document queries | Moderate, 75% | Helios already supplies evidence search, entity claims and document-to-query trace links. Sector imports and index isolation remain unverified. |
| Bounded probing and explicit verification | High, 80% | Existing typed tools, SQL validation and traces are reusable. Probes and business-rule checks need new contracts. |
| Accuracy gains from reviewed experience and repair | Moderate, 60% | Research supplies useful mechanisms. Their benefit on our models and sector questions has not been measured. |
| Local/Docker/browser delivery | Moderate, 70% | Portable artifacts exist. Current filesystem and browser restrictions prevent complete acceptance. |

### Findings that change the original plan

**Reuse more of Helios.** `apps/helios/console/main.py` already hosts the FastAPI console.
`console/conversation.py` supplies a server-side LLM/MCP loop.
`mcp/server.py` exposes `search_semantics`, `compile_query`, `run_query`, `search_evidence` and `entity_claims`.
`console/trace_documents.py` links retrieved document entity keys to query filters.
Inspect and extend these paths before copying UOB orchestration or introducing another service.
Code availability is not proof that the new four-pack workflow already works.

**Separate deterministic sample execution from LLM acceptance.** UOB's current financial sample uses a narrow offline grammar.
It cannot query manufacturing, pharma or power by changing only the database path.
Its DuckDB adapter also hardcodes `iceberg.synthetic_finance` and the finance schema.
The pack registry therefore needs a generic source adapter and a model-independent planning contract.
Milestone 1 must label deterministic example execution separately from configured LLM-generated semantic requests.

**Enforce pack boundaries in the evidence index.** Current MCP document tools authorize the selected model before accessing the index.
The inspected calls do not pass a model filter to `evidence.search` or `entity_claims`.
The source also states that document text uses the workload identity, without Ranger filtering per caller.
Use an isolated index per selected demo pack, or add tested dataset/model filters throughout the retrieval path.
A selected UI model is insufficient evidence of document isolation.
Do not expand this finding into a production permission implementation within the initial local demo milestone.

**Avoid overclaiming the fixtures.** Current documents have explicit entity IDs but lack a published runtime retrieval index and complete versioned citation records.
The catalog lists pack names and review state; it is not yet a runtime registry.
Existing aggregate checks do not establish retrieval recall, join correctness or general NL-to-SQL accuracy.
Current public-source import tests use small local inputs; actual archive import acceptance is still pending.

### First milestone acceptance

1. Launch each of the four packs through the same command and configuration contract.
2. Display the selected sector, source, sample mode and semantic release in the shared query UI.
3. Build typed local databases from declared schemas, avoiding production reliance on CSV type inference.
4. Review and select sample semantic releases explicitly before querying them.
5. Execute at least one metric per pack and reconcile it against an independent reference.
6. Reject cross-pack paths, stale release hashes and incompatible saved settings.
7. Keep evaluation files outside runtime discovery and retrieval roots.
8. Distinguish predefined offline examples from actual LLM planning in the UI and verification record.
9. Preserve existing Helios TPC-DS entry points and existing UOB demo behavior.
10. Complete milestone 1B before accepting generic LLM queries: never send the full catalog through prompts, tools or history.

### Evidence reviewed

- Current UOB orchestration, financial grammar, DuckDB adapter and single-table semantic authoring.
- Current Helios console, conversation loop, MCP tool signatures, document trace code and compiler restrictions.
- Staged sector catalog, linked document manifests and seven previously passing fixture checks.
- Three existing Helios document-trace tests passed during this review.
- Four existing Helios compiler tests passed with `HELIOS_ROOT` set to the monorepo root.
- The initial compiler test invocation used its outdated default fixture path; correcting the root resolved the setup errors.
- These seven focused checks verify reusable components, not the proposed end-to-end workflow.

## Current restrictions

This session cannot write into the sibling Helios repository.
The plan and additive files remain staged in this workspace's contribution overlay.
Upstream installation, commit and push have not occurred.
The new registry, combined-query runtime and query-focused launcher are planned work.
The current sector fixtures remain source-informed synthetic and IN_REVIEW.
