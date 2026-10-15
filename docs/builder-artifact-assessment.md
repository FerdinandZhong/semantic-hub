# Builder artifact reasonableness assessment

Assessment date: 2026-10-12, Asia/Singapore.

The unified builder passes local acceptance across all four datasets. Its generated artifacts are useful review drafts, with explicit remaining business questions.

This assessment inspected serving CSV files, semantic definitions, source documents, and live OpenAI `gpt-4o` proposals.
Generation did not read evaluation data, change source fixtures, or approve releases.
Final live evidence is in `/tmp/helios-builder-acceptance`.
The checked-in [validation summary](builder-validation.json) records results, metric definitions, document coverage, and warnings.

**Final live results**

| Pack | Executable metrics | Preserved source result | Assessment |
|---|---:|---|---|
| Finance | 5 | Settled sender outflow: SGD 686,572.96 | Source metric retained. The raw transaction total mixes currencies and carries a warning. Other new totals need scope and unit review. |
| Manufacturing | 6 | Planned maintenance: 312 minutes | Source name and planned-maintenance qualifier retained. Temperature, speed, torque, and tool-wear proposals use averages. Sampling and reporting periods still need confirmation. |
| Pharma | 1 | Mean draft assay: 98.275% | Draft-result wording remains explicit. No product-release decision is inferred. |
| Power | 1 | Measured imports: 8,547.282 kWh | The expression preserves VALID and non-estimated conditions. Reporting dates retain Asia/Singapore context. |

All thirteen proposed metrics compiled and executed against their typed serving snapshots.
Each pack also included one linked synthetic uploaded note.
Proposal generation left every saved draft unchanged and supplied no independent reference SQL.
The adapter preserves declared names, IDs, descriptions, and business rules when an LLM returns an identical source formula.
Changed formulas retain the declared metric as a separate candidate.
Raw LLM output remains available for inspection.

Finance's raw currency total should not be approved without a verified currency rule.
The net ledger total equals zero in this fixture; it does not measure payment volume.
Unspecified units and empty metadata fields remain visible for correction.
The builder does not certify arbitrary new LLM metrics merely because their SQL executes.

**Source inventory**

| Pack | Tables | Source rows | Fields | Source documents | Verified document anchors | Proposed mapped entities |
|---|---:|---:|---:|---:|---:|---|
| Finance | 6 | 19,964 | 26 | 0 | 0 | customers, transactions, ledger_postings, payments |
| Manufacturing | 3 | 264 | 15 | 12 | 12 | assets, sensor_readings |
| Pharma | 4 | 62 | 17 | 30 | 30 | products, batches |
| Power | 4 | 4,050 | 17 | 0 | 0 | substations, meters, meter_readings |

The entity column reports the generated `SourceMapping`, not a certified domain ontology. All table classes remain structural proposals. Document anchors require exactly one matching unique source column. Document assertions remain separate from source facts.

**Initial GPT outcomes and concrete mismatches**

| Pack | Initial outcome | Findings |
|---|---|---|
| Finance | Executable proposals; artifact available | `SUM(transactions.amount)` mixes currencies. The unit remains unspecified. `SUM(transactions.amount_sgd)` includes transaction statuses outside the settled-payment source scope. `SUM(ledger_postings.amount_sgd)` combines signed debits and credits; it is not payment volume. The source payment metric describes settled sender outflow using fixed synthetic FX. |
| Manufacturing | Executable proposals; artifact available | Summed temperatures, rotational speeds, torque readings, and tool-wear readings lack a stated business purpose. Averages have a clearer interpretation, subject to sampling assumptions. The source downtime metric measures planned maintenance minutes. Renaming it to total downtime must preserve that distinction. The maintenance notes assert no real failure. |
| Pharma | Initial proposal failed; no initial artifact | The initial assessment reports no usable metric candidates after four calls. Source `AVG(lab_results.assay_percent)` describes draft assay results. It does not authorize product release or clinical decisions. A repaired CASE expression still requires direct inspection and validation. |
| Power | Executable proposal; artifact available | `SUM(meter_readings.import_kwh)` omits the source metric's `VALID` and non-estimated conditions. The proposal assumes valid readings without enforcing those conditions. Missing values also require explicit treatment. The source metric uses Asia/Singapore reporting dates. |

The initial finance, manufacturing, and power artifacts carry empty independent reference SQL. Compilation and execution therefore demonstrate operability, not independent result reconciliation.

**Metadata and ontology assessment**

Field roles preserve explicit draft roles and declared HELIOS source extensions.
LLM-derived drafts use `draft_with_llm_provenance`, which permits later human edits without mislabeling all content as human-authored.
Structural role proposals record their provenance. Dataset meanings and glossary terms flow into the artifact bundle.

The graph uses existing ontology node labels and edge types. Dataset `MAPS_TO` edges describe proposed structural classes. Metric `MAPS_TO` edges describe glossary terms and explicit concept references. Glossary terms map to verified source attributes. Join `RANGE` edges preserve source fields, target fields, cardinality, and draft meaning. These edges do not establish a domain-specific predicate.

Identifier warnings remain conservative. Finance `accounts`, manufacturing `work_orders`, power `feeders`, and pharma `lab_results` and `deviations` each contain multiple unique ID columns. A foreign key happens to be unique in these small fixtures. The generator therefore avoids selecting one inferred primary identifier. Finance `fx_rates.currency` is unique but does not use an ID suffix. Explicit key links remain available after validation.

Ontology concept strings such as `sensor_readings.air_temperature_k` name source fields. Their presence alone does not establish a reviewed business concept. Reviewers must assess the term definition and its relationship to the metric.

**Document assessment**

Manufacturing contains twelve synthetic work-order maintenance notes. The first note links `SYN-WO000` to a verified work-order key. Its body references asset `SYN-M000` and requests inspection. The exported anchor does not automatically resolve every body reference.

Pharma contains twenty-four batch-review notes and six deviation notes. Batch notes reference fictional products and draft laboratory results. The exported anchors preserve their declared batch or deviation targets. Additional body references remain document text unless an explicit verified link exists.

Finance and power contain no serving documents. Their artifacts correctly retain an empty document manifest and a coverage warning. Uploaded text can extend coverage, but it remains an operator assertion.

Attachments bind content bytes, SHA-256, snapshot hash, filename, and verified entity links. Version artifacts include resolved content and citation references. A content change requires a new attachment reference and a new context review. Artifact generation rejects changed bytes behind an existing reference.

Source citations use `document:<id>`; uploaded citations use `attachment:<id>`.
The final audit confirmed that every generated document reference resolves to an exported document.
All graph edges also resolve to exported nodes.
Artifact provenance, citation, and glossary-link corrections were regenerated from the unchanged live proposals, without another LLM call.
The semantic layer remained identical during this regeneration.

The prompt includes at most five documents, each limited to 1,500 characters.
Recent uploads receive slots before remaining source notes.
Final prompt coverage was finance 1/1, manufacturing 5/13, pharma 5/31, and power 1/1 documents.
Full artifact bundles retained all 42 source documents and four uploaded notes.
Coverage warnings expose omitted documents; the builder does not claim that GPT read every note.

**Completed verification**

- 106 builder, runtime, artifact, and retrieval tests passed.
- 24 compiler, MCP bundle, and conversation-budget regression tests passed.
- Eight desktop/mobile lifecycle cases passed across all four packs.
- Eight additional browser cases passed for proposals, rich metadata, uploads, and artifact inspection.
- Live GPT-4o generation passed across all four packs, including uploaded evidence.

Lifecycle tests covered validation failures, independent reconciliation, batch review, immutable approval, publication, activation, and query results.
All automated approvals used temporary test workspaces.
Release tests confirmed that exports return frozen artifacts without regenerating them.
The local review workspace contains no automatic business approval.

The remaining foundation work concerns warehouse acceptance, authenticated enterprise review, and consumer adapters.
UOB and Semantic Guardrails still need to adopt the exported package.
