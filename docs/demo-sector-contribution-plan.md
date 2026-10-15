# Helios demo contribution guidelines and implementation plan

**Current-status note, 12 October 2026:** this is the original contribution plan.
Shared lexical indexing, bounded retrieval, local builder, and consumer export now exist.
See [foundation status](SEMANTIC_FOUNDATION_STATUS.md) and [alignment review](DOCS_ALIGNMENT.md) for remaining work.

Status: prepared contribution, 10 October 2026.
Baseline: Helios revision `316f5d89926f96d366afaee641bd923af4ca6bf3`, plus the existing local observability extension.
This document separates implemented application code, upstream work and dataset acceptance.

## Source ownership

Helios owns reusable semantic models, compilation, metadata adapters and authorization contracts.
The UOB workspace owns its UI, connectors, deployment settings and customer workflows.
Its deployment bundle contains a hashed copy of `shared/helios_core`, schemas and license assets.
Treat that copy as an immutable build artifact. Never edit it as a second source tree.
Make Helios changes in a feature branch, verify them, then rebuild the deployment snapshot.
Record the upstream revision and individual file hashes because local changes can exist after that revision.

Existing uncommitted Helios work includes the observability package, its tests, its implementation plan and README changes.
Preserve these files before any sync or merge. Do not reset the checkout.
The application currently implements banking lexical retrieval, caller policy and the offline financial adapter.
These modules have not yet become upstream Helios APIs.
Do not copy their FastAPI routes or UOB settings classes into the shared core.

```text
Helios feature branch -> reusable core + generation fixtures -> core/generator checks
                                                                  |
                                                                  v
                                         reviewed snapshot + manifest -> demo package
                                                                  |
                                                                  v
                                         customer UI + connectors -> acceptance evidence
```

## Contribution boundaries

1. Preserve existing TPC-DS models, tiny fixtures, scenario templates and published releases.
2. Add sector fixtures under `apps/helios-ds-generation/fixtures/sectors/v1`.
3. Keep reusable fixture builders in `src/helios_ds/sector_demo`.
4. Keep source downloads in a separate cache with URLs, dates, licenses and SHA256 checksums.
5. Separate serving tables, crawlable documents, semantic drafts and hidden evaluation truth.
6. Mark generated models as drafts. Never generate approval or a READY lifecycle event.
7. Import into the existing lifecycle only through a dedicated, reviewed adapter.
8. Preserve explicit synthetic and real-source distinctions in every manifest.
9. Keep customer names out of generic core APIs. SP Group appears only in the power demo presentation.
10. Add regressions for permissions, retrieval limits, repeatability and source-independent expected answers.

## Milestone 1: portable dataset catalogue

Add four additive packs: finance, manufacturing, pharma and power.
Finance reuses the exact generator from the UOB workspace and retains all six tables.
Compare generated finance records and reference totals with the existing serving artifact.
Keep source finance scenario labels and intentionally invalid rows in evaluation storage.

Manufacturing uses the UCI AI4I dataset as its source contract.
Create synthetic assets, observations and work orders from its temperature, speed, torque and wear fields.
Add project-authored maintenance reports and shift notes tied to real fixture identifiers.
Keep failure labels out of query prompts and telemetry tables when evaluating predictions.
Label narratives as synthetic maintenance documents, never original incident reports.

Pharma uses FDA product data or an explicitly licensed pharmaceutical source after provenance review.
Create synthetic product, batch, laboratory-result and deviation tables for a quality workflow.
Add authored batch-review reports, deviation investigations and release-review notes.
Use fictional product identities for generated quality examples.
Keep numerical limits illustrative; these records cannot support treatment decisions or regulatory batch release.
Patient review datasets are optional research candidates, not the default pharmaceutical quality dataset.

Power uses the UCI Individual Household Electric Power Consumption dataset as a source contract.
Create synthetic Singapore-oriented meters, feeders, substations and half-hour readings.
Differentiate kW, kWh and MWh explicitly. Integrate average power over the actual interval to calculate energy.
Keep missing intervals unknown. Do not fill them as zero consumption.
Mark estimated readings and exclude them from the default measured-energy metric.
These are illustrative utility records, not SP Group operational data or calibrated Singapore demand.
Use general NL-to-SQL benchmarks only as a supplementary compiler evaluation pack.

Each pack needs a manifest, table schemas, row counts, foreign keys, units and time-zone rules.
It also needs source provenance, draft Ossie models and an evaluation question set.
Manufacturing and pharma additionally need document IDs, checksums, structured entity links and source locators.
Golden answers stay outside crawlable documents and query models.

## Milestone 2: integrate the existing generation lifecycle

Extend the generator through a source-adapter interface instead of replacing the TPC-DS planner.
The adapter returns typed source facts, source provenance and deterministic fingerprints.
The existing planner then emits scenarios and artifacts through its current stores and sinks.
Dataset state remains IN_REVIEW until a human approves it through the existing review workflow.
The crawler sees READY artifacts only. It cannot read generation manifests or evaluation truth.

Implement an explicit importer for local sector fixtures.
Map tables into an isolated sector schema and documents into a dedicated object-store prefix.
Support dry-run inventory, schema validation, deterministic fingerprints and duplicate detection.
Never contact or write a live lakehouse while running local fixture checks.
Do not change existing source aliases or published TPC-DS model selections.

## Milestone 3: bounded semantic retrieval

Extract a framework-independent retrieval API from the workspace implementation.
Accept approved model, verified field scope, query terms and explicit context budgets.
Return selected metrics, required fields, permitted join keys and provenance.
Return structured clarification for missing matches, ties, multiple join paths or excessive expansion.
Provide a lexical backend first. Add embedding or Atlas backends through the same contract later.
Do not describe Atlas approximate search as native embedding search without testing that deployment.

Test retrieval on small reviewed models and a generated 2,000-table inventory.
Record recall, no-answer behavior, context size and latency.
Keep metric definitions and business rules attached to the selected tables.
Do not send the complete catalogue to the LLM as the default query context.

## Milestone 4: caller-enforced execution

Reuse Helios identity and physical authorization contracts.
The application authenticates a caller before retrieval and does not trust browser-supplied roles.
The platform adapter proves the effective database identity before execution.
Verify table, row and column restrictions against the installed Cloudera authorization path.
Apply equivalent controls to discovery, preview and reference validation.
Deny execution when enforcement cannot be verified. Never use a privileged shared account as fallback.
Keep the offline DuckDB adapter explicitly separate from live execution.

## Milestone 5: scoped conversation and analysis

Store approved release hash, source scope, caller policy revision and selected evidence with each conversation.
Revalidate these values on every turn. Invalidate stale context instead of silently mixing releases.
Use shared approved definitions across sessions while keeping each conversation's evidence separate.
Do not create a global accumulation of raw user prompts or retrieved data.

Add analysis only after retrieval and permission acceptance.
Start with deterministic statistics and source-derived charts.
A later Python sandbox must restrict imports, network access, files, time and memory.
Persist results only through explicit user action and an approved output contract.
Prediction claims require a held-out evaluation pack and declared uncertainty.

## Pull request sequence and acceptance

1. Add the finance parity pack and sector fixture contract.
2. Add source provenance, fetch/transform commands and repeatability checks.
3. Add manufacturing and pharma document/record consistency checks.
4. Add the power model, unit checks and SP Group example questions.
5. Add the generation lifecycle importer after local fixture acceptance.
6. Extract bounded retrieval with compatibility tests for current Helios callers.
7. Integrate verified Cloudera authorization and source-specific acceptance checks.
8. Add scoped conversations, then controlled analysis.

Keep each pull request independently reviewable. Include precise behavior, tests and remaining limitations.
Run Helios core tests and affected generator tests before rebuilding this project's snapshot.
Do not commit, push, publish datasets, deploy services or merge changes unless requested.

## SP Group prototype presentation

Replace banking tables and metrics in every static page with utility data definitions.
Use a meter-to-feeder-to-substation hierarchy and measured-energy metrics.
Sources shows schemas and unit meanings. Context shows reviewed models and exclusions.
NiFi shows meter-reading ingestion. Observability shows ingestion errors and native resource metrics.
Data understanding shows measured energy, day/region comparisons and compiled semantic SQL.
Keep source evidence, definition versions, review status and explicit sample labels visible.
The later narrative should explain this same sequence and distinguish prototype behavior from proposed production delivery.
