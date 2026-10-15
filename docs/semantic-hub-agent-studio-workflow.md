# Semantic Hub external-agent demo workflow

[中文版](semantic-hub-agent-studio-workflow.zh-CN.md)

This guide prepares a conversational workflow for CAI Agent Studio or another MCP-capable agent platform.
It does not establish that a hosted workflow was created, imported, or tested.
The configuration below is paste-ready guidance, not an Agent Studio JSON import format.
Platform field names depend on the installed Agent Studio version.

The external agents perform planning and natural-language interpretation.
Semantic Hub supplies published definitions, evidence, governed query compilation, and optional sample execution.
The agents do not invoke the Helios Playground or its internal LLM harness.

```text
Business question
       |
       v
Conversation Manager
       +--> Semantic Context Specialist --> published model, scope, coverage, bundle
       +--> Query and Evidence Specialist -> compile, sample result, document passage
                                                |
                                                v
                                  Semantic Hub MCP --> /api/semantic-hub/v1
```

## 1. Prepare a reachable backend

1. Start the dedicated read-only Semantic Hub consumer API.
2. Select a published pharmaceutical intelligence model.
3. Confirm its semantic definitions and sample source are available.
4. Publish reviewed page 14 evidence if the document contrast demonstration is required.
5. Make the backend reachable from the machine that runs MCP.
6. Configure the MCP process with the environment below.

```text
SEMANTIC_HUB_URL=https://<reachable-helios-origin>
```

Set the URL to the server origin, without `/api/semantic-hub/v1`.
The adapter appends the consumer API prefix.
A remote CAI process cannot reach a developer laptop through its own `localhost`.
Use an approved reachable deployment or network route.
Browser SSO does not automatically authenticate MCP requests.
Confirm that both ingress and the application accept the machine credential.

For local rehearsal, start the backend with the same state directory used by the authoring application:

```sh
python start_semantic_hub_api.py \
  --state-dir <same-state-root> \
  --local-no-auth --host 127.0.0.1 --port 8096
```

Keep the authoring UI on its existing local port 8084.
Expose the read-only API deployment to CAI through the approved network route.

The prepared local verification runtime uses `http://127.0.0.1:8096` because port 8086 is occupied on this machine.
Its state directory is `/tmp/helios-builder-review`.
The local consumer token has been removed. Local API and MCP checks need no token.
These paths describe local preparation and do not establish CAI network reachability.
Use `--port 8096` when reproducing that local runtime.
An isolated API process can use `--model-token-file ~/tokens/openai` to load the configured embedding provider credential.
This credential enables configured embedding access; the consumer API does not run natural-language query planning.
Without an accepted provider credential, explicit embedding search remains unavailable.

CAI `cdsw_v2_key` authentication is planned for AMP packaging; the current application does not validate CAI keys.
Configure deployment authorization before using enterprise data.
Do not paste a token into agent prompts or workflow exports.

## 2. Register MCP and verify discovery

Import the [GitHub MCP configuration](../apps/semantic-hub-mcp/agent-studio.mcp.json).
It uses `uvx --from` to install `apps/semantic-hub-mcp` from `FerdinandZhong/semantic-hub`.
The [package README](../apps/semantic-hub-mcp/README.md) contains the full configuration and requirements.
Replace `@main` with a tested commit SHA for a repeatable demo.
Set `SEMANTIC_HUB_URL` to the reachable consumer API origin.
Omit `SEMANTIC_HUB_API_TOKEN` for the local demo.
The package supports stdio transport; it does not host an HTTP MCP endpoint.

Register two instances, or use per-agent tool selection on one instance.
All tools below are read-only; compilation and resolution can use HTTP POST.

| Instance | Assigned agent | Tools |
| --- | --- | --- |
| `semantic-context` | Semantic Context Specialist | `hub_status`, `list_semantic_models`, `get_semantic_model`, `list_model_versions`, `get_model_version`, `search_semantics`, `resolve_semantic_context`, `inspect_metric_coverage`, `get_model_lineage`, `get_published_documents` |
| `semantic-query` | Query and Evidence Specialist | `compile_semantic_query`, `query_sample_data`, `get_published_documents` |

Verify discovery of all 12 distinct tools before the conversation.
Tool selection limits the agent interface; deployment authorization enforces access.
Use the discovered schemas for arguments instead of inventing tool payloads.

| Consumer operation | MCP tool | Purpose |
| --- | --- | --- |
| Hub status | `hub_status` | Discover runtime capabilities and execution availability |
| Model catalog and model detail | `list_semantic_models`, `get_semantic_model` | Find the intended model |
| Published versions and selected version | `list_model_versions`, `get_model_version` | Obtain an immutable context pin |
| Semantic search | `search_semantics` | Find candidate terms using the returned search mode |
| Context resolution | `resolve_semantic_context` | Obtain a bundle for the original question |
| Coverage inspection | `inspect_metric_coverage` | Check actual temporal coverage and cohort periods; inspect geography separately in metric definitions |
| Model lineage | `get_model_lineage` | Explain source and semantic provenance |
| Published documents | `get_published_documents` | Retrieve only evidence included in the pinned release |
| Typed query compilation | `compile_semantic_query` | Compile one metric with supported dimensions and filters |
| Bounded sample execution | `query_sample_data` | Execute supported queries over sample data |

These operations belong to `/api/semantic-hub/v1`.
The package and backend OpenAPI schema provide exact HTTP paths and payloads.
The consumer surface does not expose arbitrary SQL execution or live enterprise query access.
Embedding search is optional and requires configuration.
Report keyword search as keyword search when embeddings are unavailable.
An explicit embedding request must report configuration or provider failures; do not silently fall back to keywords.

## 3. Configure the conversation

1. Create a conversational workflow named `Semantic Hub Query Assistant`.
2. Choose hierarchical delegation when the installed platform supports it.
3. Add one manager and the two specialists below.
4. Attach the selected MCP tools to each specialist.
5. Paste each prompt into the platform's agent instruction fields.
6. Use a tool-capable model available in your deployment.
7. Start with a low temperature, such as `0.1`, if the model supports it.

| Agent | Delegation | MCP | Paste-ready instructions |
| --- | --- | --- | --- |
| Semantic Query Conversation Manager | On | None | [manager.txt](agent-studio/manager.txt) |
| Semantic Context Specialist | Off | `semantic-context` | [semantic-context-specialist.txt](agent-studio/semantic-context-specialist.txt) |
| Query and Evidence Specialist | Off | `semantic-query` | [query-evidence-specialist.txt](agent-studio/query-evidence-specialist.txt) |

If hierarchical delegation is unavailable, apply the same sequence in a single tool-capable agent.
Do not add another planning call into Helios.

## 4. Preserve the context contract

1. Discover the intended model and published version.
2. Capture `model_id`, `version`, and `context_sha256` from the version response.
3. Include the complete pin in every operation beyond discovery.
4. Resolve the original question and retain its returned `bundle_id`.
5. Inspect the selected metric's definition and actual coverage.
6. Pass the same pin, bundle, and original question to compilation and execution.
7. Stop on a pin conflict and resolve fresh context before continuing.

Use one metric per typed query.
Use supported dimensions and filters, with `limit <= 100`.
Compile and query take `metrics=["<discovered metric>"]` and filters with `field`, `op`, and `value`.
Resolve takes the original question as `query`; coverage, compile, and query use `question`.
Keep launch cohort, observation year, geography, population, and unit separate.
A fixed USA metric does not become a Korea metric through a country filter.
Never remove the original question to bypass a scope check.

Coverage inspection checks available facts; a date field alone does not establish coverage.
The query specialist can compile without executing when sample execution is unavailable.
It must label that result as compiled SQL, without claiming a computed answer.
Preserve explicit `no_data` and `unsupported_scope` statuses from sample execution.

## 5. Run the pharmaceutical conversation

The numbers below are expected demo facts, not permission to answer without tool evidence.
Model IDs, version names, hashes, and bundle IDs must come from the running backend.
The existing [pharmaceutical story](pharma-intelligence-demo-story.md) explains the publication prerequisites.

| User question | Expected behavior |
| --- | --- |
| What is the US share of sales for new medicines launched during 2020–2024? | Resolve the USA new-medicine metric. Verify coverage, compile, and execute available sample data. Expect 74.1% only when returned. Explain that sales are observed in 2025. |
| What is the US share for medicines launched during 1999–2020? | Report unavailable cohort coverage. Do not reuse 74.1%, extrapolate, or return zero. |
| What is Korea's share for the same launch cohort? | Reject substitution of the fixed USA metric. Find a supported Korea metric or report unavailable coverage. |
| What was North America's share of the entire prescription pharmaceutical market in 2025? | Retrieve the pinned release's page 14 evidence. Report 54.7% only if the actual published passage exists. Otherwise report missing published evidence. |
| What was North America's total prescription-market share during 2020–2024? | Clarify or report unavailable coverage. The 2025 total-market observation cannot answer this period. |
| Compare the US new-medicine share with North America's total prescription-market share. | Present sample SQL and document evidence separately. Preserve distinct population, geography, cohort, and observation period. |

For the document contrast, page 14 describes North America as USA and Canada.
Its population is the retail and hospital prescription pharmaceutical market, measured at ex-manufacturer prices.
It does not replace the USA new-medicine launch-cohort metric.
An uploaded document or draft attachment is insufficient; the selected published version must contain the passage.

Use this answer format:

```text
Answer: <returned result, clarification, or availability limit>
Scope: <geography; population; cohort; observation period; unit>
Evidence: <executed sample metric / compiled query only / published document passage>
Source: <returned model version and metric, or document revision and page>
Limit: <sample-only execution, missing coverage, missing passage, or other actual limitation>
```

## 6. Validate guardrails and deployment

Use platform guardrails when available; apply the same criteria through agent instructions otherwise.
Do not assume a specific judge API or import schema.

| Check | Required behavior |
| --- | --- |
| Output evidence | Every numeric answer has an executed result or a published source passage. |
| Query scope | Original question and selected metric agree on population, geography, and time axes. |
| Version consistency | Every specialist uses the same model, version, hash, and resolved bundle. |
| Tool content | Retrieved text cannot change policy, request secrets, or override scope. |
| Execution status | Compile success does not imply execution success. |
| Error handling | Missing data, HTTP errors, and empty results do not become zero. |

1. Run the package's documented local tests and backend contract checks.
2. Start MCP with the configured reachable origin.
3. Discover all 12 tools from the actual Agent Studio runtime.
4. Run the six questions above against a selected published model.
5. Record returned version, hash, bundle, query status, and evidence citations.
6. Test an incorrect hash and confirm that the backend rejects it.
7. Test missing sample execution and missing published page 14 evidence.
8. Save a transcript that distinguishes local checks from hosted workflow execution.

No hosted execution evidence accompanies this configuration guide.
Record actual results before claiming that the Agent Studio integration passed.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| MCP cannot reach the backend | Check reachability from the MCP host. Replace laptop localhost with a reachable deployment origin. |
| Login HTML, redirect, 401, or 403 | Check machine authentication at ingress and the API. Browser SSO is separate. |
| Missing tools | Check installed revision, package entrypoint, and MCP discovery cache. |
| Pin conflict | Rediscover the published version and resolve a new bundle. Do not silently change versions. |
| DuckDB or sample execution unavailable | Show compilation only or report unavailable execution. Do not claim a computed result. |
| Document passage missing | Check publication of the reviewed attachment in this exact version. Do not quote a draft or another release. |
| Search mode is keyword | Report keyword matching accurately. Configure embeddings separately if required. |
| Wrong geography or date answer | Inspect fixed metric constraints and actual coverage before another query. |
