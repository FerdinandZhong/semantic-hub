# Pharmaceutical Industry Intelligence & New Drug Analysis

For a presentation script and click-by-click sequence, use the [pharmaceutical demo story](pharma-intelligence-demo-story.md).

Implemented locally on 13 October 2026 as `pharma_intelligence`.
The Hub now contains five source models.
This model is separate from `pharma`, which demonstrates synthetic batch quality.
The new model contains curated public facts, not synthetic patients or fictional clinical results.
It starts as an unreviewed model. Existing user releases remain unchanged.

## Dataset and scope

| Table | Rows | Scope |
| --- | ---: | --- |
| `source_documents` | 4 | URLs, source checksums, publication details, and extraction notes |
| `drugs` | 46 | FDA CDER's 2025 novel approval list |
| `approval_events` | 46 | Original approval dates and source indications |
| `trials` | 1 | Beamion LUNG-1, NCT04886804, supporting HERNEXEOS approval |
| `trial_cohorts` | 2 | The original 105-patient efficacy population, split by prior HER2-directed ADC treatment |
| `trial_results` | 4 | Response rates and response duration, with separate denominators |
| `trial_demographics` | 11 | Source demographic categories; dimensions overlap |
| `industry_observations` | 5 | Geographic shares of new-medicine sales from the EFPIA chart |

The model has 119 records, 67 fields, 12 directed relationships, six metrics, and five glossary concepts.
Four curated source briefs explain the source scope and interpretation limits.
The builder does not ingest evaluation answers as model evidence.

Sources:

- [FDA 2025 novel approvals](https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025).
- [FDA HERNEXEOS trial snapshot](https://www.fda.gov/drugs/drug-trials-snapshots/drug-trials-snapshots-hernexeos).
- [FDA demographic figure](https://www.fda.gov/files/Picture1_90.png).
- [EFPIA industry figures 2026](https://www.efpia.eu/media/owqczcqz/the-pharmaceutical-industry-in-figures-2026.pdf).

The approval list uses deterministic HTML table extraction.
Trial facts and chart values were explicitly curated and checked against their sources.
The dataset construction does not claim automated OCR or chart understanding.
Raw downloaded assets remain outside the repository.
Their URLs and checksums remain in the source facts and pack manifest.

## What the documents add

The clinical results demonstrate why numbers alone are insufficient.
The no-prior-ADC cohort has 71 patients and a 75% objective response rate.
Its 58% durable-response result uses 53 responders as its denominator, not all 71 patients.
The document supplies the endpoint meaning, population, exclusions, and denominator.
These facts support field definitions, metric descriptions, and explicit filters.

The industry example has a similar distinction.
The 74.1% figure describes US sales of medicines launched during 2020–2024.
It is not the US share of the entire pharmaceutical market.
The report year does not replace the observation period.

A visual check of original EFPIA PDF page 4 corrected two previously reversed geography values.
Pharmerging is 2.9%; Rest of the World is 3.8%.
The chart reports latest sales in 2025 for medicines launched during 2020–2024.
The related prose uses the same launch period.
The nearby 2020–2025 market-growth paragraph describes a different indicator.
This correction removes the earlier unsupported period-conflict warning.

Upload is useful when these definitions arrive in a new report, policy, trial update, or internal document.
The library retains the original file and lets several models reuse separately reviewed evidence.
A new upload does not silently replace published definitions.

```text
Document -> cited AI claims -> proposed model links -> human review
                                                        |
                                                        v
Published version <- validation + review <- AI draft <- attached evidence
```

## Use the unified workflow

1. Open the pharmaceutical intelligence card in Semantic Hub.
2. Select **Open Studio**, then open its documents section.
3. Select **Add supporting material** to open the shared library for this source.
4. Upload PDF, DOCX, Markdown, text, PNG, or JPEG content.
5. Select **Analyze content**, then inspect claims and source quotations.
6. Select **Find model links** and review each proposed target.
7. Approve relevant links and add their evidence to the selected model draft.
8. Select **Open Studio to draft with AI**.
9. Select **Draft semantic definitions with AI**, then inspect and explicitly apply the candidate.
10. Validate SQL and relationships, review objects, and create a version.

The canvas shows supporting-evidence edges to linked objects.
These edges represent reviewed support, not SQL joins or observed causal relationships.
AI drafting can use attached evidence with the structured schema.
The [visual workflow](visual-document-facts.md) separately creates typed fact sources from explicitly reviewed observation rows.
Select one to six physical pages from PDFs containing at most 32 pages.
GPT-4o proposes observations from images and scanned pages; reviewers correct and approve the retained rows.
The new source starts with a semantic draft and still requires Studio validation and publication.
OpenAI text embeddings use local Lance storage for model-link matching.
The current bounded compiler still requires supported structured fields and expressions.

## Validation references

These queries reconcile the six starter metrics.
Copy each query into its corresponding verification field before validation.

```sql
-- Expected: 46
SELECT COUNT(*) AS novel_approval_count FROM approval_events;

-- Expected: 105, the original efficacy population; not total trial enrollment
SELECT SUM(patient_count) AS evidence_patient_count FROM trial_cohorts;

-- Expected: 75 percent
SELECT value AS no_prior_adc_orr_percent
FROM trial_results WHERE result_id = 'beamion_no_prior_adc_orr';

-- Expected: 44 percent
SELECT value AS prior_adc_orr_percent
FROM trial_results WHERE result_id = 'beamion_prior_adc_orr';

-- Expected: 58 percent of 53 responders
SELECT value AS no_prior_adc_durable_response_percent
FROM trial_results WHERE result_id = 'beamion_no_prior_adc_dor_ge_6_months';

-- Expected: 74.1 percent, new-medicine sales for the chart's specified period
SELECT value AS us_new_medicine_sales_share_percent
FROM industry_observations WHERE geography = 'USA';
```

## Source issues retained for review

- FDA's Nereus indication text ends at “motion”. The source text remains visibly incomplete.
- The Exdensur indication contains an apparent “Komzifti” copy error. It remains flagged rather than silently corrected.
- The trial snapshot has inconsistent summary wording about randomization. The detailed trial section describes a single-arm study.
- Ethnicity missingness differs between the table and figure text. The curated table values retain this warning.
- EFPIA new-medicine-sales chart and related prose both use the 2020–2024 launch period. Nearby 2020–2025 market-growth figures describe another indicator.
- Demographic dimensions describe the same patients. Summing across dimensions would count patients repeatedly.

## Reproduce and verify

```sh
PYTHONPATH=apps/helios-ds-generation/src python -m helios_ds.sector_demo.pharma_intelligence \
  --facts apps/helios-ds-generation/fixtures/source_facts/pharma_intelligence.json \
  --output apps/helios-ds-generation/fixtures/sectors/v1

PYTHONPATH=shared:apps/helios-ds-generation/src python -m pytest \
  apps/helios/tests/test_pharma_intelligence.py \
  apps/helios/tests/test_material_citations.py \
  apps/helios/tests/test_material_matching.py -q
```

The generator rebuilds only the pharmaceutical intelligence pack and prints its registry entry.
If source facts change, update the registry hashes before launching the pack.
The original four source fingerprints remain unchanged.

An isolated GPT-4o check analyzed the curated trial brief and verified six exact-cited claims.
Matching linked the evidence to `trial_results.denominator_count` and `trial_cohorts`.
Both links appeared in the resolved canvas evidence.
AI drafting then generated six candidate metrics and included the attached evidence.
This test did not apply the proposal, publish a version, or modify user state.

A second isolated check uploaded the original 28-page EFPIA PDF.
GPT-4o produced 53 claims across 30 extracted sections, with every quotation verified against the source text.
Matching proposed 45 pharmaceutical-model links.
Four test-selected links resolved into draft evidence for the industry table, indicator field, and sales-share metric.
These relevance suggestions still require human interpretation review; the test does not certify every claim or candidate link.
The combined regression run passed 123 tests.
See the [increment verification record](pharma-intelligence-verification.json).

The visual increment now supports scanned pages and standalone PNG/JPEG uploads.
The final regression passed 207 tests, including the corrected pharmaceutical pack.
Live OpenAI checks passed for the FDA image, its image-only PDF, and EFPIA page 4. Desktop/mobile workflow checks also passed.
See the [visual verification record](visual-document-verification.json).
Text extraction does not prove accurate interpretation of PDF charts or complex tables.
Scoped document answers and combined SQL/document answers remain M3B work.
