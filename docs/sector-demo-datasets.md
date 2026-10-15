# Sector demo datasets

These additive fixtures extend the existing TPC-DS and tiny fixture collection.
They do not replace published models or modify the generation lifecycle.
All models are drafts. All packs remain `IN_REVIEW`.

## Fixture layout

```text
fixtures/sectors/v1/
  catalog.json
  finance/          serving/ + evaluation/ + manifest.json
  manufacturing/    serving/ + evaluation/ + manifest.json
  pharma/           serving/ + evaluation/ + manifest.json
  power/            serving/ + evaluation/ + manifest.json
  pharma_intelligence/ serving/ + evaluation/ + manifest.json
```

Serving contains CSV tables, draft Ossie models, metadata and linked documents.
Evaluation contains reference SQL, expected answers and hidden labels.
Only serving content can enter a future crawler. Do not crawl whole pack directories.
The existing lifecycle importer remains planned in [the contribution plan](demo-sector-contribution-plan.md).

## Build and verify

Run from the Helios repository root:

```sh
PYTHONPATH=apps/helios-ds-generation/src python -m helios_ds.sector_demo \
  --output apps/helios-ds-generation/fixtures/sectors/v1

PYTHONPATH=apps/helios-ds-generation/src:shared python -m pytest \
  apps/helios-ds-generation/tests/test_sector_demo.py -q
```

Generation uses only Python's standard library.
Acceptance checks also require Helios dependencies, pytest and DuckDB.
Use `--seed` for deterministic alternate fixtures and `--sector` to select one pack.

## Public sources and provenance

The original four checked-in packs are source-informed synthetic fixtures.
They contain no downloaded public records.
The fifth pack, [pharmaceutical intelligence](pharma-intelligence.md), contains curated FDA and EFPIA public facts.
It has its own builder, provenance, source warnings, and six validation references.
Generate a distinct source-derived pack when network access is available:

```sh
python apps/helios-ds-generation/workbench/fetch_sector_sources.py \
  --output /tmp/helios-sector-source-cache

PYTHONPATH=apps/helios-ds-generation/src python -m helios_ds.sector_demo \
  --source-cache /tmp/helios-sector-source-cache \
  --output /tmp/helios-source-derived-sectors
```

Downloads retain source URLs, retrieval timestamps and SHA256 checksums in cache sidecars.
Pack manifests record input checksums, source record counts, transformation mode and limitations.
Import failures raise errors. They do not silently switch to independent synthetic generation.
Use a fresh output directory when changing source mode.
Keep raw cache files outside version control and serving directories.

Manufacturing uses [UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), DOI `10.24432/C5HS5C`, CC BY 4.0.
AI4I is itself synthetic. Sensor values map to fictional assets and timestamps.
Failure labels stay in evaluation. Maintenance documents are authored synthetic artifacts.

Pharma uses [openFDA NDC](https://open.fda.gov/apis/drug/ndc/) and the [openFDA license](https://open.fda.gov/license/).
CC0 terms apply subject to the published exceptions.
Public product facts remain separate from fictional batches, assays and deviations.
NDC listing does not establish FDA approval.
Draft reports cannot authorize product release or support treatment decisions.

Power uses [UCI household electric power consumption](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption), DOI `10.24432/C58K54`, CC BY 4.0.
The source describes one household in France. It does not describe SP Group.
Imported one-minute power samples shape fictional half-hour profiles.
They are not measured half-hour aggregates of the source household.
The reader uses at most 10,000 source records. Seasonal calibration remains pending.
Default totals exclude missing and estimated readings. Missing energy stays null.
Energy equals interval average power in kW multiplied by 0.5 hours, giving kWh.
UTC interval timestamps map to reporting dates in Asia/Singapore.

Finance is independently synthetic. Its tables match the UOB workspace generator at seed 8100.
It contains fixed illustrative FX rates and no customer records.

## Acceptance and remaining work

Seven offline tests passed against the Helios compiler on 10 October 2026.
They check checksums, deterministic generation, foreign keys, document links, unit conversion and compiled SQL reference results.
Finance references reconcile to SGD 686,572.96.
Power references reconcile to 8,547.2820 kWh across 3,960 eligible readings.

The pharmaceutical intelligence pack has verified public-source inputs and offline acceptance checks.
The original four public-source transformation modes still need separate acceptance.
Lifecycle import, governed lakehouse loading, document crawling and published semantic releases remain pending.
Production calibration, predictive accuracy and SP Group operational acceptance are not established.
