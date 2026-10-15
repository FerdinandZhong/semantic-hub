# Financial data and metadata foundation

Implemented starter increment: 8 October 2026.
Helios dependency: sibling checkout at `316f5d89926f96d366afaee641bd923af4ca6bf3` plus the existing local observability extension.
The current branch was fast-forwarded from `83ac412` to `origin/main`.
The local README modification and untracked observability files were preserved.
No merge commit, push or deployment occurred.

## What this increment provides

- Normalized table metadata in existing source-discovery responses.
- An optional, read-only Atlas entity enrichment adapter with explicit source mapping.
- An independent deterministic financial fixture generator.
- A draft Ossie payment model produced through the demo's existing model-authoring function.
- Separated evaluation labels, deliberate quality failures, reference totals and artifact checksums.

This increment does not implement permission-filtered retrieval or verified caller delegation.
It does not replace the current four-row offline preview or activate a new semantic release.
The generated pack requires a subsequent local loader or explicitly approved lakehouse ingestion workflow.

## Dataset research and decision

| Candidate | What it provides | Decision |
| --- | --- | --- |
| [IBM AML-Data / AMLworld](https://github.com/IBM/AML-Data/blob/main/README.md) | Already synthetic transfers with laundering labels; generated from a virtual population. | Preferred external reference for later realism and detection evaluation. |
| [IBM AMLSim](https://github.com/IBM/AMLSim) | A configurable simulator with transaction graph patterns. | Useful pattern reference; its documented Java/Python dependencies would add substantial setup to this demo. |
| Independent project fixtures | Controlled identifiers, relational contracts, evaluation truth and reproducible generation. | Implemented for immediate metadata and Helios integration testing. |

IBM distinguishes the repository's Apache-2.0 license from the actual AML-Data dataset's CDLA-Sharing-1.0 license.
This increment does not download, transform or redistribute IBM records.
The fixture is independently generated from project-authored rules.
Do not describe it as an IBM subset, an anonymized bank dataset or a calibrated AML benchmark.

The [IBM research publication](https://research.ibm.com/publications/realistic-synthetic-financial-transactions-for-anti-money-laundering-models)
supports using explicit synthetic ground truth for evaluation.
It does not validate this project's generator or its realism.

## Fixture contract

The default pack includes:

| Table | Default rows | Meaning |
| --- | ---: | --- |
| customers | 200 | Clearly named synthetic parties across SG, HK and GB. |
| accounts | 200 | One account per party with a declared currency. |
| fx_rates | 3 | Fixed illustrative SGD conversion rates. |
| transactions | 5,011 | Background transfers plus 11 injected graph-pattern events. |
| ledger_postings | 9,700 | Two balanced SGD-normalized postings per settled transfer. |
| payments | 4,850 | Curated settled sender outflows for the first Ossie metric. |

These counts apply to seed 8100 and the default generator arguments.
Other seeds change rejection rates and curated row counts.
The postings are a simplified normalized transfer ledger, not a complete accounting simulator.
The data has no real names, account numbers or customer records.
Fixed FX rates are not historical market observations.

The pack declares grain, units, currency conversion, UTC booking dates, inclusion rules and relationship direction.
It distinguishes sender jurisdiction from receiver jurisdiction.
It excludes rejected transfers from the settled-payment metric.
It keeps cycle, fan-in and fan-out scenario labels outside operational tables and metadata.
Those motifs do not prove financial crime.

`evaluation/ground_truth.json` contains injected event identities and intentionally invalid records.
The invalid records cover duplicates, orphan account references, missing currency and negative amounts.
They must remain outside clean business tables unless testing a separately labeled quality workflow.
`evaluation/reference_queries.json` contains expected whole-pack payment totals and counts.
Tests independently reconcile raw transfer/FX SQL with the curated payment total.

`payments.ossie.draft.json` is a draft for `iceberg.synthetic_finance.payments`.
It is not pinned, approved, published or activated by generation.
The current Helios compiler validates and compiles its total-settled-outflow metric in tests.

## How metadata enters the demo

```text
Trino source discovery ─── technical names and types ─┐
                                                    |
Optional Atlas entity ─── terms and classifications ─┤
                                                    v
Independent fixture ─── explicit sample metadata → normalized inventory
                                                    |
                                      review meanings and relationships
                                                    |
                                      approved Ossie release → retrieval
```

The existing Trino discovery path reads bounded catalog/schema/table and column information.
The additive `metadata` response uses discovered columns without extra source calls.
The adapter attributes names/types to Trino or to explicit offline sample data.
Trino schema discovery does not establish business meanings, join cardinality or access grants.
Reviewed domain definitions supply those meanings.

Next, build a release-versioned retrieval index from authorized normalized metadata and approved Ossie definitions.
Include required metric expressions and join dependencies in each selected bundle.
Do not feed the complete 2,000-table catalog to the planner.
Keep financial row-volume tests separate from the 2,000-table metadata-scale benchmark.
Neither large-catalog retrieval nor population calibration is implemented by this fixture generator.

## Atlas integration decision

Atlas suits the platform-connected governance story.
It should remain optional for a standalone local demonstration.
Use schema discovery and reviewed definitions when Atlas is absent.
Do not present synthetic lineage as an Atlas response.

[Apache Atlas REST APIs](https://atlas.apache.org/api/v2/ui/index.html) expose entities, glossary, discovery and lineage.
[Cloudera documents Iceberg support](https://docs.cloudera.com/runtime/7.3.2/atlas-iceberg/topics/iceberg-for-atlas.html).
However, [lineage depends on collected process metadata](https://docs.cloudera.com/runtime/7.3.2/atlas-exploring-using-lineage/topics/atlas-lineage-lifecycle.html).
Do not assume every Trino query automatically produces Atlas lineage.
Confirm the deployed engine hooks, entity types and platform version during live acceptance.

The implemented adapter accepts an existing Helios AtlasClient and reads one explicitly mapped entity.
It verifies the GUID, qualified name and ACTIVE status.
It copies only selected descriptions, classifications and glossary labels.
It rejects malformed, deleted or mismatched entities and performs no Atlas writes.
No live Atlas call or new connection-settings UI was added.

The next live integration needs server-side credentials, verified metadata authorization and explicit asset mappings.
Map catalog/schema/table identities to Atlas GUIDs and cluster-qualified names.
Do not join assets by table name alone.
Record capture time, provenance and partial/missing enrichment.
Add bounded lineage reads through the sibling client only after the mapping is verified.
An unavailable Atlas service must display unavailable enrichment; it must not fabricate catalog facts.

Atlas tags are not proof that the query engine enforced access.
Retain a separate verified caller and database authorization boundary.
Do not deploy Atlas locally merely to run the current fixture pack.

## Quality gates before customer presentation

1. Pass referential integrity, monetary consistency and source-reference tests.
2. Add a local read-only loader and labeled preview of this pack.
3. Review and validate the draft through the existing publication workflow.
4. Implement caller authorization before demonstrating multiple permission scopes.
5. Add permission-filtered retrieval and the separate 2,000-table benchmark.
6. Measure calibration, temporal behavior and scenario coverage before claiming realistic financial distributions.
7. Verify real Atlas enrichment and source lineage only on a configured platform.

The current pack is an integration fixture with tested invariants.
It is not yet a statistically calibrated customer dataset or a production security demonstration.
