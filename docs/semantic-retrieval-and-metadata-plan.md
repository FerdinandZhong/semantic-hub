# Bounded semantic search and metadata use

Status: shared indexed core and MCP enforcement implemented on 11 October 2026; consumer and production acceptance remain open.
See [implementation, contracts and measured results](semantic-retrieval.md).
The plan below preserves the original requirements and baseline gaps for acceptance tracking.
This is a prerequisite for the reusable Helios query demo.
The full catalog remains server-side. It must never become the default LLM prompt or a tool-result fallback.

The local Studio supplies reviewed definitions, stable IDs, immutable context versions and parsed SQL dependencies.
The separate shared retrieval service now implements indexing and bundle enforcement. Studio publication still needs an adapter to the MCP registry.
See [current progress and consumer requirements](SEMANTIC_FOUNDATION_STATUS.md).

## Model discovery versus definition retrieval

Model discovery chooses an authorized published model and release.
Definition retrieval finds the necessary objects within that selected release.
Current MCP uses `list_models`, `discover_models`, and `resolve_context` for inventory, discovery, and bounded definitions.
The local Hub lists configured source models and supports name/type/status filters.
That Hub filter is not the MCP relevance-search service.
Studio releases are not automatically registered in MCP.

Connect Studio publication to a compatible approved-model registry before exposing its releases to downstream search.
Preserve context-package and Ossie-document hashes separately.
UOB and Semantic Guardrails must adopt a pinned compatible release through their own adapters.
Publishing a model must not automatically activate it in either consumer.

## Original baseline gaps (10 October; retained for traceability)

The following baseline predates the indexed retrieval implementation.
`describe_model`, `describe`, and `search_semantics` are no longer registered agent tools.
Current contracts are in [semantic-retrieval.md](semantic-retrieval.md).

Helios already implements lexical `search_semantics` in `apps/helios/mcp/server.py`.
It searches dataset, field and metric names, descriptions and synonyms.
Its tool limit defaults to 10 matches and clamps at 100.
A result-count limit alone does not bound description lengths, dependency expansion or accumulated conversation context.
`describe_model` returns the full model and is available among the MCP tools.
The conversation system prompt requests semantic search before compilation, but a prompt instruction is not a service-enforced prerequisite.

The UOB reference implementation is archived at `demo-handoff/reference/uob/app/semantic_retrieval.py`.
`SemanticIndex.bundle()` filters permitted fields, ranks lexical matches and resolves metric and join dependencies.
Its existing defaults cap a bundle at five datasets, 100 fields and 24,000 serialized characters.
It asks for clarification when matching is ambiguous or dependencies exceed the limits.
`validate_request()` checks the proposed semantic request against the retrieved bundle.

The archived retrieval tests include one 2,000-distractor-table case with 30 fields per distractor.
That check verifies a small output for one question. It is not a 2,000-by-40 recall or latency benchmark.
Current lexical retrieval and character limits are foundations. Token accounting and scalable indexing still require work.
Extract reusable behavior into Helios without importing UOB application dependencies into the shared core.

## Offline metadata preparation

```text
Database schemas + reviewed Ossie releases + optional catalog enrichment
                                |
                                v
              Normalize fields, meanings, relationships and provenance
                                |
                                v
              Versioned search index + dependency graph + policy scope
```

Technical metadata comes from database discovery or typed fixture schemas.
Capture catalog/schema/table/column identifiers, types and declared keys.
Profile only bounded, approved values when needed. Do not embed complete source tables.

Business metadata comes from reviewed definitions and Ossie releases.
Capture metric expressions, synonyms, grain, units, time basis, inclusion rules and join meaning.
A description is not automatically an executable filter. Store and validate executable rules separately.

Relationship metadata supplies join paths and entity-key mappings.
Store reviewed cardinality, key uniqueness evidence and allowed join direction.
Preserve roles such as sender versus receiver. Do not let lexical similarity select an arbitrary relationship.

Document metadata supplies asset/version/page-or-paragraph/chunk references and canonical entity keys.
Keep document-text retrieval separate from table/metric retrieval.
Link the two through reviewed entity mappings and typed assertions.

Governance metadata supplies source scope, release hash, review state and policy revision.
Apply real caller policy before ranking and again before execution.
Classifications and glossary labels cannot grant database permissions.

Lineage metadata supports traceability and source impact analysis.
It is not an automatic join instruction or proof that a transformation preserves metric grain.
Atlas can enrich terms, ownership, classifications and lineage when available.
The local demo must work with its fixture catalog and Ossie releases without an Atlas dependency.
Do not assume Atlas supplies embedding search in the selected deployment.

Each index record needs a stable ID, dataset ID, model/release hash, metadata origin and update fingerprint.
Rebuild or invalidate entries when a source schema, semantic release or approved mapping changes.
Partition indexes and caches by dataset/model and enforce policy restrictions before returning candidates.
Keep hidden evaluation labels, answers and unrestricted profiling data out of these indexes.

## Online query contract

```text
Question + selected pack + caller scope
                 |
                 v
Extract intent/terms using question and a compact pack summary
                 |
                 v
Search permitted metadata -> ranked candidate IDs and brief definitions
                 |
                 v
Select metric/table -> clarify ambiguity -> expand required dependencies
                 |
                 v
Enforce context budget -> issue versioned semantic bundle and bundle ID
                 |
                 v
LLM typed request -> validate bundle scope -> Helios compile -> bounded execute
```

1. Bind the request to the selected pack, model release and current caller scope.
2. Keep the original question and add optional structured search terms and explicit date/entity constraints.
3. Search a server-side index of permitted metrics, datasets, columns and glossary terms.
4. Rank a small candidate set and return stable identifiers with concise explanations.
5. Resolve the intended metric and requested dimensions. Ask when the business meaning remains ambiguous.
6. Add only required expression fields, keys, executable rules and reviewed join paths.
7. Enforce field, dataset, character and tokenizer-based budgets before sending any context to the LLM.
8. Bind an immutable bundle ID to its content hash, release, dataset, policy revision and request scope.
9. Accept only a typed semantic request that resolves inside that bundle.
10. Recheck the bindings and execution permissions before running compiled SQL.

A second bounded search is allowed when a needed definition is missing.
Replace irrelevant context rather than appending an unbounded sequence of search results.
Use the exact selected metric as the dependency-graph anchor when available.
Do not connect unrelated high-ranking fields merely because they share words with the question.
Keyword extraction is optional and must not require the full schema as input.
LLM relevance checks can refine candidates; deterministic code enforces scope and budgets.

## Initial budget contract

Use the existing five-dataset, 100-field and 24,000-character caps as conservative ceilings.
Add a proposed 6,000-token ceiling for the semantic bundle using the configured model's tokenizer.
Configure the total input budget independently and reserve room for the answer.
The total input includes system instructions, tool schemas, history, semantic context, document passages and tool results.
If the model window is smaller, lower the component budgets to fit it.
These are initial limits to benchmark, not established optimal values or a characters-to-tokens conversion.

Expose only bounded semantic-search and describe operations to the query agent.
Keep full-model inspection in an authorized, paginated UI/API outside the LLM tool context.
Prevent indirect full-model leakage through errors, diagnostics, cached history and oversized tool responses.
Compilation and execution require a valid bundle binding; prompt instructions alone cannot enforce this.
Fail with clarification when required dependencies exceed a budget. Never drop required filters to make a request fit.

## Metadata examples

- “Electricity consumption”: retrieve the measured-import metric, kWh units, Singapore reporting date and exclusions for estimated/missing readings.
- “Maintenance downtime by line”: retrieve work orders, assets, the asset join key and the planned-downtime definition.
- “Batches with documentation deviations”: retrieve batches, deviations and their reviewed relationship, then linked report evidence if requested.
- “Outgoing payments”: retrieve the reviewed sender-outflow definition and fixed synthetic FX rule; clarify alternative net-flow meanings.

Only these relevant definitions and their dependencies enter the query prompt.
The complete pack catalog remains available to server-side search and the preparation UI.

## Implementation tasks and order

1. Define typed metadata records, search requests, candidates, semantic bundles and bundle bindings in Helios.
2. Adapt current `search_semantics` and UOB dependency/budget logic into one retrieval service.
3. Build an offline lexical index at pack preparation; keep the backend replaceable for later hybrid lexical/vector retrieval.
4. Add dataset/model/policy filtering and index invalidation before ranking.
5. Integrate bundle generation and request validation into the existing conversation/MCP path.
6. Remove full-model tool responses from that agent path and enforce cumulative input-token budgets.
7. Add cross-pack, ambiguity, dependency and context-window acceptance tests.
8. Benchmark a 2,000-table-by-40-field catalog with labeled relevant and confusing matches.
9. Add embeddings only if the same evaluation shows a useful improvement.

The preceding consumer contract and publication-to-registry bridge are prerequisites for sharing newly authored Studio releases.
Do not label the local canvas search or review-table filtering as completed semantic retrieval.

This becomes milestone 1B, immediately after startup pack selection and before multi-sector LLM-query acceptance.
Semantic authoring and document work reuse this retrieval contract.
The first UI can show deterministic sample execution while milestone 1B is being completed.
It must not label that sample execution as accepted generic LLM planning.

## Acceptance gates

- The query agent never receives the full table/field catalog, including through tool results or conversation history.
- Every prompt and tool result stays within the configured model budget.
- All required metric dependencies and mandatory filters survive context construction.
- Compilation rejects names outside the retrieved bundle and stale or cross-pack bundle bindings.
- Ambiguous terms and conflicting join paths produce clarification.
- Unauthorized candidates never enter ranking results or diagnostic output.
- The benchmark reports recall@k, required-field recall, clarification behavior, token counts and p50/p95 retrieval latency.
- Evaluate paraphrases, unmatched terms, similar metric names, distractor tables, join roles and multi-turn scope changes.
- Keep benchmark labels and expected answers outside retrieval and reusable experience stores.

Define measured recall/latency targets after the baseline run. Security, scope and budget invariants are mandatory from the first implementation.
