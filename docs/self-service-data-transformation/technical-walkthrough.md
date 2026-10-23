# Technical walkthrough: from business scripts to a governed data pipeline

This proposed workflow turns business-owned CSV files and SQL or Excel logic into a reviewed PySpark pipeline.
It delivers Hive external tables and CSV files while IT controls table creation and sensitive-data access.
This document explains the design; it does not describe a deployed system.

## Read the diagram

![Six-agent workflow with business and IT approval gates](agent-workflow.png)

[Open full-size diagram](agent-workflow.png) · [Edit in draw.io](agent-workflow.drawio)

Read the first two rows from left to right.
Follow the third row from right to left, then follow the execution row from left to right.
Orange boxes represent business or IT decisions.
Dashed arrows return work for revision before execution.
The coordinator manages every step, although the diagram shows only its entry connection.

```text
Uploads → IT privacy gate → six-agent workflow → approved execution
                                ↑       |
                                └─ feedback
                                            |
                           Hive tables + CSV outputs → reconciliation
```

## A concrete example

Assume a business team prepares a daily sales report using CSV files and 15 SQL or Excel transformations.
Several scripts repeat customer lookups, date filters, and amount calculations.
The team wants automated processing but must keep receiving its existing CSV reports during transition.

The proposed workflow produces four PySpark jobs, approved table definitions, and the required CSV outputs.
Four jobs is an example outcome, not a fixed target.
The original business outputs must remain available even when fewer jobs produce them.

| Uploaded item | Example purpose |
| --- | --- |
| `orders.csv` | Order identifiers, dates, customer identifiers, and amounts |
| `customers.csv` | Customer lookup information, including potentially sensitive fields |
| MySQL scripts | Joins, filters, calculations, and aggregations |
| Excel logic | Lookup formulas, adjustments, rounding, and report layouts |
| Existing output CSVs | Baseline results for reconciliation |

## 1. Receive uploads and clear the IT privacy gate

The upload service stores files in a restricted landing area.
Uploading does not send file contents to an LLM.
An LLM is the language model used by agents to interpret logic and propose code.

IT uses controlled inspection tools to review source schemas and sensitive fields.
IT creates the required intake table definitions and establishes column classifications in Apache Atlas.
An access policy then controls which information can enter agent prompts and tool responses.

The agents receive approved schemas, sanitized scripts, and synthetic or approved de-identified examples.
Actual business rows remain in the controlled data-processing environment.
Sensitive SQL literals and spreadsheet cells also require inspection.

**Gate output:** an approved input inventory and an explicit list of information the agents may use.
Atlas labels describe sensitivity; the access and masking controls enforce the restriction.

## 2. Let the coordinator manage the workflow

The coordinator acts as a workflow controller.
It assigns work, stores artifact versions, checks prerequisites, and routes failures for revision.
It is separate from the six specialist agents.

Each agent receives a bounded task and produces a reviewable artifact.
An artifact is a saved output, such as a mapping file, script, test report, or approval record.
The coordinator retains these artifacts so later steps use the correct version.

For example, a changed customer mapping triggers conversion and validation again.
The previous approval cannot authorize the changed code.

## 3. Agent 1: Mapper / Interpreter

The Mapper identifies what each input means and where each output belongs.
It resolves source columns, target names, folder paths, and dependencies between transformations.
It asks for clarification when the business rule is ambiguous.

For the sales example, it may identify `customer_id` as the join key.
It also records the expected output columns, their types, and the daily reporting window.
These decisions form the output contract: the structure and meaning that downstream users expect.

**Agent output:** source-to-target mappings, dependency information, and an output contract.

## 4. Agent 2: SQL / Excel Converter

The Converter translates the complete transformation logic into PySpark.
PySpark runs Python-defined data transformations on Apache Spark.
The Converter examines shared work across scripts before deciding job boundaries.

An illustrative consolidation could look like this:

| Original logic | Proposed job |
| --- | --- |
| Five repeated input preparation scripts | `01_prepare_inputs.py` |
| Four repeated lookup and enrichment scripts | `02_enrich_orders.py` |
| Four calculation and aggregation scripts | `03_calculate_reports.py` |
| Two output formatting scripts | `04_publish_outputs.py` |

The mapping preserves traceability from all 15 original scripts to the four proposed jobs.
It also preserves every required output, even if one job produces several files or tables.
Different schedules, permissions, or business meanings can prevent consolidation.

Excel behavior needs particular care around lookups, blank cells, errors, and rounding.
Unsupported macros or external workbook dependencies require clarification before conversion can pass validation.

**Agent output:** PySpark scripts, a job dependency graph, and a consolidation explanation.

## 5. Agent 3: Folder / Table Structure Creator

This agent generates a consistent storage plan and Hive external-table DDL.
DDL means the statements that define a table, including its columns and storage location.
An external table describes data stored at a designated location.

```text
/data/projects/self-service/use-case-1/
├── input/             Uploaded source files
├── scripts/           Approved PySpark scripts
├── ddl/               Table definitions for IT
├── tables/            Data locations used by external tables
├── output/<run-id>/   CSV files for downstream processes
└── reports/<run-id>/  Validation, approval, and execution evidence
```

The agent proposes folder creation and table definitions.
IT retains authority to execute the DDL and control storage permissions.
The runtime can create approved folders using its assigned permissions.

**Agent output:** a folder manifest and an IT-reviewable DDL package.

## 6. Agent 4: Validator

The Validator checks whether the proposed pipeline preserves the required behavior.
A successful syntax check alone does not prove correctness.
The Validator uses deterministic checks and isolated test execution alongside any agent reasoning.

| Check | Example question |
| --- | --- |
| Code and dependencies | Can the generated jobs run with approved libraries? |
| Schema | Do output columns and types match the contract? |
| Business rules | Do filters, joins, and calculations preserve the original meaning? |
| Edge cases | Do nulls, duplicates, decimals, and dates behave correctly? |
| Equivalence | Do old and new transformations produce matching results on approved fixtures? |

Test execution uses sanitized fixtures and cannot write to production destinations.
Failed checks return the relevant artifacts for revision.
Production-scale reconciliation happens later, inside the controlled execution environment.

**Agent output:** a validation report with passed checks, failures, and unresolved questions.

## 7. Agent 5: Documenter, followed by business review

The Documenter assembles a readable report from the actual artifacts and validation results.
It explains what changed, why scripts were consolidated, and what execution will read and write.
It also identifies unresolved issues and the version being presented for approval.

The business reviewer follows this sequence:

1. Review the output contract and proposed changes.
2. Inspect the consolidation mapping and validation results.
3. Return corrections when the interpretation is wrong.
4. Approve the exact execution package when the evidence is acceptable.

Returned feedback starts another mapping, conversion, validation, and documentation cycle as needed.
The pipeline cannot proceed with unresolved blocking issues.

**Gate output:** business sign-off tied to the reviewed artifact version.

## 8. IT creates the output tables

IT reviews and executes the approved output DDL.
IT confirms the output columns' Atlas classifications and the runtime's access permissions.
Business users and agents receive no table-creation privileges.

This gate differs from the intake gate.
The intake gate controls information available to AI before planning begins.
This gate prepares the approved production destinations before processing begins.

**Gate output:** IT readiness for the approved table definitions, locations, classifications, and runtime identity.

## 9. Agent 6: Executor

The Executor checks business approval and IT readiness before starting Spark.
It verifies that the scripts and configuration match the approved artifact version.
It submits the approved jobs; it does not rewrite code during execution.

Spark reads the authorized inputs and applies the approved transformations.
The pipeline writes data to the IT-created external-table locations and produces downstream CSV files.
The DDL defines the tables; the Spark jobs populate their data locations.

```text
Approved scripts + authorized input files
                    |
                 Spark run
                    |
          +---------+---------+
          |                   |
   Hive table data      Downstream CSVs
          |                   |
          +---- Run report ---+
```

Each run records its input identity, code version, approvals, output locations, and status.
The design stages outputs and declares completion only when both delivery paths succeed.
A failed delivery remains visible and requires controlled recovery without duplicate writes.

**Agent output:** populated table data, CSV outputs, execution logs, and a run manifest.

## 10. Reconcile before cutting over

The business team continues its existing process during the parallel-run period.
The new pipeline produces both table data and CSV outputs for the same agreed input window.
CSV delivery preserves existing downstream interfaces while users build confidence.

1. Match legacy CSVs, new CSVs, and Hive table results using agreed business keys.
2. Compare counts, duplicate keys, amounts, and selected field values.
3. Apply business-approved tolerances for rounding or other accepted differences.
4. Investigate discrepancies and revise the pipeline when necessary.
5. Repeat validation and approval for changed executable artifacts.
6. Cut over after the agreed acceptance period and explicit business approval.

The team must agree on the period, tolerances, owners, and rollback procedure before production rollout.
A successful Spark job alone does not establish business acceptance.

## Technical components behind the diagram

| Component | Purpose |
| --- | --- |
| Upload service and restricted storage | Receive files and preserve their versions |
| Workflow coordinator and state database | Track tasks, artifacts, retries, and approvals |
| Agent runtime and approved LLM endpoint | Interpret permitted context and propose transformations |
| Controlled tools and test environment | Inspect files, validate code, and execute isolated tests |
| Hive catalog, Atlas, and access controls | Register tables, classify columns, and enforce permitted access |
| Spark execution service | Run approved jobs against authorized business data |
| Artifact and output storage | Retain scripts, DDL, reports, CSVs, and table data |

These are proposed responsibilities rather than selected products or deployed services.
The Spark platform, storage backend, LLM endpoint, and policy integration still need implementation decisions.

For the detailed responsibilities and open decisions, see the [design notes](README.md).
