# Indexed retrieval and agent integration

Implemented and tested locally on 11 October 2026.
This increment provides a shared retrieval core and a bounded MCP query workflow.
Downstream application adoption and production load acceptance remain separate work.

## Request path

```text
Published Ossie release -> immutable FTS5 index + dependency graph
                                      |
Trusted caller + adopted release ------+
                                      v
              permitted candidates -> selected metric + dependencies
                                      |
                                      v
                        bounded, expiring semantic bundle
                                      |
                                      v
Agent typed request -> bundle validation -> compilation -> execution authorization
```

The index builds before serving queries where the MCP startup adapter can prepare published releases.
Historical pinned revisions and newly changed artifacts can still require a first-use build.
The adapter reuses immutable model snapshots after preparation.
Index storage is currently process-local SQLite memory.
Restarts rebuild indexes and invalidate outstanding bundle IDs.

FTS5 locates candidates through an inverted index.
The implementation ranks permitted candidates by weighted lexical overlap.
It deliberately avoids corpus-dependent BM25 statistics influencing permission-filtered results.
No LLM, embedding service or source-data query runs inside retrieval.

Metric selection anchors dependency expansion.
Explicit matching fields must belong to its connected model component.
Required expression fields, primary keys and selected relationship keys remain in the bundle.
Ambiguous metrics, competing join paths, forbidden dependencies and excessive bundles require clarification.
Unsupported mandatory rules fail closed; the service does not silently discard them.
Opaque catalog annotations stay outside serving results.

## MCP tools

1. Call `discover_models(question)` when the application has not selected a model.
2. Call `resolve_context(question, model)` for a published release.
3. If the response needs clarification, ask the user to choose the business meaning.
4. Build a typed metric, dimension and filter request from the returned bundle.
5. Pass its `bundle_id` to `compile_query` or `run_query`.

Compilation uses the bounded model itself.
Missing, expired, cross-session, changed-policy and changed-release bindings fail before execution.
Existing execution authorization remains in force.
Unreviewed proposal fallback is removed from the MCP model store.
Full-model `describe_model`, broad `describe` and legacy `search_semantics` are no longer registered as agent tools.
Their Python implementations remain available to existing non-agent callers.
The console conversation exposes only `list_models`, `discover_models`, `resolve_context`, `compile_query` and `run_query`.
It rejects document tasks on this workflow until scoped document retrieval is verified.
Separate MCP document APIs remain unchanged and are outside this acceptance claim.

Discovery searches explicitly scoped models and returns choices.
It does not compare lexical scores between different model corpora to choose a winner.
It is not yet a paginated enterprise catalog with owner/domain filters.
Its cost grows with the number of adopted models; that scaling needs a separate benchmark.

The MCP adapter derives caller identity, session and policy revision from trusted server context.
Its current metadata authorization remains model-level.
The shared service supports explicit field allowlists, but MCP does not yet derive those from warehouse column policies.
Warehouse permissions are checked separately at execution.
Do not claim MCP field-level metadata isolation until that adapter exists.

## Shared application API

`Scope` is constructed by trusted application code, never by agent-supplied tool arguments.
`register` accepts publication evidence from a trusted adapter; it does not authenticate an arbitrary uploaded manifest.
Hashes establish integrity and binding, not publisher identity.

```python
from helios_core.retrieval.service import RetrievalService, Scope

service = RetrievalService()  # Register releases during application preparation.
manifest = service.register(
    model_id="payments",
    release_version="v1",
    document=reviewed_ossie_document,
    publication={"status": "published", "source": "trusted-registry", "reference": "release-v1"},
    context_sha256=reviewed_context_hash,
)
scope = Scope(
    principal_id=authenticated_caller_id,
    policy_revision=current_policy_revision,
    releases={"payments": manifest["release_id"]},
    allowed_fields={"payments": permitted_field_ids},  # frozenset of dataset.field
    context=trusted_session_and_purpose,
)
result = service.resolve_context(question, scope, model="payments")
if result["status"] == "ready":
    bounded_model = service.validate_request(result["bundle_id"], scope, typed_request)
    # Compile only bounded_model; recheck application action permissions.
```

Use `None` for a model's field scope only when model-level metadata access intentionally grants all fields.
An empty field set denies all field-dependent definitions.
The cache binds the exact question, model, optional metric, identity, permissions, policy, release and application context.
It stores at most 256 bundles by default, each valid for 300 seconds.
Returned objects are copies; client mutation cannot alter the retained bundle.

## Studio consumer export

`GET /demo/api/context/export?version=<published-version>` returns four objects:

| Object | Purpose |
| --- | --- |
| `manifest` | Model ID, release version, specification version, both hashes, release ID and publication provenance |
| `document` | Ossie document suitable for the existing UOB file loader |
| `context` | Complete reviewed Studio context, including units, grain, time rules and review evidence |
| `artifacts` | Frozen semantic layer, metadata, structural ontology, source documents, appended documents, and their hashes |

New versions freeze artifacts before calculating the context hash.
Export returns the stored artifacts, so later generator changes cannot rewrite approved evidence.
Legacy versions without stored artifacts use the compatibility generator.

Studio metrics now preserve descriptive business metadata in the HELIOS `business_context` extension.
Search indexes synonyms, example questions, units, grain, time rules, ontology concepts, and inclusion/exclusion descriptions.
Returned bundles preserve the validated business context.
Independent reference SQL stays outside the searchable model.
Typed fixed filters become aggregate CASE expressions, so they survive export and generic compilation.
Textual rules do not insert filters or supply currency conversions.
These changes enrich lexical retrieval; they do not add metric embeddings or a vector database.

Export requires a matching publication record, including for legacy versions accepted elsewhere in the local UI.
`release_id` binds model ID, business release version, document hash and context hash.
It distinguishes two reviewed contexts containing identical Ossie documents.
Canonical hashes use sorted JSON keys, compact separators and standard ASCII escaping.

The endpoint does not publish into the remote MCP artifact store or activate a downstream application.
UOB must import the document and retain the manifest and richer context through its adapter.
Guardrails must add its provider and bind mandatory facts separately from search relevance.
Neither sibling application was modified by this increment.

## Budgets

Bundles allow at most five datasets, 100 fields, 24,000 serialized characters and 6,000 tokens.
Supply the target model's tokenizer through `token_counter` for exact configured token accounting.
Without it, the implementation uses UTF-8 byte length as a conservative token bound.
That fallback is explicitly labeled in evidence; it is not a measured tokenizer count.

The conversation service checks complete messages, history and tool schemas before every LLM round.
It preserves history and rejects oversized input rather than silently dropping required context.
The default input ceiling is 16,000 tokens, using the same conservative fallback when no tokenizer is supplied.
Deployments must configure an input ceiling that leaves room for output within the selected model's context window.

## Verification

The checked-in [benchmark artifact](retrieval-benchmark.json) covers 2,000 tables, 80,000 fields and 40 labeled synthetic questions.
Labels remain in benchmark code and never enter retrieval.

| Warm operation | p50 | p95 |
| --- | ---: | ---: |
| Candidate search | 18.880 ms | 19.464 ms |
| Complete bundle construction | 26.362 ms | 27.543 ms |
| Uncached service resolution | 26.233 ms | 26.781 ms |
| Cached service resolution | 0.096 ms | 0.105 ms |

All 40 bundles succeeded and retained every labeled dependency.
Candidate recall was 100% at five and ten results, and 50% at one result.
Index construction took 5.049 seconds; service registration took 5.862 seconds.
Maximum bundle size was 1,963 characters on these fixtures.
These measurements cover one warm, sequential process on Darwin arm64.
They exclude HTTP, external authorization, network, inference and warehouse execution.
They do not establish production concurrency, multilingual recall or broad paraphrase quality.
The main timing corpus uses unrestricted model metadata; permission-negative probes run separately.
Large per-caller field allowlists require their own latency measurements.

Reproduce the benchmark from the repository root:

```sh
PYTHONPATH=shared python apps/helios/workbench/benchmark_retrieval.py
```

Run focused tests with an environment containing the demo requirements and pytest:

```sh
python -m pytest -c pyproject.toml -o 'pythonpath=. shared' \
  apps/helios/tests/test_retrieval_index.py \
  apps/helios/tests/test_retrieval_service.py \
  apps/helios/tests/test_mcp_bounded_retrieval.py \
  apps/helios/tests/test_conversation_input_budget.py \
  apps/helios/tests/test_talk_to_data.py
```

The `pythonpath` override prevents the application's `mcp` directory from shadowing the installed MCP SDK.
Tests cover actual MCP transport with synthetic models and mocked warehouse execution.
They also cover publication export, permission filtering, graph ambiguity, opaque metadata exclusion, budgets and binding invalidation.
The final focused retrieval, agent and authorization run passed 93 tests.
The Studio/runtime regression run passed 45 tests; the compiler regression run passed four tests.
The existing four-pack demo remains isolated from general LLM planning until its own adapter and acceptance gates are complete.
