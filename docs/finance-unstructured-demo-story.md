# Synthetic finance: documents, structured facts, and published answers

Prepared 14 October 2026. [中文版](finance-unstructured-demo-story.zh-CN.md).

For official bank and industry PDFs, see the [real finance document collection](finance-real-document-sources.md).
It includes page-level mapping guidance and remains separate from the synthetic evidence pack below.

The supporting pack describes the existing synthetic finance dataset. It contains no real customer documents or external financial records.
The synthetic PDF and chart were removed from the local library at the user's request on 14 October 2026.
This guide remains an archived synthetic example. Use the [real HSBC document workflow](finance-real-document-sources.md) for the active demo.
The finance draft, published versions, and source snapshot were not changed.

```text
Finance CSVs --> PDF definitions + settlement memo + chart image
                       |
                 Inspect and analyze
                       |
              +--------+---------+
              |                  |
       Link existing model   Review chart rows
              |                  |
       Validate / publish    Create separate draft
              |                  |
       Playground answers    Validate / publish
```

## Prepared files

Use [synthetic-finance-supporting-evidence.pdf](demo-inputs/finance/synthetic-finance-supporting-evidence.pdf) for the main story.
Use [finance-settled-outflow-chart.png](demo-inputs/finance/finance-settled-outflow-chart.png) for the image-only example.

| PDF page | Content | Purpose |
| --- | --- | --- |
| 1 | Payment definition, settled status, debit/credit reconciliation | Explain the existing metric and prevent double counting |
| 2 | Fixed synthetic FX and rounding | Explain SGD conversion and reporting limits |
| 3 | Image chart with GB, HK, and SG settled outflow | Demonstrate AI extraction and row review |
| 4 | Settlement memo for `SYN-T00000000` | Trace a document statement to a source record |

Editable text copies: [payment definition](demo-inputs/finance/finance-payment-definition.md), [FX rules](demo-inputs/finance/finance-fixed-fx-rules.md), and [settlement memo](demo-inputs/finance/finance-settlement-memo.md).
The [manifest](demo-inputs/finance/manifest.json) records fixture and output checksums.
The fixture's original `documents.json` remains empty. New documents enter through the shared library and become model evidence after review.

## Story 1: explain the existing finance model

Say: “The database gives us amounts. These documents explain which amounts belong in the metric and how conversion works.”

1. Open [Supporting materials](http://localhost:8084/demo/materials?source=finance).
2. Select **synthetic-finance-supporting-evidence** in the library. Do not upload another copy.
3. Open **Extracted sections** and inspect pages 1, 2, and 4.
4. Optionally use **Analyze content** to generate a summary and proposed claims. Check their source quotations.
5. Expand **Add evidence to an existing semantic model**.
6. Set **Evidence to match** to **All extracted document text**.
7. Leave embedding similarity unchecked for this repeatable keyword demo.
8. Click **Find model links**, then expand **Candidate model links**.
9. Filter by **Finance sample context** and search for each target below.
10. Select one matching link per page. Check its evidence before selection.

| Search target | Required page | What the evidence supports |
| --- | --- | --- |
| `ledger_postings.amount_sgd` | page 1 | Signed postings net to zero; absolute postings count both sides |
| `fx_rates.sgd_rate` | page 2 | Fixed rates and conversion before aggregation |
| `payments.amount_sgd` | page 4 | The memo's converted amount belongs to one existing payment |

These exact field candidates were verified against starter definitions. A direct metric link is not required for published document answers.
Scores indicate relevance, not correctness. Edited definitions, embeddings, or AI visual transcriptions can change candidate ranking.
Use the original `page N` text candidate for this story, rather than a duplicate AI transcription candidate.

11. Enter your reviewer name and a note after checking the three passages.
12. Click **Approve selected links**.
13. Select the approved links and choose the finance model under **Target model**.
14. Click **Apply approved evidence to draft**.
15. Open Studio and inspect the documents and evidence links on the canvas.

Suggested review note:

> Checked September 2026 fixture scope, settled-only sender outflow, fixed FX rounding, and the SYN-T00000000 memo against source records. Documents add evidence, not new payment rows.

### Validate and publish

1. Select metric `total_amount_sgd` in Studio.
2. Paste the [reference SQL](demo-inputs/finance/finance-reference.sql) into its reference SQL field.
3. Save the draft and run validation.
4. Review the definitions and document evidence. Approve the items you checked.
5. Create a reviewed version with an unused version name, your name, note, and acknowledgment.
6. Publish that version and select it in Playground.

```sql
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM transactions
WHERE status = 'SETTLED';
```

The metric uses `payments`. The reference checks the corresponding settled `transactions` total.
Both return **686,572.96 SGD**, covering **4,850** settled payments during **1–30 September 2026 UTC**.

### Playground demonstrations

| Action or question | Expected result |
| --- | --- |
| Saved metrics → `total_amount_sgd` | Executed SQL returns 686,572.96 SGD |
| “What fixed USD-to-SGD conversion rate does this synthetic fixture use?” | Document evidence: 1 USD = 1.300000 SGD |
| “Why should both ledger sides not be summed as settled sender outflow?” | Page 1: signed amounts net to zero; absolute amounts double count |
| “What converted amount does settlement memo SYN-T00000000 report?” | Page 4: 496.90 SGD from 382.23 USD |

The saved metric and FX question were executed during preparation. The remaining document questions are presenter examples.
Use **Interpret question**, inspect the plan, then **Run this interpretation** for AI questions.
Published document citations use the reviewed version's attachments, not every file in the library.

**Current limit:** Combined finance prompts returned “Multiple permitted relationships require clarification” during preparation.
Run the saved metric and document question separately for this demo. Do not describe combined finance execution as verified.
The general combined-answer feature exists, but finance relationship selection needs a separate improvement.

## Story 2: turn the chart into a separate model

1. Select the PDF and analyze physical page **3**, or select the PNG and analyze page **1**.
2. Compare each proposed row with the image and the [row guide](demo-inputs/finance/finance-chart-row-guide.csv).
3. Verify the sender jurisdiction, SGD unit, September 2026 period, and exact value.
4. Select only the three checked rows.
5. Expand **Approve reviewed rows as a new draft model**.
6. Use title **Synthetic settled outflow by jurisdiction**, your name, a review note, and acknowledgment.
7. Click **Approve rows and create model**, then continue in Studio.

| Sender jurisdiction | Settled sender outflow, SGD |
| --- | ---: |
| GB | 44,454.90 |
| HK | 350,641.68 |
| SG | 291,476.38 |

The chart values are image pixels inside the PDF. Text extraction alone does not expose them.
Live GPT-4o extraction of PDF page 3 returned all three values, SGD units, jurisdictions, and the September 2026 period correctly.
The PDF and PNG represent the same facts. Use one source for model creation to avoid duplicate observations.
This creates a separate aggregate dataset. Do not append its values to the original payments or count both datasets together.
The [chart SQL](demo-inputs/finance/finance-chart-reference.sql) independently checks these values against the original finance data.
It is a grouped presenter check, not the new model's scalar reference SQL.
The generated model's metric names and observation IDs depend on reviewed extraction results. Inspect them before preparing its publication SQL.

## Preparation and verification

Regenerate the files with:

```sh
/tmp/helios-demo-implementation-venv/bin/python apps/helios/workbench/prepare_finance_materials.py
```

The generator reads serving CSVs only. It does not read evaluation truth files.
Output checksums reproduced exactly in a second directory.
Run `apps/helios/workbench/check_finance_materials.py` with the project Python environment for isolated lifecycle checks.
Add `--live-ai` to test GPT-4o document answers and chart extraction using `~/tokens/openai`.
See [verification results](finance-supporting-materials-verification.json) and [local staging record](demo-inputs/finance/local-staging.json).
All automated reviews and publication checks used isolated test state. Live review and publication remain your actions.
