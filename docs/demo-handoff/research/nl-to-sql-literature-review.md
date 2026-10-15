# Recent NL to SQL Agent Advances and GEL Implementation Review

Updated 7 October 2026 · Targeted engineering review

Recent research advances NL-to-SQL agents through active database exploration, structured execution memory, evidence-based repair, and training over tool-use trajectories. For GEL Phase 1, the recommended combination is PV-SQL-style probing and verification, AgentSM-style experience retrieval, and MIRA-style repair memory.

This recommendation is an engineering synthesis. None of the reviewed papers establishes guaranteed correctness for unrestricted finance questions.

**Search scope and evidence**

The updated search specifically targeted 2026 agent architectures, tool use, execution feedback, memory, verification, and reinforcement learning. Seven agent papers form the main comparison. ReViSQL supplies a complementary finding on training-data quality. Older work appears only where it supports evaluation.

Primary sources were retrieved from arXiv and ACL Anthology. Records were deduplicated by DOI/arXiv identifier and title/author. Conference status is stated only where supported by the retrieved record; other entries are labeled preprints. Method sections were inspected for AgentSM, PV-SQL, and MIRA. Other summaries use the retrieved primary abstracts and publication records. Experiments were not reproduced.

This is a targeted review, not an exhaustive systematic review. Academic MCP tools were unavailable, and the OpenAlex fallback failed on DNS resolution. Web retrieval supplied the primary evidence. Benchmark results use different models, datasets, and budgets; they must not be treated as a common ranking.

**Recent papers**

| Paper and publication status | Agent advancement | Evidence and limitation | GEL implication |
|---|---|---|---|
| Biswal et al., [AgentSM: Semantic Memory for Agentic Text-to-SQL](https://arxiv.org/abs/2601.15709). 22 January 2026; arXiv preprint 2601.15709. | A planner and schema-linking agent reuse structured execution trajectories. Composite tools combine recurring operations. | Reports 44.8% execution accuracy on Spider 2.0 Lite. Its implementation uses coding agents; a constrained Agent Studio adaptation needs separate evaluation. | Retrieve reviewed query procedures and examples before repeating exploration. Keep planning and SQL generation in a shared context. |
| Jiang et al., [SQLAgent: Learning to Explore Before Generating as a Data Engineer](https://arxiv.org/abs/2602.01952). 2 February 2026; arXiv preprint 2602.01952. | Separates database exploration from deployment. Builds a knowledge base of schema fragments, executable queries, and natural-language descriptions. | Reports improvements on large-scale benchmarks. Executable examples alone do not establish approved finance meaning. | Prepare tested usage examples alongside Helios definitions before user rollout. |
| Tian and Zhang, [PV-SQL: Synergizing Database Probing and Rule-based Verification for Text-to-SQL Agents](https://arxiv.org/abs/2604.17653). 19 April 2026; arXiv record states acceptance to Findings of ACL 2026. | Uses adaptive database probes and a deterministic constraint checklist to guide SQL generation and repair. | Reports improved BIRD accuracy and efficiency. The verifier covers selected constraint types, not complete SQL semantics. | Inspect actual values when needed; check required conditions explicitly before accepting a candidate. |
| Dai et al., [ReEx-SQL: Reasoning with Execution-Aware Reinforcement Learning for Text-to-SQL](https://aclanthology.org/2026.acl-long.35/). ACL, July 2026. DOI: 10.18653/v1/2026.acl-long.35. | Incorporates execution feedback during reasoning and rewards useful exploration. Uses tree-based decoding for sampling efficiency. | Reports 65.3% BIRD accuracy at 7B scale. Results require its training and inference setup, not just a prompt change. | Capture useful tool trajectories now; consider policy training after establishing reliable labels. |
| Liu et al., [MIRA: Evidence-Verified Repair Memory for Text-to-SQL Correction](https://arxiv.org/abs/2608.06950). 7 August 2026; arXiv preprint 2608.06950. | Splits confirmed corrections into reusable repair items. Verifies their applicability against current database evidence before rewriting SQL. | Evaluates 1,785 queries across 14 databases. Its memory depends on confirmed historical corrections from the same database. | Seed a small reviewed correction library. Measure both successful repairs and damage to previously correct queries. |
| Kakkar et al., [ReToolSQL: Agentic Reinforcement Learning for Robust Text-to-SQL](https://arxiv.org/abs/2608.27796). 28 August 2026; arXiv preprint 2608.27796. | Combines supervised learning on verified traces with reinforcement fine-tuning over multi-turn tool use. | Reports 74.32% single-pass BIRD development accuracy for its strongest 31B configuration. Benchmark rewards and teacher traces do not transfer automatically to GEL. | A later approach for learning when to inspect, verify, and repair; not a Phase 1 dependency. |
| Chen et al., [DualSQL: Text-to-SQL with Multi-Agent Reinforcement Learning](https://arxiv.org/abs/2609.18135). 16 September 2026; arXiv preprint 2609.18135. | Jointly trains schema-linking and SQL-generation agents with shared weights. Adds rollout controls and robust execution match rewards. | Reports 71.1% BIRD development accuracy with an 8B model trained on 3,755 examples. This requires model training beyond Agent Studio configuration. | Consider joint optimization after collecting trustworthy GEL examples and building a suitable reward environment. |

A complementary result comes from Zhu et al., [ReViSQL: Achieving Human-Level Text-to-SQL](https://arxiv.org/abs/2603.20004), March 2026, arXiv preprint. The authors emphasize corrected training data and verifiable rewards rather than additional agent complexity. Its headline result uses an expert-verified BIRD Mini-Dev set and a proxy human comparison. It is not evidence of guaranteed enterprise accuracy. For GEL, verified examples and labels deserve priority alongside workflow design.

**Practices to adopt in Phase 1**

1. **Explore to resolve a specific uncertainty.** Give the agent bounded tools for value inspection and relationship checks. PV-SQL supports question-directed probing. A sample can reveal a code format, but cannot certify whole-table uniqueness. [PV-SQL methods](https://arxiv.org/html/2604.17653v1).
2. **Reuse structured experience.** Store approved examples with their semantic definitions, tools, and validation evidence. AgentSM supports trajectory reuse; GEL should scope retrieval by dataset and semantic version. [AgentSM methods](https://arxiv.org/html/2601.15709v1).
3. **Verify explicit requirements.** Check required filters, reporting periods, metric grain, and currency treatment. PV-SQL’s rule checks motivate this step but do not prove complete business correctness. [PV-SQL verification](https://arxiv.org/html/2604.17653v1).
4. **Repair only with supporting evidence.** Retrieve a relevant correction, check whether its error recurs, and preserve unrelated logic. Revalidate the result and record regressions. [MIRA methods](https://arxiv.org/html/2608.06950v1).
5. **Separate memory publication from query execution.** A successful query may enter a review queue. Only reviewed outcomes become reusable knowledge. This is a proposed GEL control, not a demonstrated guarantee from the papers.

Start with one planner that retains the question, observations, and candidate history. AgentSM uses two tightly coupled agents; it does not establish that every deployment needs multiple agents. Add a specialist explorer only if controlled evaluation shows a benefit.

**Implementation in Agent Studio**

The local source supports the required extension points. This assessment is based on code inspection; the complete GEL workflow has not been implemented or integration-tested.

| Capability | Inspected evidence | Implementation decision |
|---|---|---|
| Repeated tool use and bounded agent iterations | [agents_smart.py](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/crewai/agents_smart.py) | Use one regular Finance Query Agent with explicit tools and a configured iteration limit. Enforce database budgets separately in the service. |
| Planning and agent coordination | [crew_smart.py](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/crewai/crew_smart.py) | Planning tools and sequential/hierarchical processes exist. Hierarchical manager tools are cleared, so a manager cannot serve as the direct database operator. |
| Structured Python tool inputs | [Custom tools guide](../../cloudera-ai-agent-studio/docs/user_guide/custom_tools.md) | Use Pydantic contracts for semantic requests, probes, candidate identifiers, and evidence. |
| Bedrock configuration | [llm_kwargs.py](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/crewai/utils/llm_kwargs.py) | Retain Bedrock; verify the chosen model’s tool behavior and authentication in GEL. |
| MCP integration | [mcp.py](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/crewai/mcp.py) | The inspected path launches Python/Node servers over stdio. Use a Python API wrapper or stdio adapter for remote Helios services. |
| Guardrails and traces | [Guardrail loader](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/guardrails/loader.py), [execution traces](../../cloudera-ai-agent-studio/studio/workflow_engine/src/engine/crewai/execution_trace.py) | Reuse model/tool checks and tracing. Build SQL enforcement and reviewed memory separately. |
| Existing SQL execution | [cdw_sql_query/tool.py](../../cloudera-ai-agent-studio/studio-data/tool_templates/cdw_sql_query/tool.py) | This tool executes supplied SQL and fetches all rows. Replace it with a bounded, validated executor for this workflow. |

The proposed tools are `get_query_context`, `probe_data`, `validate_candidate`, `execute_candidate`, `get_repair_examples`, and `finalize_answer`. They are additions to build, not existing Agent Studio functions.

```text
Agent Studio question -> Finance Query Agent <-> Approved context / memory
                                  |
                                  v
                           Bounded data probes
                                  |
                                  v
                         Compile / verify candidate
                                  |
                                  v
                         Execute / inspect evidence
                                  |
                     +------------+------------+
                     |                         |
                  Finalize                Targeted repair
                     |                         |
              Answer + evidence           Revalidate / stop
```

For approved metrics, the agent produces a typed semantic request and Helios compiles it. Probing uses separate restricted operations. Requests outside the supported semantic scope trigger clarification or a visible stop. A general free-form SQL path requires separate design and evaluation.

The query service stores candidates and issues identifiers bound to SQL, session, authorization scope, and semantic version. Execution rechecks that binding and the validation rules. Read-only database permissions, deadlines, and result limits apply independently of model instructions. These are proposed implementation controls.

The final answer path must check that reported values correspond to execution evidence. Returning an evidence object from a tool alone does not prevent later model fabrication. Implement and test an output gate or deterministic result rendering. Agent iteration limits likewise do not guarantee that the last answer is supported.

**Reusable UOB and platform materials**

The [UOB implementation](../../uob-ai-data-operations-workspace/architecture.md) supplies typed plans, checksum-pinned semantic models, SQL checks, and reference-result comparison. Its [semantic preparation](../../uob-ai-data-operations-workspace/demo/app/semantic_workflow.py) currently has a narrow authoring scope. Business-rule descriptions do not automatically become SQL filters. GEL must validate any extension to joins or more complex metrics.

UOB uses LangGraph and Trino; GEL will adapt the contracts to Agent Studio and Impala. Its [verification record](../../uob-ai-data-operations-workspace/demo/VERIFICATION.md) does not establish live GEL banking-query acceptance or per-user delegation.

[Helios](https://github.com/christopheraburns/helios) supports the semantic preparation and compilation path. [Ray Serve on CAI](https://github.com/FerdinandZhong/ray-serve-cai) is a later serving option. [Training with Ray](https://github.com/FerdinandZhong/smart-router-training) offers training infrastructure, but does not implement the reviewed SQL training methods as a ready GEL solution.

**Evaluation before rollout**

Build a reviewed question set and separate held-out questions from examples used for prompting or memory. Keep paraphrases and closely related question templates in the same split. Freeze the model, data snapshot, semantic release, and memory library for each comparison.

Compare the same questions under four configurations: schema-only baseline; approved semantics; semantics plus probing/verification; and the same workflow with reviewed memory. This measures the contribution of each addition. Training is outside the Phase 1 comparison.

| Measure | What to report |
|---|---|
| Correctness | Correct answers divided by all answerable test questions; include unresolved failures and abstentions in the denominator. |
| Precision and coverage | Correct answers divided by answered questions, alongside the fraction of answerable questions answered. |
| Repair behavior | Initially wrong queries corrected and initially correct queries made wrong. |
| Clarification | Appropriate questions, preserved context across turns, and correct handling of unsupported requests. |
| Execution controls | Write rejection, unauthorized objects, stale candidate rejection, timeouts, and truncation. |
| Efficiency | Tool calls, token use, p50/p95 latency, and cost per correct answer. |

Independent reference queries and finance review should cover duplicate joins, nulls, cancellations, currencies, time boundaries, empty results, and zero denominators. Test multiple data conditions where practical. Agreement on one snapshot does not establish semantic equivalence. [Semantic Evaluation with Distilled Test Suites](https://aclanthology.org/2020.emnlp-main.29/).

Interactive testing should include ambiguous questions and follow-ups, following the concerns examined by [BIRD-INTERACT](https://arxiv.org/abs/2510.05318). GEL’s tests remain read-only. Agree acceptance thresholds before tuning and retain failure examples for review.

The [Phase 1 proposal](phase_1_proposal.md) translates these findings into milestones and ownership. Resource sizing follows scope confirmation. The first deliverable is a controlled agent workflow with measured accuracy and reviewed experience, not a claim of universal correctness.
