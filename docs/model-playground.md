# Published model playground

Current diagnostics report checked period and geography independently.
For example, Korea with a valid 2020–2024 cohort fails the fixed-USA metric's geography constraint, not its period.
Auto mode considers published passages before issuing a final refusal; an unrelated passage's dates are not model coverage.
The [GPT-5.4 verification](query-scope-gpt54-verification.json) records four live cases, including supported SQL and document routing.

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

The Model playground tests published semantic models inside Semantic Hub.
The official DeepSeek Harness coordinates AI planning through bounded tools.
See the [current architecture and diagram](playground-agent-architecture.md).
It does not replace consumer applications or their operational query engines.

```text
Published version → DeepSeek Harness + bounded tools → checked typed request
                                                        |
                                                 Inspect and run
                                                        v
Version-bound evidence ← local DuckDB result ← scoped retrieval + validated compilation
```

## Use the playground

1. Open a source in Semantic Hub and select **Playground**.
2. Select a published version. This does not change the active version used by other query paths.
3. Choose **AI · query data + documents**, **Metric query**, or **Document evidence**. Enter a question and select **Interpret question**.
4. Inspect the metric, expression, unit, grouping, fixed rules, and additional filters.
5. Select **Run this interpretation**.
6. Inspect the result, SQL, release hashes, and focused read-only dependency graph.

Use **Saved metrics** to run a reviewed metric without an LLM.
Selecting a saved metric explicitly uses its saved description and grouping.
Unsupported or ambiguous questions request clarification instead of executing a guessed query.
The query LLM is configured independently under **Model configuration → Model playground**.
GPT-4o and GPT-5.4 retain Chat Completions; GPT-6 models use Responses for agent tool calling.
See [model compatibility and configuration](model-configuration.md#older-and-newer-openai-models).

## Version and execution contract

- Only published Studio releases appear in the version selector.
- The adapter consumes the verified Studio release export and registers its document with the shared retrieval service.
- Retrieval uses SQLite FTS5, permitted definitions, dependency expansion, and bounded semantic bundles.
- Explicit saved-metric selection supplies required grouping fields without adding unrelated lexical field matches.
- Scope binds the local runtime session, adopted release, and local sample field policy.
- Natural-language planning receives a published-model catalogue capped at 48,000 characters, excluding reference SQL.
- Tools inspect reviewed metrics, qualified fields, relationships, actual DATE ranges, and exact cohort pairs.
- The server enforces requested period filters independently of the model. Missing periods return no data.
- The UI shows tool checks, source coverage, and distinct clarification or runtime-failure outcomes.
- AI selects one metric and explicit fields before dependency retrieval. Unrelated keyword matches cannot add joins.
- The shared service then resolves and validates the exact metric, grouping fields, and filter fields.
- Ambiguous relationships, unknown fields, and unsupported requests return clarification without an executable plan.
- The LLM returns a typed request, never executable SQL.
- Each request contains one published metric, up to three dimensions, up to twenty additional filters, and a result limit of 1–200.
- Fixed metric filters remain compiled into the published metric expression. Additional filters cannot remove them.
- The compiler accepts only definitions inside the retrieved bundle.
- The server stores interpreted plans for five minutes, with a maximum of 128 cached plans per runtime.
- Execution receives a plan ID, then rechecks publication, source/session bindings, bundle validity, and the pinned context hash.
- Local DuckDB retains its read-only query restrictions, five-second deadline, and 256 MB memory limit.
- Execution fetches one extra row to report result truncation. Evidence shows the actual executed SQL.
- Draft edits and unrelated version activation do not change a pinned interpretation.

The local sample field policy permits the selected fixture schema.
It is not an enterprise authorization implementation.
Applications must construct their own trusted caller and field scopes when consuming the shared retrieval service.

## Evidence display

The interpretation identifies its provider and model, or states that it uses a saved metric.
The interface separates proposed interpretation from executed results.
Results record context, snapshot, SQL, and result hashes.
The graph shows definition dependencies and the relationships used by the query.
It does not claim to visualize returned entity instances or observed execution lineage.
In Metric query mode, supporting documents provide background context; their text does not generate the SQL answer.
Open the published model to inspect their saved contents and evidence links.

The original sample execution and optional result explanation remain available in a collapsed compatibility section.
That section follows the active-version behavior of the existing sample API.

## API

| Route | Purpose |
| --- | --- |
| `GET /demo/api/playground?source=<connection>` | Published versions and their saved metric summaries |
| `POST /demo/api/playground/interpret?source=<connection>` | Retrieve semantic context and stage a typed interpretation |
| `POST /demo/api/playground/run?source=<connection>` | Execute a stored, version-bound interpretation |

Interpretation requires the pack, snapshot, runtime session, selected version, context hash, and question.
The optional metric name selects a saved metric explicitly and overrides the answer mode.
`mode` accepts `auto`, `metric`, or `document`. Existing API clients default to `metric`; the UI explicitly selects `auto`.
Document interpretations return `kind: document`, passages, and an artifact hash. Their run responses contain cited claims instead of SQL.
Execution accepts the pack, snapshot, runtime session, and plan ID; it does not accept SQL or a replacement query.

## Product boundary and next integration work

Semantic Hub owns authoring, validation, review, version comparison, and publication.
The playground is a consumer of that published-release contract.
External interpretation applications should submit proposals for review and consume pinned published releases.
External proposal ingestion, remote source imports, authenticated registry adoption, and consumer adapters remain separate increments.
Independent model identity is still needed before one connection can host multiple semantic models.
The reference Cyber Semantic Layer app informed the interpretation and evidence presentation; its domain-specific Cypher is not imported.

## Verification

- Backend coverage: published-only access, source/session/hash binding, expired plans, typed-request validation, fixed semantics, and draft independence.
- Saved-metric browser journeys run against all four datasets at desktop and mobile sizes.
- Additional live GPT-4o checks use the configured local manufacturing release.
- Live verification returned 312 minutes for “What is the total planned maintenance time?” against manufacturing v1.0.
- “What caused the downtime?” requested clarification because the release contains no causal evidence.
- The existing manufacturing authoring, review, and publication browser workflow passed at desktop and mobile sizes.
- Browser script: `apps/helios/workbench/check_playground_browser.py`.
- Backend tests: `apps/helios/tests/test_demo_playground.py` and retrieval service tests.

## Published document answers — 14 October 2026

Playground can answer source-reported questions from reviewed library evidence attached to a published model.
This supports the EFPIA page 14 question without creating a new SQL metric.

```text
Question + selected published version
                 |
       Auto route or explicit mode
          /                     \
Metric query                Document evidence
Typed request               Bounded published passages
Compiled SQL                Proposed cited claims
DuckDB result               Quote, number, and scope checks
          \                     /
          Answer + version evidence
```

1. Review a document link in Supporting materials and apply it to the existing model draft.
2. Validate and publish that draft in Studio.
3. Select the new version in Playground.
4. Choose **AI · query data + documents** or **Document evidence** and enter the question.
5. Select **Interpret question** and inspect the retrieved passages.
6. Select **Answer from these documents**.
7. Expand the citation to inspect the source quotation, page, revision, and checksums.

For page 14, ask: `What was North America's share of the total prescription pharmaceutical market in 2025?`
The source-reported answer is **54.7%**, for USA and Canada at ex-manufacturer prices.
The existing USA new-medicine metric remains **74.1%**. Its launch cohort and geography differ.

Document answers need no additional reference SQL. Existing model metrics retain their publication validation requirements.
Document answers do not create fact tables, change metrics, or publish releases.

### Evidence boundary

- Only library-linked operator attachments frozen in the selected published release supply passages.
- Merely uploading, reviewing a link, or applying it to an unpublished draft does not make it available to Playground.
- Direct notes, built-in source documents, unrelated models, and the live document library are outside this initial answer path.
- Retrieval uses local keyword overlap, at most 12 passages, and a 45,000-character serialized evidence budget.
- Auto routing can translate retrieval keywords. This increment adds no vector database dependency.
- The server verifies attachment hashes, citation IDs, and exact quotations after whitespace normalization.
- Citations retain adjacent source sentences when available, preserving nearby year and scope statements.
- One bounded regeneration may repair an invalid response; all checks still apply.
- Numbers in claims must occur in their cited original-text excerpts. Numeric claims cannot rely solely on AI visual transcription.
- A separate LLM check tests whether quotations support each claim's meaning and scope.
- The LLM check is fallible. Exact quotations and reviewer-approved links do not establish the truth of every source assertion.
- Missing evidence requests clarification or returns insufficient evidence. Unverified quotations, numbers, or scope checks reject the answer.
- Plans expire after five minutes and remain bound to the source, runtime session, publication, context, snapshot, and artifact hashes.
- This is local release isolation. Enterprise identity, document ACLs, multi-metric synthesis, and general cross-model Q&A remain future work.

Tests cover API bindings, unpublished evidence, draft changes, citations, unsupported numbers, scope failures, and saved-metric compatibility.
See [live verification](document-answers-verification.json) for GPT-4o results against an isolated pharmaceutical workspace.

## AI tool planning and period correction — 14 October 2026

The default AI mode can use a metric query, document evidence, or both within one published model.
The planner receives metric definitions and published document topics. A combined plan names one existing metric.
The compiler validates the typed request before DuckDB runs it. The answer model receives executed results and frozen document passages.
Each final claim cites an executed SQL result or a verified document excerpt.

```text
Original question -> AI tool plan -> typed metric request -> DuckDB result
                             |                                  |
                             +-> published passages ------------+
                                                                |
                                              checked cited AI answer
```

The UI shows a proposed tool plan before execution. It does not display the router's unverified answer text.
The original question stays unchanged throughout planning and execution.
Explicit years must occur in selected evidence and the final cited excerpts. A separate AI check evaluates scope and meaning.
Year presence is a necessary check, not proof of scope; the semantic check remains fallible.

Regression example: `北美在2020到2024年整个处方药市场中占多少`.
Page 14 reports a 2025 observation. It cannot answer that 2020–2024 question.
The application requests clarification or reports insufficient evidence without presenting 54.7% as the answer.

Combined demo question:
`What is the US share of sales for new medicines launched during 2020–2024, and how does it differ from North America's share of the total prescription market in 2025?`

Expected tool use: execute `us_new_medicine_sales_share_percent`, then read the published page 14 passage.
Expected answer: 74.1% from SQL and 54.7% from the document, with their different geography and population clearly stated.
The evidence does not justify treating the percentages as equivalent or subtracting them as a like-for-like market change.
Saved metrics remain deterministic and do not require an AI answer.
See [live tool verification](ai-query-tools-verification.json).

## Finance and power customer acceptance

See the [finance story](finance-customer-demo-story.md), [power story](power-customer-demo-story.md), and [forty query cases](customer-demo-queries.json).
The isolated runner compares supported query results with independent SQL.
It requires unsupported questions to return clarification without a plan ID.
Cases include unit confusion, missing metrics, excluded populations, forecasts, relative dates, mutations, secrets, and injected instructions.

The local engine now accepts compiler-generated `CAST('YYYY-MM-DD' AS DATE)` literals.
It still rejects arbitrary casts, external access, and data modification.
Observed sample dates remain valid even when they exceed the LLM's training cutoff.
An omitted period means the whole selected snapshot. Relative periods still require clarification.
These are local Playground rules. The shared retrieval service and consumer permission contracts are unchanged.

```bash
PYTHONPATH=shared:. python apps/helios/workbench/check_customer_queries.py --live-ai
```

The runner uses `~/tokens/openai` and GPT-4o by default.
It creates temporary workspaces and publishes test versions there only.
It does not approve or publish customer demo versions.
Without `--live-ai`, it verifies reference SQL only; it does not claim AI acceptance.
