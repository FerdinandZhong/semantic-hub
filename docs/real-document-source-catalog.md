# Real visual documents for Semantic Hub

Update, 14 October 2026: the [expanded finance collection](finance-real-document-sources.md) now contains six locally downloaded official PDFs and current import checks.
The importer results below remain the historical 13 October snapshot.

Checked on 13 October 2026. Six sources were downloaded and representative visuals were inspected.
Three sources support pharmaceutical industry intelligence and new drug analysis.
The collection contains mixed text/visual PDFs and one original chart PNG, not six scanned documents.

Original files and page previews are in `/tmp/helios-real-documents-20261013/`.
This temporary directory can be cleared by the operating system.
[The source manifest](real-document-sources.json) retains URLs, checksums, file sizes, page counts, and parser results.
Original publisher files are outside the repository and the application fixtures.
No documents were uploaded, approved, attached to models, or published during this discovery task.

## Downloaded and inspected sources

Page references below use one-based PDF page positions, which can differ from printed page numbers.

| Sector | Official source | Visual evidence inspected | Suggested semantic use |
| --- | --- | --- | --- |
| Pharma: industry intelligence | [EFPIA, The Pharmaceutical Industry in Figures 2026](https://www.efpia.eu/media/owqczcqz/the-pharmaceutical-industry-in-figures-2026.pdf) | 28-page report; page 4 contains a geographical market map with percentage markers | Industry, geography, reporting period, market share, R&D investment, units, and source attribution |
| Pharma: new drug analysis | [FDA, New Drug Therapy Approvals 2025](https://www.fda.gov/media/190705/download?attachment=) | 36-page report; page 34 contains a colour-coded drug designation matrix | Drug, active ingredient, indication, regulator, approval year, and regulatory designation |
| Pharma: trial evidence | [FDA, HERNEXEOS Drug Trials Snapshot](https://www.fda.gov/drugs/drug-trials-snapshots/drug-trials-snapshots-hernexeos) and [original Figure 1 PNG](https://www.fda.gov/files/Picture1_90.png) | Actual raster pie chart with sex categories, patient counts, percentages, and a legend | Drug, trial population, demographic subgroup, count, percentage, and evidence figure |
| Finance | [BIS CPMI Brief 10, Moving on up, December 2025](https://www.bis.org/publications/cpmi-brief-10-moving-results-2024-cross-border-payments-monitoring-survey.pdf) | 26-page report on the 2024 survey; page 5 contains grouped and stacked payment-system charts | Payment-system type, currency arrangement, survey year, jurisdiction, and settlement terminology |
| Manufacturing | [US DOE, Operations & Maintenance Best Practices, Release 3.0](https://www.energy.gov/sites/default/files/2020/04/f74/omguide_complete_w-eo-disclaimer.pdf) | 321-page reference guide from August 2010; page 64 contains infrared and equipment photographs | Equipment, maintenance method, inspection finding, thermal symptom, and supporting explanation |
| Power | [SP Group Sustainability Report FY2025/2026](https://www.spgroup.com.sg/dam/spgroup/pdf/about-us/our-sustainability-commitment/sp-group-sustainability-report-fy2025-26) | 79-page report; page 54 contains a grid-reliability time series and comparison range | Utility, network, financial year, reliability measure, unit, and reporting scope |

These mappings are design recommendations, not extracted or approved model links.
Public availability does not establish a common redistribution licence.
Keep publisher attribution and source-specific reuse terms with any downstream evidence package.

## Current importer compatibility

The check called the current `parse_document` implementation directly on each original file.
It did not call an LLM or test claim accuracy.

| File | Size | Result |
| --- | --- | --- |
| `efpia-industry-figures-2026.pdf` | 4.19 MiB | Text extraction passed: 30 chunks. Chart meaning remains unverified. |
| `fda-new-drug-approvals-2025.pdf` | 4.25 MiB | Parser rejects the PDF encryption flag, although ordinary viewing works. |
| `fda-hernexeos-trial-demographics-sex.png` | 0.03 MiB | PNG upload is unsupported. |
| `bis-cross-border-payments-2024-survey.pdf` | 1.46 MiB | Parser rejects an image-bearing page without extracted text. This does not establish that the whole report is scanned. |
| `doe-operations-maintenance-guide-2010.pdf` | 8.17 MiB | Exceeds the 5 MiB upload limit. |
| `spgroup-sustainability-2025-26.pdf` | 5.85 MiB | Exceeds the 5 MiB upload limit. |

Only EFPIA passed the current text importer unchanged.
Text extraction cannot preserve every relationship encoded by a chart's colours, axes, or spatial layout.
The FDA designation matrix makes this limitation visible: coloured cells carry information beyond the extracted words.
Large reports need bounded page selection or a revised ingestion design with explicit limits.
Any page extract must retain its original document checksum and source-page mapping.

## Recommended pharma model

The existing pharma fixture models synthetic batch quality, assays, and deviations.
It does not currently model pharmaceutical markets, clinical trials, or drug development pipelines.
Create a separate **Pharmaceutical Industry Intelligence & New Drug Analysis** model when implementing this use case.
Retain the existing quality model and link evidence only where entities and scope match.

```text
Industry report --> Market observation --> Geography + reporting period
Approval report --> Drug --> Indication
                      |         |
                      +--> Approval event --> Regulator
                      |
                      +--> Trial --> Population + endpoint + result
                                     |
                                     +--> Source page / figure / table
```

Candidate questions for this collection:

- Which drugs have a specified regulatory designation in the FDA report?
- Which regions appear in EFPIA's new-medicine sales distribution, and which years does the chart cover?
- Which population does a drug-trial demographic chart describe?
- Which supporting source establishes each extracted fact?

The selected sources do not provide a complete competitive pipeline database.
Sponsor presentations and trial-registry records would be additional inputs for pipeline and trial-outcome analysis.
Approval counts, recommendation counts, clinical results, and market observations require distinct definitions.
External real documents cannot validate fictional batches, transactions, maintenance events, or meter readings.

## Proposed visual-document increment

This is follow-up scope, not an implemented capability.

1. Preserve original files, source URLs, checksums, publication dates, and reporting periods.
2. Extract text and tables; render selected pages for chart and image interpretation.
3. Use OCR for image text and a vision-capable model for charts, legends, and layout.
4. Store extracted claims with page coordinates, units, qualifiers, and the original visual.
5. Match claims to model entities using metadata, ontology terms, keywords, and optional embeddings.
6. Require human review before applying evidence to a model draft.
7. Publish evidence only through the existing version review process.

```text
Original document
  -> Text / table / visual extraction
  -> Cited claims
  -> Model matching
  -> Human review
  -> Versioned supporting evidence
```

Embeddings improve matching after extraction; they do not replace OCR or chart interpretation.
Model configuration should distinguish document understanding from embedding generation.
Keep the original visual available beside each proposed fact during review.

## Additional candidates and retrieval issues

- [EMA, Human medicines in 2025](https://www.ema.europa.eu/en/documents/report/human-medicines-2025_en.pdf): official PDF found through search; download returned HTTP 429. Not visually inspected locally.
- [MAS Annual Report 2024/25 infographic](https://www.mas.gov.sg/publications/annual-report/2025/annual-report-2024-2025): official infographic link found. The local response contained a service-unavailable page, so it was excluded.
- EFPIA's indexed 2025 PDF returned HTTP 404. The verified 2026 edition replaces it in this collection.

Related implementation: [Supporting materials](supporting-materials.md).
Dataset boundaries: [Sector demo datasets](sector-demo-datasets.md).
