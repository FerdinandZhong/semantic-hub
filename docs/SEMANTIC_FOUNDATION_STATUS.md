# Semantic foundation: progress and consumer handoff

**CAI ingress and Swagger verification — 19 October 2026:** The deployed Application accepted a supplied CAI API v2 key for Swagger, OpenAPI, capabilities, and supporting materials (HTTP 200).
Requests without a key redirected to CAI login (HTTP 302). The deployment reported CAI ingress authorization.
Its material catalog did not contain the HSBC guide; the finance documentation now includes AMP upload instructions.
The AMP Swagger template now removes legacy consumer-token markup and exposes standard CAI API v2 bearer authorization.
Eleven AMP tests and twelve consumer API tests pass. The template update requires a checkout update and Application restart.

**AMP Application launcher repair — 18 October 2026:** Replaced kernel-process execution with a blocking child-process supervisor.
The launcher retains the CAI Jupyter kernel, propagates server failures, and cleans up the server process group on shutdown.
The isolated bootstrap now consumes its project-root argument before server argument parsing.
Eleven AMP tests pass, including command-line handling, parent-process survival, and signal cleanup.
Live CAI restart remains required.

**AMP setup isolation repair — 18 October 2026:** CAI setup reported conflicts with platform MLflow, CML, and OpenTelemetry distributions.
A local regression reproduced the same failure using an inherited notebook package path.
Setup and startup now clear inherited Python paths and install overrides and run Python in isolated mode.
Setup checks distribution origins, disables system-site-packages, and preserves contaminated runtimes before rebuilding.
Eight AMP tests pass, including path contamination and state-preserving runtime repair.
See [setup recovery](amp-deployment.md#recovery-cai-packages-reported-by-pip-check). Live CAI rerun remains required.

**AMP MCP configuration — 18 October 2026:** The default Agent Studio configuration now targets an authenticated CAI Application origin and pins published AMP commit `bb6a518`.
The MCP subprocess inherits `CDSW_APIV2_KEY` from its secret environment; no credential is stored in the JSON template.
A separate local configuration retains loopback access. English and Chinese workflow guides describe both paths.
Live CAI ingress acceptance remains pending.

**AMP packaging — 17 October 2026:** Added the Cloudera AMP manifest, catalog metadata, isolated-runtime setup, and a combined Application launcher.
Studio, Swagger, and the consumer API share one Hub instance and persistent project state.
CAI Application ingress provides authentication; no local consumer token is created.
MCP accepts `CDSW_APIV2_KEY` when no standalone consumer token is configured.
Setup preserves credentials and reviewed state and does not automatically publish models.
A clean Python 3.11 installation passed fixture/import checks, six AMP tests, twelve consumer API tests, and fifteen MCP tests.
Local HTTP smoke checks confirmed UI, Swagger, capabilities, and empty published inventory through the combined launcher.
See the [deployment guide](amp-deployment.md). Live CAI installation, ingress authentication, and restart acceptance remain unverified.

**GitHub packaging and local API access — 15 October 2026:** The MCP adapter now has a GitHub `uvx` configuration matching the AML project pattern.
Local API, Swagger, and MCP checks support explicit loopback-only access without a consumer token.
Code is published at https://github.com/FerdinandZhong/semantic-hub.
The GitHub-installed adapter passed all twelve tool calls, returned 74.1 for the supported cohort, and returned `no_data` for 1999–2020.
See [GitHub installation verification](semantic-hub-github-mcp-verification.json). The importable MCP configuration pins that tested commit.
The local consumer token was removed at the user's request. Model-provider credentials remain separate.
At that milestone, CAI authentication and AMP packaging were planned; see the 17 October increment above.
The saved GPT-5.4 connection returned HTTP 200 after URL normalization and generation-parameter fixes.
The local-access increment passed 12 consumer API tests and 13 MCP tests. Swagger browser execution returned HTTP 200 without authentication.
Full legacy-suite collection remains blocked in the demo environment by an MCP package-name collision and missing Impala dependencies.


**Query diagnostics and GPT-5.4 compatibility — 15 October 2026:** Period checks and explicit category checks now report separate outcomes.
A Korea filter against the fixed-USA metric reports geography mismatch while confirming the valid 2020–2024 period.
Document-only date gaps no longer establish missing model coverage in Auto mode.
Before final metric refusal, Auto mode checks available published document evidence.
GPT-5.4 requests use `max_completion_tokens`; its live connection and four scoped query checks passed.
See [live verification](query-scope-gpt54-verification.json) and [short finance/manufacturing demos](finance-manufacturing-simple-demo.md).
This targeted check does not establish general natural-language correctness.

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

Updated: 15 October 2026. This report covers the inspected Helios working tree and its downstream integration requirements.

**Finance supporting materials:** A reproducible four-page synthetic PDF, image chart, Markdown copies, and reference SQL now accompany the finance fixture.
The synthetic PDF and PNG were subsequently removed from the library at the user's request and replaced by the original HSBC Smartform guide.
HSBC revision 1 has 13 extracted sections and awaits review. The live finance workspace remains unchanged.
Isolated linking, validation, publication, and saved-metric execution returned 686,572.96 SGD. Live GPT-4o document QA returned the fixed USD/SGD rate of 1.3.
The earlier combined-finance run required join clarification. Explicit-field planning now removes unrelated keyword joins; genuine account-role ambiguity still requires clarification.
See the [verification record](finance-supporting-materials-verification.json) for measured extraction results and limits.

**UI polish:** The Hub, Studio, supporting materials, model configuration, and playground now share compact blue navigation with line icons.
The design follows the sibling UOB workspace's spacing and surface conventions while retaining Cloudera branding.
Upload controls share a baseline and 44 px height on desktop; smaller screens use a stacked layout.
Read-only browser checks passed at 1440, 1024, and 390 px, including source-dialog layout and no horizontal page overflow.

**Supporting-material UX update:** Page analysis now precedes two independent model actions.
Users can create a semantic model and attach evidence from the same results.
Repeat extraction automatically creates a document revision, preserving earlier reviews and models.
Matching can use analyzed pages or all extracted text. English and Chinese demo instructions follow this flow.

**AI query correction:** Default AI mode now supports one executed metric plus published document evidence in a single cited answer.
The plan no longer displays unverified router prose. Requested years stay bound to the original question.
The 2020–2024 North America question must not receive the 2025 figure as its answer.
This increment passed 29 backend tests, desktop/mobile hybrid UI checks, and seven live GPT-4o cases.

**Published document answers:** Playground now reads reviewed library passages frozen in the selected published model.
EFPIA page 14 supports the 54.7% answer without a new SQL metric.
Verification: 48 backend tests, four-dataset desktop/mobile checks, and document-answer browser checks passed.
Live GPT-4o checks returned 54.7% for English and Chinese questions, 74.1% for the existing sales metric, and 46 approvals. See [contract and limits](model-playground.md).

**Demo readiness update:** The [two pharmaceutical stories](pharma-intelligence-demo-story.md) now separate existing-model evidence from new document-derived facts.
English and Chinese scripts include page 14 linkage, pages 4–5 row review, all reference SQL, and saved-metric questions.
The old EFPIA demo model and upload were archived; all five base workspaces and the manufacturing release were preserved.
Serving-model generation now removes authoring-only `builder_seed` metadata, preventing published seeded models from failing playground retrieval.
Other extension rules remain intact and still pass through the existing rule checks.
The [preparation verification](pharma-demo-stories-verification.json) checks both stories in isolated state; it does not claim live AI extraction accuracy.
All sixteen saved metrics executed after isolated publication, and the related 83-test regression passed.

**Implementation update:** [Indexed retrieval and agent integration](semantic-retrieval.md) now implements the shared core, scoped model discovery and MCP bundle enforcement.
The unified builder now stages source-only proposals, edits business metadata, and binds document evidence to immutable releases.
Studio exports a published consumer package with separate document, context, snapshot, and artifact hashes.
The landing Hub now catalogs five local source models and opens connection details, versions, and source-specific Studio workspaces.
The new [pharmaceutical intelligence model](pharma-intelligence.md) contains 119 curated public records across eight tables and six metrics.
It remains separate from the synthetic pharma batch-quality model.
Studio now has one primary supporting-material workflow, followed by an explicit AI drafting step using attached evidence.
Connection configuration supports local dataset, Iceberg, Trino, and Atlas profiles.
Remote profiles require import adapters before authoring or execution; they do not borrow local fixture models.
The local 80,000-field benchmark passes all 40 labeled bundle cases.
Downstream adoption, production load testing and warehouse-derived metadata field policies remain open.
**Semantic building, the published-model playground, and supporting-material review work locally.**
The [supporting-material library](supporting-materials.md) now retains document revisions, cited analysis, reviewed model links, and archived attachment provenance.
The [visual-document increment](visual-document-facts.md) adds reviewed image/scanned-PDF facts and local Lance vector storage.
Reviewers select one to six physical pages from PDFs containing at most 32 pages.
GPT-4o proposes observations; explicit row review creates a new typed fact source and semantic draft.
The [visual verification record](visual-document-verification.json) tracks acceptance.
The final regression passed 207 tests, including the corrected pharmaceutical pack.
Live OpenAI checks passed for the FDA image, its image-only PDF, and EFPIA page 4. Desktop/mobile workflow checks also passed.
Consumer adoption, scoped passage answers, and production acceptance remain open.
UOB already consumes Helios models and compilation through its own adapter.
The new Studio release format still needs a consumer adapter.
Semantic Guardrails plans to consume Helios; its semantic provider is not implemented yet.

The UOB checkout is `../uob-ai-data-operations-workspace`; no checkout named `../uob-ai-data` exists beside Helios.
The other consumer is `../semantic-guardrails-cai`.
The retrieval increment changes Helios code and documentation; neither consumer checkout was modified.

## 1. Capability status

| Capability | Current status | Boundary for downstream applications |
| --- | --- | --- |
| Typed source inspection | Implemented locally across finance, manufacturing, pharma, power, and pharmaceutical intelligence | Fixture-backed DuckDB schemas and bounded previews; not live-source discovery acceptance |
| Pharmaceutical intelligence dataset | Implemented locally | Curated FDA/EFPIA public facts, source warnings, six validated starter metrics; not automated OCR or a complete drug pipeline |
| Semantic building | Implemented locally | Stage LLM or deterministic proposals; explicitly apply; edit metrics, metadata, grouping, fixed filters, and directed relationships |
| Business metadata | Implemented locally | Dataset meanings, field roles, glossary terms, metric business context, provenance, and evidence references |
| Builder document evidence | Implemented locally | Serving bytes and reviewed supporting attachments; verified keys, citations, and immutable manifests |
| Shared supporting-material library (M3A) | Implemented locally | TXT/MD, PDF, DOCX, PNG/JPEG; cited analysis, keyword/Lance embedding matching, reviewed links, and draft application |
| Visual document facts | Implemented and tested locally | GPT-4o selected-page extraction, original previews, explicit row correction/review, immutable typed fact sources, and semantic drafts |
| Model configuration | Implemented locally | Independent draft, playground/query, and embedding profiles; environment references or encrypted, write-only direct API keys |
| Structural ontology artifacts | Implemented locally | Typed source mappings and graph proposals; explicit item review; no enterprise ontology certification |
| Visual editing | Implemented locally | Object tree, canvas, inspector, field connections, search, zoom, reversible column/neighbor views, and fullscreen |
| Dependency graph | Implemented locally | Declared relationships, parsed SQL references, and distinct document evidence links; not execution-observed lineage |
| Technical validation | Implemented locally | Compiled/reference SQL reconciliation, key uniqueness, null keys and unmatched source checks |
| Human review | Implemented locally | Review metadata, metrics, relationships, source documents, attachments, and ontology; complete approval requires every required item |
| Change and version controls | Implemented locally | Stable object IDs, before/after comparison, affected objects, immutable versions and draft restoration |
| Publication and activation | Implemented locally | Separate local Hub publication and query activation; no remote registry publication adapter |
| Model inventory | Existing MCP implementation | `list_models` lists published models visible through model-read authorization |
| Search within a model | Indexed retrieval implemented | `resolve_context` returns permitted definitions and complete dependencies |
| Cross-model discovery | Implemented for adopted scopes | `discover_models` returns matching authorized models; enterprise owner/domain catalog UI remains open |
| Bounded semantic bundles | Implemented in reusable Helios core | UOB and Guardrails adoption remain open; MCP now enforces bundle bindings |
| Published-model playground (M2B) | Implemented locally | Version-pinned retrieval, bounded typed LLM interpretation, explicit run, SQL evidence and read-only query graph; no arbitrary SQL; separate cited document-answer path available |
| Scoped document query answers (M3B) | Local release-scoped increment implemented | Auto/metric/document modes, frozen linked passages, exact citations, numeric checks, and LLM support review; enterprise ACLs and cross-model answers remain open |
| Legacy MCP document evidence retrieval | Existing separate implementation; integration incomplete | Model authorization does not currently become a model/pack filter in the evidence search call; disabled in the local demo |

The [Model playground](model-playground.md) now consumes published Studio exports through the shared retrieval service.
It does not activate versions or publish into the separate MCP artifact store.

The new Studio runs through the optional local console routes.
It does not replace the existing React console or automatically publish into the existing MCP artifact store.
Local Hub lists models across the configured local connections and shows each connection's version history.
This local catalog does not yet provide enterprise authentication, remote imports, or cross-instance registry federation.

## 2. Semantic building delivered

```text
Serving evidence -> staged proposal -> explicit apply -> editable draft
                                                           |
                                                           v
Consumer export <- local publication <- immutable artifacts <- validation + item review
                         |
                         v
                  query activation
```

Draft revisions prevent stale tabs from overwriting newer edits.
Validation and item decisions bind to the exact saved definitions and evidence.
Semantic edits invalidate those decisions; moving canvas nodes only changes layout preferences.
Final version approval requires successful technical checks and every required item decision.
Publication does not change active queries.

Versions retain definitions, the generated Ossie document, validation results, item decisions, and immutable artifact bundles.
Bundles contain metadata, source mappings, ontology graphs, actual document content, citations, manifests, and quality warnings.
Source facts and document assertions remain separate.
Source identifiers require verified keys; ambiguous inferred anchors remain unmapped.
Finance and power currently contain no serving documents.
The shared library imports TXT, Markdown, PDF, DOCX, PNG, and JPEG documents.
Scanned PDFs use bounded vision extraction with explicit physical-page selection.
Reviewers can create a new typed source from selected observations before semantic validation and publication.
It retains original bytes, checksums, revisions, and cited sections.
Content analysis covers every section in bounded batches and rejects unsupported quotations.

Keyword matching and optional embeddings propose model, metric, field, table, ontology, and glossary links.
Human batch review precedes draft application.
Applied evidence retains the document revision, citations, target links, reviewer, and original checksum.
Source document previews, the grouped canvas collection, document inspectors, and review rows now link to each other.
Unlinked documents remain model-wide context.
Supporting-material embeddings rank proposed links; scoped passage query retrieval and combined answers remain open.

LLM proposals use serving evidence and record provider, model, assumptions, and source references.
The live checks select GPT-4o through their configured provider.
Deterministic evidence proposals remain available without a model call.
Generation only stages a candidate.
Explicit application changes the draft and clears previous validation and decisions.
The proposal path does not read evaluation answers or fill independent reference SQL.
Independent result reconciliation and explicit review remain required.

Typed fixed filters affect compiled execution.
Descriptive inclusion rules do not automatically add conditions or convert units.
The generated HELIOS `business_context` extension preserves units, grain, ownership, synonyms, examples, rules, evidence, assumptions, and rationale.
Shared retrieval preserves this metadata and indexes relevant business terms.
Executable filter definitions and independent reference SQL stay outside this descriptive extension.
The supporting-material matcher stores vectors in local Lance tables keyed by text SHA256 and endpoint/model fingerprint.
Dimensions use separate fixed-size tables; valid legacy SQLite vectors migrate without provider calls.
The legacy MCP document index remains separate and unchanged.
Stable IDs make renames distinguishable from deletion and addition.
Change review uses a canonical baseline and displays removed objects.
Affected-metric marking is conservative when relationships or field meanings change.
It is not a measured execution-impact analysis.

Current authoring limits are 20 metrics, 20 single-key many-to-one relationships and three grouping fields per metric.
Each metric expression uses one fact table and one supported aggregate.
Validation limits each query to five seconds, 256 MB of DuckDB memory and 200 result rows.
Sample reconciliation establishes agreement on the selected fixture, not correctness on unseen production data.
Reviewer names provide local attribution, not authenticated enterprise identity.

Implementation references:

- [Context workspace and release lifecycle](../shared/helios_core/demo/context.py).
- [Local API routes and sample-mode isolation](../apps/helios/console/demo.py).
- [Studio and Hub workflow](context-builder.md).
- [Studio UI](../apps/helios/console/static/demo-context.js) and [canvas](../apps/helios/console/static/demo-canvas.js).
- [Existing React canvas](../apps/helios/ui/src/pages/CanvasPage.tsx), which has a separate API and review workflow.

## 3. What semantic search currently means

These are separate capabilities, with different completion states:

| Search task | Available implementation | Remaining work |
| --- | --- | --- |
| Find an object on the current canvas | Local graph-name filtering and focus | Not a model catalog or LLM retrieval service |
| Find a review item | Local name/kind and change filters | Not a model catalog |
| List accessible models | MCP `list_models` with model authorization | Enterprise catalog filters and UI |
| Discover matching models | MCP `discover_models` over authorized published models | Large multi-model catalog performance evaluation |
| Find definitions inside one model | MCP `resolve_context` using the shared FTS5 service | Warehouse-derived field scopes and downstream adapters |
| Match supporting materials to model objects | Local keyword and optional embedding matcher | Relevance requires human review; no passage-query acceptance claim |
| Retrieve document passages | Separate embedded document index and `search_evidence` | Propagate verified caller/model/pack/source scope into retrieval before reuse |

[MCP retrieval](../apps/helios/mcp/server.py) now searches an indexed semantic release and expands required dependencies.
The legacy `search_semantics` Python function remains, but it is no longer an agent tool.
The [implementation report](semantic-retrieval.md) records the new contract, benchmark and limitations.

Model-level authorization precedes semantic search.
That does not establish field-level permission filtering before ranking.
Query execution has separate authorization code; consumers must preserve it.
`describe_model` remains a Python function but is no longer an agent tool.
Compilation and execution require a current bundle and compile only its bounded model.

The MCP model store now rejects unreviewed proposal fallback.
Pinned-revision loading exists in the authenticated MCP path, but Studio's SQLite releases are not connected to that store.

[Document evidence search](../shared/helios_core/index/evidence.py) supports an optional source filter.
The current MCP `search_evidence` call checks model access but does not pass that scope to the evidence index.
Do not treat this path as verified cross-pack or cross-model retrieval isolation.
The four-pack local demo keeps this integration disabled.

## 4. Consumer handoff

### UOB AI Data & Operations Workspace

The inspected [UOB loader](../../uob-ai-data-operations-workspace/demo/app/semantics.py) reads a pinned Ossie file or an approved AlloyDB JSONB row.
It verifies the document hash and imports the actual Helios model, validator and compiler.
Its [retrieval implementation](../../uob-ai-data-operations-workspace/demo/app/semantic_retrieval.py) already filters permitted definitions and expands required dependencies.
Default bundle limits are five datasets, 100 fields and 24,000 serialized characters.
It asks for clarification on missing matches, ambiguous selections or excessive dependencies.
Character limits do not establish tokenizer or accumulated conversation limits.

UOB retains ownership of application workflows, caller mapping, Trino execution and banking policy enforcement.
Reusable semantic normalization, indexing, dependency expansion and bundle validation should move into Helios.
UOB should consume that shared implementation through a compatibility-tested adapter.
Existing UOB integration is not proof that the new Studio package is already compatible.

Studio now provides `/demo/api/context/export?version=<published-version>` for a verified local publication.
It returns the manifest, Ossie document, complete context package, and immutable builder artifacts separately.
The format distinction is essential:

| Artifact or identifier | Meaning | Adapter requirement |
| --- | --- | --- |
| Studio version response / downloaded context JSON | Context package containing `definition`, `document`, validation and review evidence | Do not give the entire package to the existing Ossie loader |
| `document` inside that package | Generated Ossie model | Validate and export this document for the UOB loader |
| `context_sha256` | Hash of the immutable context package, excluding the hash field itself | Retain for context provenance; do not use as the Ossie document hash |
| Hash of canonical `document` JSON | Hash expected by UOB's semantic loader | Compute separately using the agreed serialization contract |
| Context `version` | Human-selected release name | Preserve separately from Ossie's format version |
| Ossie `document.version` | Format/specification version | Do not interpret as the approved business release version |
| Local publication record | Separate SQLite record for the version and context hash | Verify publication explicitly; an approved version response alone does not prove publication |

The future adapter must also preserve metric grain, units, time rules and review evidence from `definition`.
Exporting only the Ossie document can omit application-facing context from that richer authoring record.
Actual source names and compiler compatibility need validation against UOB's selected serving engine.
Local sample tables must not silently become live warehouse references.

### Semantic Guardrails on Cloudera AI

The [consumer plan](../../semantic-guardrails-cai/IMPLEMENTATION_PLAN.md) explicitly selects Helios for semantic definitions and bounded retrieval.
Its README records implemented M0 gateway enforcement and local Ray integration.
The Helios semantic provider remains planned under M2a.
Those gateway results do not demonstrate semantic retrieval or live Ossie integration.

Guardrails retains ownership of classification overlays, disclosure policies, detector/judge integration and final release decisions.
Semantic similarity cannot grant permission or declassify restricted source material.
Mandatory source-fact lookup must remain independent of relevance ranking.
Missing required context must not produce an allow decision.
Both judge and pipeline must consume compatible, pinned definitions.
Publication in Helios must not automatically change a guardrails profile's adopted release.

The adapter must bind retrieved context to release, policy, trusted caller, content, processing stage and destination.
Output checks must rebind context after content or destination changes.
The [governed evolution design](../../semantic-guardrails-cai/docs/GOVERNED_SEMANTIC_EVOLUTION.md) can reuse Studio's review concepts.
Its observation, candidate evaluation and profile-adoption services remain separate consumer work.

## 5. Foundation delivery and remaining acceptance

The shared core and MCP workflow are implemented through a Python contract and MCP tools.
The consumer manifest and Studio export endpoint are implemented.
The following sequence still requires downstream adoption and production acceptance:

```text
Published model registry -> compatible release adapter -> scoped metadata index
                                                               |
                                                               v
                                           bounded definitions + dependencies
                                                               |
                                       +-----------------------+-------------------+
                                       |                                           |
                                UOB query adapter                         Guardrails provider
                                       |                                           |
                             compile + authorize                         policy + final checks
```

1. Adopt the implemented manifest and Studio export through compatibility-tested UOB and Guardrails adapters.
2. Establish independent model IDs; local model identity currently follows its source connection.
3. Connect Studio publication to the MCP artifact registry before claiming automatic availability there.
4. Derive metadata field scopes from each deployment's trusted policy provider.
5. Validate mandatory Guardrails source facts independently of relevance ranking.
6. Configure each model's tokenizer and input/output budget through the deployment adapter.
7. Test concurrent requests, broad paraphrases and many-model catalogs beyond the initial sequential benchmark.
8. Implement authorization-scoped passage queries and evaluate retrieval before enabling M3B combined answers.
9. Add live Iceberg, Trino, and Atlas import adapters behind configured connections.

The [milestone 1B plan](semantic-retrieval-and-metadata-plan.md) defines the complete retrieval acceptance gates.
The [implementation report](semantic-retrieval.md) identifies delivered steps and remaining integration limits.
Keep external document retrieval separate until enterprise caller and document authorization are integrated.
The existing [observability context library](observability-semantic-context.md) remains a separate native-tool contract.
It should not be presented as SQL model search or as the completed generic bundle service.

## 6. Verification and release state

Current verification covers Studio, the completed M2B playground, and the completed M3A supporting-material library.
The focused material checks passed: 19 parser tests, 13 library tests, and 11 API tests.
Supporting-material browser checks passed at 1440 and 390 pixels.
These checks cover cited analysis, review guards, draft revision checks, cache reuse, and published artifact preservation.
The final regression run passed 141 backend tests. Live GPT-4o analysis produced six cited statements; text-embedding-3-small matching found finance and manufacturing candidates. Repeated matching made zero embedding calls. These checks do not establish production acceptance.

The final test totals and live proposal outcomes must come from the current run.
Earlier Studio checks established local editing behavior but do not establish this increment's acceptance.
See [reproducible commands](context-builder.md#validation-and-verification) and [artifact assessment](builder-artifact-assessment.md).
Local authoring checks do not establish warehouse compatibility or downstream integration acceptance.

The retrieval increment reran focused retrieval, MCP, conversation and Studio tests locally.
It also benchmarked 2,000 tables and 80,000 fields with 40 labeled synthetic questions.
UOB and Guardrails statements describe their inspected source and recorded status, not newly verified deployments.

The unified builder includes working-tree changes.
A prior base commit does not establish the current increment's release state.
Freeze a reviewed commit or content-addressed package before downstream adoption.
No UOB bundle, AlloyDB registry, guardrails profile or external deployment was updated by this increment.

The local review process used in this session serves `http://localhost:8084/demo`.
Studio opens per source at `/demo/context?source=<connection-id>`.
See [reference SQL examples](demo-reference-sql.md) and [documentation alignment](DOCS_ALIGNMENT.md).
A running Docker preview must rebuild before it reflects current working-tree changes.
