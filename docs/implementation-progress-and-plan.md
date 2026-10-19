# Semantic Hub: implementation progress and next steps

Updated: 19 October 2026.
Latest application commit reviewed: `95886c2`.
Repository: https://github.com/FerdinandZhong/semantic-hub
This snapshot consolidates the recorded milestones. It does not claim a fresh full-system verification.
The [detailed milestone log](SEMANTIC_FOUNDATION_STATUS.md) retains earlier evidence and historical limitations.

## Current position

Semantic Hub manages semantic definitions, document evidence, immutable reviewed versions, and consumer access.
Studio builds and validates models. Playground tests published definitions through bounded query workflows.
External agents can retrieve versioned semantic context through the consumer API and MCP adapter.
The application is packaged as a Cloudera AMP and has run in CAI.
Enterprise authorization and production acceptance remain incomplete.

```text
Structured sources + supporting documents
                   |
                   v
       AI proposals + Studio editing
                   |
                   v
       Human review + validation SQL
                   |
                   v
        Reviewed / published versions
                   |
                   +----> Playground verification
                   |
                   +----> Consumer API ----> MCP ----> External agents
```

## Delivered scope

| Area | Implemented progress | Evidence and limits |
| --- | --- | --- |
| Hub and navigation | Source-scoped model catalog, details, versions, Studio, and Playground entry points | [Studio guide](context-builder.md) |
| Interface | Blue theme, aligned controls, simplified canvas controls, review pagination, and clearer document actions | Historical milestone log and linked UI verification records |
| Studio canvas | Dataset, field, metric, relationship, and document evidence views | Read-only published-version inspection preserves model immutability |
| Review and versions | Draft saving, validation, object review, reviewed versions, publication, comparisons, and query activation | Review and publication are explicit user actions |
| Starter sources | Finance, manufacturing, pharma batch quality, and power fixtures | Synthetic data remains distinct from external source evidence |
| Pharma intelligence | Separate public-source pharmaceutical intelligence model and demo material | [Model guide](pharma-intelligence.md), [two demo stories](pharma-intelligence-demo-story.md) |
| Supporting materials | Shared library, revisions, selected-page visual analysis, claims, matching, review, and draft attachment | [Materials guide](supporting-materials.md) |
| Document-derived models | Reviewed visual rows can create a new source and draft model with provenance | [Visual facts](visual-document-facts.md); creation does not publish |
| Document workflow UX | Dropzone upload; Extract / Analyze / Use-in-a-model steps; create a new model, attach evidence, or both | Scanned pages are transcribed by the draft VLM on upload; mixed PDFs keep text pages |
| Playground chat | UOB-style transcript: user bubbles, AI answer cards, bottom composer, saved-metric chips | Earlier turns are read-only; each question is still an independent request |
| Embeddings | Optional text vectors and Lance storage with model/endpoint fingerprints and cache reuse | Text embeddings; no direct image/text embedding endpoint integrated |
| Model credentials | Direct masked API-key entry, environment references, encrypted local storage, and connection testing | [Configuration guide](model-configuration.md); CAI ingress credentials remain separate |
| Playground | Published-version metric queries, scoped document answers, combined evidence, and explicit query plans | Lightweight model verification; not a general warehouse agent |
| Query scope | Separate geography and time diagnostics; missing cohorts do not fall back to another period | Narrow live acceptance cases passed; broad natural-language correctness remains unproven |
| Agent modules | Harness, skills, bounded tools, and release-scoped audit memory | [Agent architecture](playground-agent-architecture.md) |
| External consumers | Read-only published inventory, versions, definitions, ontology, lineage, search, and frozen evidence | [Consumer API](semantic-hub-consumer-api.md) |
| Bounded execution | Pinned version, expiring context bundle, typed compilation, and bounded local sample execution | External agents retain their own warehouse execution tools |
| MCP | Twelve tools; local stdio/HTTP verification; GitHub uvx installation configuration | [Adapter](../apps/semantic-hub-mcp/README.md) |
| CAI workflow | English and Chinese Agent Studio setup and demo instructions | [Workflow](semantic-hub-agent-studio-workflow.md) |
| AMP | Manifest, isolated environment, persistent state, combined UI/API process, and verification scripts | [Deployment guide](amp-deployment.md) |
| CAI authentication | Ingress authentication and `CDSW_APIV2_KEY` support; no generated local Hub token | Live authenticated HTTP checks passed on 19 October |
| Swagger | Standard CAI API v2 bearer authorization; legacy custom-token form removed from AMP template | Local browser/API tests passed; deployed template revision requires confirmation |
| Architecture assets | Editable draw.io overview and agent architecture documentation | [Overview diagram](diagrams/semantic-hub-overview.drawio) |
| Customer presentations | Semantic Hub slides added and styled in the Toyotec deck | Local deck work completed; deck is outside this repository |

## Recent fixes and release evidence

| Commit | Change | Recorded validation |
| --- | --- | --- |
| `bb6a518` | Initial AMP packaging and shared application state | Clean Python 3.11 installation; AMP, consumer API, MCP, and local HTTP checks |
| `4c27217` | Isolate setup/startup from inherited CAI packages | Eight AMP tests and contaminated-path reproduction |
| `2d7eb19` | Preserve the Jupyter kernel through child-process supervision | Eleven AMP tests and local process lifecycle checks |
| `ab87bb4` | Bind the CAI server to `127.0.0.1` | User subsequently confirmed the Application runs |
| `d3da9af` | Native Swagger CAI API v2 authorization | Eleven AMP tests, twelve consumer tests, and browser authorization checks |
| `2302b07` | Real DOE manufacturing PDF excerpt and linking guide | File size, page mapping, checksums, and visual inspection |
| `95886c2` | Older/newer OpenAI request compatibility | 120 regression tests; three model connections; nine live Playground cases |

These commits were pushed to the Semantic Hub repository.
A pushed commit does not prove that CAI runs that commit.
No application restart or remote checkout update occurred during this documentation task.

## Model compatibility milestone

GPT-4o and unknown compatible model IDs retain legacy Chat Completions behavior.
GPT-5 uses completion-token controls. Existing GPT-5.1+ reasoning behavior remains unchanged.
GPT-6 text and tool calls use Responses with supported low reasoning.
Tool loops preserve function-call identifiers and encrypted reasoning items.
Visual extraction keeps its JSON-schema contract and now selects compatible generation fields.

Live tests used GPT-4o, GPT-5.4, and GPT-6.1 Sol.
Each model passed these three Playground checks:

1. Return 74.1% for the supported USA new-medicine launch cohort, 2020–2024.
2. Return no data for the missing 1999–2020 cohort.
3. Reject Korea against the fixed-USA metric as unsupported geography.

See [machine-readable compatibility evidence](model-compatibility-verification.json).
These checks do not establish unrestricted NL-to-SQL correctness or newer-model visual extraction accuracy.

## Customer documents and storylines

| Sector | Prepared material | Demo boundary |
| --- | --- | --- |
| Finance | Original HSBC Smartform PDF and real-source catalog | Page 7 supports recipient account meaning; it does not validate synthetic transfers |
| Manufacturing | Nine-page DOE maintenance excerpt, 1.64 MiB, with original-page map | Excerpt pages 4/5 support maintenance and condition-monitoring context |
| Pharma intelligence | FDA and EFPIA references; English and Chinese storylines | Evidence attachment and new fact-model creation are separate actions |
| Power | Customer storyline with ten supported and ten unsupported requests | Demonstrates energy, quality rules, Singapore dates, and source lineage |

Finance synthetic upload artifacts were removed from the earlier local library at the user's request.
The original synthetic source datasets remain available.
The earlier EFPIA demo model was requested for cleanup; current CAI inventory must be inspected before asserting its presence or absence.
Prepared files are not automatically uploaded into every deployed workspace.
The 19 October CAI catalog check found no HSBC upload.
The DOE excerpt was prepared without automatically uploading or approving it.

- [Finance document linking](finance-real-document-sources.md)
- [Manufacturing document linking](manufacturing-real-document-sources.md)
- [Finance customer story and twenty questions](finance-customer-demo-story.md)
- [Power customer story and twenty questions](power-customer-demo-story.md)
- [Short finance/manufacturing stories](finance-manufacturing-simple-demo.md)
- [Pharma demo stories](pharma-intelligence-demo-story.md)
- [Chinese pharma demo stories](pharma-intelligence-demo-story.zh-CN.md)
- [Reference SQL](demo-reference-sql.md)

The finance starter metric totals settled payments: 686,572.96 SGD in the recorded fixture.
Its reference SQL sums `transactions.amount_sgd` where `status = 'SETTLED'`.
The manufacturing starter metric sums `work_orders.downtime_minutes`: 312 minutes in the recorded fixture.
Document attachment alone does not change either metric's SQL or result.

## Verification summary and practical limits

- The latest compatibility suite passed 120 tests. This is a targeted suite, not the entire repository suite.
- Earlier local GitHub-installed MCP verification exercised all twelve tools.
- Earlier live agent checks passed seven pharma cases and 38 of forty finance/power cases.
- Two Singapore-date interpretations remained imperfect in that agent acceptance run.
- A prior planner passed forty customer cases; it predates the Harness acceptance run.
- Live CAI checks returned HTTP 200 with a supplied CAI API v2 key and login redirects without credentials.
- Historical visual checks covered GPT-4o extraction, source review, and Lance cache reuse.
- No production load, broad multilingual accuracy, or enterprise per-model authorization acceptance is claimed.

Do not add historical test totals together as one current test run.
Use each linked verification report for its exact environment and scope.

## Implementation plan after this milestone

| Priority | Next action | Completion evidence |
| --- | --- | --- |
| 1 | Confirm CAI checkout, restart, and latest compatibility behavior | Deployed revision recorded; UI, Swagger, and three model-path checks pass |
| 2 | Rehearse real finance and manufacturing document linking | Reviewed source page, selected model object, saved draft, and immutable published evidence |
| 3 | Test newer-model image/PDF extraction | Original page versus extracted categories, values, units, and periods |
| 4 | Improve document/VLM/embedding labels in configuration help | Users can identify extraction versus optional similarity search |
| 5 | Recheck multilingual and date-boundary query behavior | Explicit geography/time tests, including the two recorded Singapore-date failures |
| 6 | Rehearse the hosted CAI Agent Studio MCP workflow | Actual remote MCP tool calls through authenticated ingress |
| 7 | Add enterprise authorization and operational controls | Per-model/document permissions, audit retention, concurrency, and durable-job acceptance |
| 8 | Implement live source and storage adapters as required | Iceberg/Trino/Atlas integration and object-storage validation |
| Conditional | Add direct multimodal embeddings | A measured image-retrieval requirement and a supported provider/model benchmark |

The current OpenAI-only recommendation uses a VLM for understanding and text embeddings for optional retrieval.
See [discussion and decisions](vision-ocr-and-embeddings-discussion.md).
No dedicated OCR service or direct multimodal embedding model was added in this milestone.
Atlas integration remains possible but is not implemented by these changes.
