# Pharmaceutical demo: two document-to-model stories

Updated 14 October 2026. [中文版](pharma-intelligence-demo-story.zh-CN.md).

**Story 1 enriches an existing model with evidence. Story 2 creates a separate model from reviewed chart rows.**
You perform all approvals and publication steps yourself.

| Story | PDF pages | Result | What the playground queries |
| --- | --- | --- | --- |
| 1. Explain the scope of an existing metric | 14 | Evidence attached to pharmaceutical intelligence | Published metrics plus cited page 14 document answers |
| 2. Turn charts into queryable facts | 4 and 5 | New document-derived source and semantic model | Rows you checked and approved |

```text
Story 1: PDF page 14 → review evidence links → existing draft → validate → publish → query
Story 2: PDF pages 4,5 → review numeric rows → new draft → validate → publish → query
```

## Preparation

1. Open [Semantic Hub](http://localhost:8084/demo).
2. Confirm **Pharmaceutical Industry Intelligence & New Drug Analysis** appears in the catalog.
3. Keep **Pharma sample** separate; it demonstrates synthetic batch quality.
4. Test the drafting and playground profiles under **Model configuration** with `gpt-4o`.
5. Download the [original EFPIA 2026 PDF](https://www.efpia.eu/media/owqczcqz/the-pharmaceutical-industry-in-figures-2026.pdf).
6. Keep the SQL files and row guide below available for copying.

Local PDF: `/tmp/helios-real-documents-20261013/efpia-industry-figures-2026.pdf`.
All page numbers below are physical PDF pages, starting at one.

The 14 October cleanup archived **EFPIA New Medicine Sales by Region** and its previous upload.
The original four workspaces, manufacturing `v1.0`, and pharmaceutical intelligence workspace remain unchanged.
Backup: `/tmp/helios-efpia-reset-20261014-090454/`.
No new models or releases were created in the live workspace during preparation.

## Story 1 — Explain why 74.1% and 54.7% answer different questions

Allow 12–15 minutes, plus AI processing time.

### Scene 1: Start with the existing model

1. Open **Pharmaceutical Industry Intelligence & New Drug Analysis → Open Studio**.
2. Inspect `industry_observations` and `us_new_medicine_sales_share_percent`.
3. Show the current value: **74.1%**, for USA sales of new medicines launched during 2020–2024.
4. Open **Add supporting material** to enter the shared library with this source selected.

Say:

> The model already has a sales-share metric.
> A new report contains another percentage that looks similar.
> We will preserve the difference through reviewed evidence and explicit definitions.

### Scene 2: Upload the PDF and inspect page 14

1. Choose **New document** and upload the original PDF.
2. Find **1. Analyze pages with AI**.
3. Enter `14` and click **Analyze selected pages with AI**.
4. Expand **Review page results** and compare the original with the derived text and proposed observations.
5. Inspect the world-market chart and its source note.
6. Leave **Approve reviewed rows as a new draft model** unused for this story.

Page 14 reports **54.7% for North America (USA and Canada)**.
It covers the **2025 global retail and hospital prescription pharmaceutical market**, at **ex-manufacturer prices**.
Its Europe category includes Belarus, Turkey, Russia, and Ukraine.
These regions and this population differ from page 4's launch-cohort chart.

The lower chart concerns retail-price components in 2024. Exclude it from this story's links.

Say:

> Page 14 gives total-market context.
> North America is not USA alone, and the total prescription market is not a new-medicine launch cohort.
> We attach this evidence to explain an exclusion. We do not replace 74.1% with 54.7%.

### Scene 3: Link page 14 evidence to the existing model

1. Expand the separate **Add evidence to an existing semantic model** card.
2. Keep **Evidence to match → Analyzed pages: 14**. Text summarization above is optional.
3. Leave **Use embedding similarity** unchecked for the prepared keyword route.
4. Click **Find model links**.
5. Expand **Candidate model links**.
6. Set **Filter by model** to **Pharmaceutical Industry Intelligence & New Drug Analysis**.
7. Keep **Filter by status → Suggested** and **Sort links → Highest relevance**.
8. Use **Search candidate links**: search `industry_observations.indicator page 14`, then `us_new_medicine_sales_share_percent page 14`. Selections persist between searches.
9. Inspect their **Section: page 14** labels and source quotations.
10. Select only the appropriate links from this table.

| Target | Passage to check | Why this is a valid link |
| --- | --- | --- |
| `industry_observations.indicator` | Page 14's world prescription-market scope and North America definition | Supporting context for distinguishing different indicators |
| `us_new_medicine_sales_share_percent` | Page 14's 54.7% North America passage, with its market-scope note | Evidence for an exclusion; it does **not** substantiate the metric's 74.1% value |

The original PDF text yielded these two targets in the checked keyword-matching route.
Matching defaults to page 14, including its original text and AI transcription.
Choose **All extracted document text** only when broader matching is needed.
Inspect the page label and quotation, not only the score.
For a repeatable demo, use the original-text `page 14` candidates, rather than duplicate AI-transcript links.
If suggestions differ, do not approve unrelated targets. Check the source filter and use the original-text keyword route.

Optional text analysis produces summaries and cited claims. Optional embeddings can change candidate ranking.
Neither operation establishes that a passage supports a target.
There is no manual arbitrary-target link editor in this workflow.

Enter your own name and this note after checking the page:

```text
I checked physical page 14 against the original EFPIA 2026 PDF. This passage describes the 2025 total prescription pharmaceutical market at ex-manufacturer prices. North America includes USA and Canada. I approve this link as scope and exclusion evidence only. It does not substantiate or replace the USA 74.1% new-medicine sales-share value from page 4. The retail-price components chart is excluded.
```

11. Click **Approve selected links**.
12. Keep the approved links selected.
13. Select the pharmaceutical intelligence model in **Target model**.
14. Click **Apply approved evidence to draft**.
15. Click **Open Studio to draft with AI** to return to Studio.

Applying evidence attaches reviewed passages and provenance. It does not import page 14's numbers or change SQL.
The canvas shows supporting-document edges to the reviewed objects. These are evidence links, not database joins.

### Scene 4: Make the scope visible in the metric

For a predictable demo, edit the existing metric directly instead of regenerating all definitions.
Keep its name, expression, unit, and filters unchanged.
Append this sentence to its description or exclusion rules:

```text
Exclude total prescription-market shares. EFPIA page 14 reports North America (USA and Canada), not USA alone. Its 54.7% figure has a different population from this metric's 2020–2024 new-medicine launch cohort, measured using 2025 sales.
```

Save the draft. Editing definitions can make old matching suggestions stale; finish evidence application before this edit.
You can also demonstrate AI drafting, but inspect every proposed change before applying it.
Do not claim that attaching a document automatically changes metric behavior.

### Scene 5: Validate and publish

Use [Story 1 reference SQL](demo-inputs/story-1-pharma-reference.sql).
Copy **one statement into each matching metric's verification SQL field**.
All six metrics need reference SQL, even though this story changes only one metric's explanation.

| Metric | Expected result |
| --- | ---: |
| `novel_approval_count` | 46 |
| `evidence_patient_count` | 105 |
| `no_prior_adc_orr_percent` | 75 |
| `prior_adc_orr_percent` | 44 |
| `no_prior_adc_durable_response_percent` | 58 |
| `us_new_medicine_sales_share_percent` | 74.1 |

1. Save the draft and run validation.
2. Inspect metric reconciliation, relationship checks, and document evidence.
3. Review the objects; use batch approval only after checking the selected objects.
4. Open **Versions & releases**.
5. Enter an unused version name, such as `v1.0`, your name, and a review note.
6. Confirm the acknowledgment and create the reviewed version.
7. Publish the version.
8. Select **Use for queries** if you also want to activate the version for sample queries.

Suggested release note:

```text
Reviewed the six starter metrics and their reference SQL. Added EFPIA page 14 as scope/exclusion evidence. Preserved the USA new-medicine sales-share calculation and its 2020–2024 launch cohort with latest sales in 2025.
```

### Scene 6: Query the published version

1. Open **Playground** and select the published version.
2. Ask: `What is the US share of sales for new medicines launched during 2020–2024?`
3. Click **Interpret question**, then inspect the selected metric and scope.
4. Click **Run this interpretation**. Expect **74.1%**.
5. Ask: `How many FDA CDER novel drugs were approved in 2025?` Expect **46**.

For deterministic execution, select the corresponding **Saved metrics** entry instead of using natural-language interpretation.
The interpretation model can request clarification; inspect its proposed metric before running.

Now demonstrate the published document evidence path:

> What was North America's share of the entire prescription pharmaceutical market in 2025?

The existing source has no structured metric for that question. Do not accept 74.1% as its answer.
1. Keep **AI · query data + documents** selected, or choose **Document evidence**.
2. Enter the contrast question and click **Interpret question**.
3. Inspect the retrieved page 14 passage.
4. Click **Answer from these documents**. Expect the source-reported **54.7%**.
5. Expand the citation and check page 14, the exact quotation, and document revision.

The selected published version must include the reviewed page 14 attachment. Upload or draft application alone is insufficient.
This document answer needs no new reference SQL. It reports a source statement; it does not create a structured metric.
A reusable 54.7% SQL metric still requires reviewed structured facts and metric validation.

Say: “The Hub preserves two meanings. SQL computes 74.1% from the new-medicine dataset. Published document evidence reports 54.7% for North America.”

### Combined AI question

Ask: `What is the US share of sales for new medicines launched during 2020–2024, and how does it differ from North America's share of the total prescription market in 2025?`
Inspect the SQL and document plan, then select **Run AI query and answer**.
The answer should cite 74.1% from SQL and 54.7% from page 14 with their distinct scopes.
For `North America during 2020–2024`, expect clarification. The 2025 observation cannot answer that question.

## Story 2 — Create a new model from pages 4 and 5

Allow 15–20 minutes, plus AI processing time.

### Scene 1: Start a separate document workflow

1. Return to **Supporting materials**.
2. Select the PDF used in Story 1 and choose its latest revision.
3. Earlier reviewed evidence stays intact when you analyze again.
4. Enter `4, 5` in **Pages to analyze**.
5. Click **Analyze selected pages with AI**.
6. Inspect each page beside the proposed rows.

Repeat analysis creates the next document revision automatically. Story 1 retains its earlier revision and attachments.
Choose **New document** and upload the PDF only if you want a separate library entry.
This story uses **Create a new semantic model**. The evidence action remains available but is not required.

### Scene 2: Review exactly nine observations

Use the [row guide CSV](demo-inputs/efpia-pages-4-5-row-guide.csv) as a copy sheet, not as an AI extraction result.
It supplies exact entity, metric, period, unit, population, and suggested metric-name values.

| Page | Entity | Indicator | Value | Unit | Period |
| --- | --- | --- | ---: | --- | --- |
| 4 | USA | New medicine sales share | 74.1 | % | Launches 2020–2024; sales 2025 |
| 4 | Europe Top 5 | New medicine sales share | 15.6 | % | Launches 2020–2024; sales 2025 |
| 4 | Japan | New medicine sales share | 3.6 | % | Launches 2020–2024; sales 2025 |
| 4 | Pharmerging | New medicine sales share | 2.9 | % | Launches 2020–2024; sales 2025 |
| 4 | Rest of the World | New medicine sales share | 3.8 | % | Launches 2020–2024; sales 2025 |
| 5 | Europe | Pharmaceutical R&D expenditure | 56344 | EUR million | 2024 |
| 5 | USA | Pharmaceutical R&D expenditure | 75895 | USD million | 2024 |
| 5 | Japan | Pharmaceutical R&D expenditure | 16607 | JPY million x 100 | 2024 |
| 5 | China | Pharmaceutical R&D expenditure | 114557 | CNY million | 2024 |

1. Select only these nine rows after checking their chart labels.
2. Correct their editable labels to match the CSV exactly, including the en dash in `2020–2024`.
3. Keep `denominator` blank; neither chart prints a numeric denominator for these observations.
4. Preserve the actual source labels in **Source quote**, and keep the correct physical page.
5. Exclude page 4 prose values and page 5's earlier years and parallel-import chart.
6. Record any unresolved extraction uncertainty rather than silently assuming a value.

For Japan, the chart explicitly scales yen as **million × 100**. Keep 16607 with that unit.
Do not relabel it as 16607 million yen or convert currency without an explicit conversion method.
Europe on page 5 is the R&D series; it is not page 4's Europe Top 5 sales region.
Do not add or rank the four R&D values as though they used the same currency.

AI output varies. If a required row is missing, rerun selected-page analysis before approval and check the replacement proposals.
The form cannot add an arbitrary missing row. Do not approve unrelated rows to reach nine.
The SQL below assumes these nine reviewed rows, not an arbitrary extraction result.

### Scene 3: Create the draft model

1. Expand **Approve reviewed rows as a new draft model**.
2. Enter the title `EFPIA New Medicine Sales and R&D Evidence`.
3. Enter your own reviewer name.
4. Use this note only after checking both original pages:

```text
I checked nine chart observations against physical pages 4 and 5 of the EFPIA 2026 PDF. Page 4 contains five regional new-medicine sales shares for launches during 2020–2024, with latest sales in 2025. Page 5 contains four R&D values for 2024. I retained each national-currency unit, including Japan's million-yen times 100 scale. I excluded other years, prose figures, and the parallel-import chart. Numeric denominators remain unknown. These observations must not be pooled across indicators or currencies.
```

5. Select the acknowledgment and click **Approve rows and create model**.
6. Click **Open created model in Studio**.
7. Inspect `document_observations`, `document_sources`, and their provenance relationship on the canvas.

Expect **nine observation rows**, **one source row**, and **ten starter metrics**: one count plus nine individual values.
The original document and reviewed-row provenance already belong to the new model.
No additional model link is required. Creation does not publish the model.

### Scene 4: Prepare and validate the metrics

Generated metric names resemble `observation_17_value`. IDs depend on extraction order.
Do not assume that `observation_1` represents USA.

1. Match each generated value metric to its entity, indicator, and period using its description and source row.
2. Rename it to the corresponding `metric_name` in the CSV.
3. Keep its generated expression unchanged; it selects the original reviewed observation ID.
4. Keep the count metric named `reviewed_observation_count`.
5. Copy the matching statement from [Story 2 reference SQL](demo-inputs/story-2-efpia-reference.sql) into each verification field.
6. Save and validate all ten metrics.

The reference queries locate rows by business labels, page, unit, and period.
The generated expressions locate rows by observation ID. Comparing both routes helps catch a wrong row-to-metric mapping.
An empty result or duplicate match fails reconciliation; correct the labels or inspect duplicate observations.
Never replace the reference query with a constant such as `SELECT 74.1`.
If you keep generated metric names, change the reference query's `AS` alias to the exact current metric name.

Example after renaming the USA R&D metric:

```sql
SELECT value AS us_rd_2024_usd_million
FROM document_observations
WHERE source_page = 5
  AND entity = 'USA'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'USD million'
  AND period = '2024';
-- Expected: 75895 USD million
```

### Scene 5: Publish and query

1. Review validation results, source provenance, object definitions, and supporting evidence.
2. Create a reviewed version named `v1.0`, with your reviewer name and decision note.
3. Publish it, then open **Playground** and select that version.
4. Choose a saved metric for the first deterministic run.
5. Try the natural-language questions below and inspect each interpretation before execution.

| Question | Saved metric | Expected result |
| --- | --- | --- |
| How many reviewed observations are available? | `reviewed_observation_count` | 9 |
| What is the US share of new-medicine sales for 2020–2024 launches? | `us_new_medicine_sales_share_percent` | 74.1% |
| What was pharmaceutical R&D expenditure in the USA in 2024, in USD million? | `us_rd_2024_usd_million` | 75895 USD million |
| What was pharmaceutical R&D expenditure in Europe in 2024, in EUR million? | `europe_rd_2024_eur_million` | 56344 EUR million |

Say:

> The PDF is the original evidence.
> I reviewed the extracted rows and preserved their units, periods, and page locations.
> SQL checks the metric calculation, and publication freezes the reviewed semantic version.
> The playground queries those structured rows under that version.

## Is reference SQL necessary for unstructured data?

| Material or output | Current requirement | What it establishes |
| --- | --- | --- |
| Uploaded PDF or supporting passage | No reference SQL | Human review checks the passage and its relevance |
| Evidence link to an existing model | No separate reference SQL for the link | Review checks the target and scope; existing metrics still need SQL |
| Numeric rows created from charts | Reference SQL for every semantic metric before publication | Reconciles the compiled calculation with a reference query over stored rows |
| Original chart accuracy | Source-page review, not SQL | Checks extraction, labels, values, units, dates, and population |

Reference SQL is a rule of the current publication workflow, not an inherent requirement for every unstructured document.
SQL alone cannot prove that OCR or chart extraction is correct.
Automating draft reference-query suggestions could reduce typing later, but independent human review would still be needed.
That automation is not part of this preparation.

## Presenter checks and limits

- Keep reviewer names and approvals authentic. Do not reuse another person's acknowledgment.
- Repeat page analysis from the latest revision whenever needed. It creates a new revision and preserves earlier approvals.
- Story 1 changes supporting evidence and meaning; it does not add a new numeric fact table.
- Story 2 creates a separate source; it does not merge facts into pharmaceutical intelligence.
- Natural-language interpretation is model-dependent. Saved metrics provide the repeatable demo route.
- Playground answers from linked published document passages. Cross-model document Q&A and currency conversion remain outside this increment.
- [Preparation verification](pharma-demo-stories-verification.json) distinguishes deterministic checks from live AI behavior.

Both stories passed isolated validation, publication, and saved-metric execution: six metrics for Story 1 and ten for Story 2.
The related regression suite passed 83 tests. This preparation did not rerun live AI extraction or natural-language interpretation.
Reproduce the deterministic check with the original PDF:

```sh
python apps/helios/workbench/check_pharma_demo_stories.py \
  --pdf /tmp/helios-real-documents-20261013/efpia-industry-figures-2026.pdf
```
