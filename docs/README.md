# Semantic Hub documentation map

Reviewed on 19 October 2026 against the local working tree.

Start with [current implementation progress and plan](implementation-progress-and-plan.md).
Read [vision, OCR, and embeddings decisions](vision-ocr-and-embeddings-discussion.md) for the document-understanding discussion.

## Integrate an external agent

Use the [consumer API](semantic-hub-consumer-api.md), [MCP adapter](../apps/semantic-hub-mcp/README.md), and [CAI Agent Studio workflow](semantic-hub-agent-studio-workflow.md).
The workflow is also available in [Chinese](semantic-hub-agent-studio-workflow.zh-CN.md).
See the [Playground architecture](playground-agent-architecture.md) for the local DeepSeek Harness flow.

## Use the local demo

Configure credentials through [Model configuration](model-configuration.md), including direct API-key entry.

1. Start with [Demo start here](DEMO_START_HERE.md).
2. Follow [runtime setup](demo-runtime.md) and open the source in Semantic Hub.
3. Use [Studio and review](context-builder.md) to build a semantic layer.
4. Use [reference SQL examples](demo-reference-sql.md) to validate the four starter metrics.
5. Add reviewed evidence through [Supporting materials](supporting-materials.md).
6. Test published definitions in the [Model playground](model-playground.md).
7. Read [foundation status](SEMANTIC_FOUNDATION_STATUS.md) before integrating another application.

For real visual evidence, see the [four-sector document source catalog](real-document-source-catalog.md).
Use the [finance customer story](finance-customer-demo-story.md) and [power customer story](power-customer-demo-story.md).
For a short presentation, use the [finance and manufacturing storylines](finance-manufacturing-simple-demo.md).
Each includes twenty questions, reference SQL, publication steps, and expected boundaries.
The [machine-readable cases](customer-demo-queries.json) and [verification](customer-query-verification.json) support repeatable acceptance.
The earlier synthetic finance document story is archived.
For actual publisher documents, use the [six downloaded finance references](finance-real-document-sources.md), including illustrated bank forms and BIS charts.
The source catalog also includes a pharma-focused collection and measured importer limitations.
The [pharmaceutical intelligence walkthrough](pharma-intelligence.md) covers the fifth model, public facts, validation SQL, and document-to-model evidence.
Use the [two pharmaceutical demo stories](pharma-intelligence-demo-story.md) for exact linking, validation, publication, and playground steps.
The same runbook is available in [Chinese / 中文版](pharma-intelligence-demo-story.zh-CN.md).
Story 1 uses PDF page 14 as scope evidence for the existing model; Story 2 creates a separate model from pages 4 and 5.
Copy the [Story 1 SQL](demo-inputs/story-1-pharma-reference.sql), [Story 2 SQL](demo-inputs/story-2-efpia-reference.sql), and [nine-row guide](demo-inputs/efpia-pages-4-5-row-guide.csv).
The earlier [page 4-only input sheet](efpia-page4-demo-inputs.md) remains an optional smaller example.
The [visual-document workflow](visual-document-facts.md) covers PNG/JPEG, scanned PDFs, reviewed typed fact sources, and local Lance vectors.
Its [verification record](visual-document-verification.json) tracks acceptance.
GPT-4o processes one to six selected physical pages from PDFs containing at most 512 pages.
Explicit row review creates a source and semantic draft; publication remains a separate Studio action.

## Choose the correct system

| System | Main references | Scope |
| --- | --- | --- |
| Local Hub and Studio | [Builder](context-builder.md), [runtime](demo-runtime.md) | Fixture-backed authoring, document evidence, review, local releases |
| Supporting-material library (M3A) | [Guide](supporting-materials.md) | Revisioned TXT/MD, text PDF, DOCX, cited analysis, optional embeddings, batch review, and archived draft evidence |
| Published-model playground (M2B) | [Guide](model-playground.md) | Bounded typed question interpretation, explicit execution, SQL evidence, and pinned releases |
| Shared semantic retrieval | [Implementation](semantic-retrieval.md), [plan](semantic-retrieval-and-metadata-plan.md) | FTS5 search, dependencies, scoped bundles, cache and budgets |
| Authenticated React/API/MCP | [API contract](ui-backend-contract.md), [MCP](mcp-server.md), [conversation](talk-to-your-data-architecture.md) | Registered models, identity, authorization, warehouse execution |
| Crawler and document index | [Crawler guide](crawler-guide.md), [analysis](crawler-analysis.md), [plan](crawler-burndown.md) | Extracted passages, entity resolution, claims and evaluation |
| Ontology services | [Authoring proposal](ontology-authoring.md), [deployment](ontology-deployment.md), [plan](ontology-burndown.md) | LinkML and graph services; broader authoring remains planned |
| Deployment and operations | [UI deployment](ui-deployment.md), [networking](ui-api-networking.md), [security](SECURITY_ARCHITECTURE.md), [metadata](helios-metadata-database.md) | Authenticated deployment and operational state |
| Research and historical evidence | [Alignment review](DOCS_ALIGNMENT.md), [walkthroughs](walkthrough/README.md), [deck notes](Helios-Overview-notes.md) | Design inputs and recorded evidence, not current deployment proof |

The [alignment review](DOCS_ALIGNMENT.md) maps the remaining materials to implemented, separate, or deferred work.
For customer architecture questions, see [workflow state, artifact storage, and Atlas integration](semantic-hub-storage-and-atlas.md).
Historical handoff copies retain their original content and checksums.
Use current implementation guides when a historical plan or screenshot differs.

The [Model playground](model-playground.md) documents published-version question interpretation, execution evidence, and integration boundaries.

M2B and M3A work locally. Scoped published-passage queries and combined SQL/document answers are implemented for the local Playground.
Production acceptance and downstream adoption remain open.
The current workspace now has a dedicated published-model API and MCP adapter.
Enterprise per-model identity and live imports remain integration work. CAI ingress checks passed; full hosted acceptance remains open.
The legacy MCP document index remains separate and disabled in the local demo.

### GitHub MCP handoff

- [Importable MCP configuration](../apps/semantic-hub-mcp/agent-studio.mcp.json): pinned GitHub installation through uvx.
- [GitHub MCP verification](semantic-hub-github-mcp-verification.json): twelve tools tested against the local API without a consumer token.
- [Short finance and manufacturing stories](finance-manufacturing-simple-demo.md): questions, expected starter values, and validation SQL.

AMP packaging and CAI ingress authentication are implemented. Full hosted Agent Studio acceptance remains open.

- [Semantic Hub AMP deployment](amp-deployment.md): setup, persistent storage, CAI authentication, and MCP configuration.

- [Manufacturing real-document evidence](manufacturing-real-document-sources.md): upload-ready DOE excerpt, page mapping, model-link instructions, and demo questions.
