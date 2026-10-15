# Scene 3: EFPIA page 4 input sheet

This is the earlier page 4-only example. For the current two-story demo, use the [updated storyline](pharma-intelligence-demo-story.md).
Its second story combines pages 4 and 5 and uses a different nine-row guide and SQL file.

Use this sheet to prepare the approval form yourself. These values do not constitute a completed review.

## Source and scope

- Source: [EFPIA — The Pharmaceutical Industry in Figures 2026](https://www.efpia.eu/media/owqczcqz/the-pharmaceutical-industry-in-figures-2026.pdf).
- Local PDF: `/tmp/helios-real-documents-20261013/efpia-industry-figures-2026.pdf`.
- Physical PDF page: **4**.
- Chart: geographic shares of sales for new medicines launched during **2020–2024**.
- Latest sales year: **2025**. The report publication year is **2026**.

The chart describes a launch cohort. It does not describe the entire pharmaceutical market.

## Extract and check the five rows

1. Open **Supporting materials** and upload the original PDF.
2. Expand **Select pages and review proposed rows** under **Review document visuals**.
3. Enter `4` and click **Analyze selected pages with AI**.
4. Compare each proposed row with the original page.
5. Correct each row's labels, scope, and unit before selecting it.
6. Select only the five checked rows below.

| Entity / region | Value | Unit |
| --- | ---: | --- |
| USA | 74.1 | % |
| Europe Top 5 | 15.6 | % |
| Japan | 3.6 | % |
| Pharmerging | 2.9 | % |
| Rest of the World | 3.8 | % |

Use these shared field values where the extraction needs correction:

| Field | Input |
| --- | --- |
| Metric | Share of sales of new medicines launched during 2020–2024 |
| Period | Latest sales 2025; launch cohort 2020–2024 |
| Population / scope | New medicines launched during 2020–2024; main markets shown in the chart |
| Denominator | Leave blank: no numeric denominator is printed |
| Page | 4 |
| Source evidence | Preserve the actual visible label or source text for each row |

Select rows by their entity and value. AI extraction can assign different row identifiers on each run.
Exclude nearby figures such as North America **54.7%** and Europe **23.7%**; they describe a different measure.
Do not replace the launch period with the nearby growth period **2020–2025**.

## Complete the model creation form

1. Expand **Approve reviewed rows as a new draft model**.
2. Enter this model title:

   ```text
   EFPIA New Medicine Sales by Region
   ```

3. Enter your own name in **Reviewer**.
4. Use this decision note only after checking the original chart:

   ```text
   I checked the five regional values against the original EFPIA Industry Figures 2026 report, physical page 4. The values are USA 74.1%, Europe Top 5 15.6%, Japan 3.6%, Pharmerging 2.9%, and Rest of the World 3.8%. The scope is medicines launched during 2020–2024, using latest sales data for 2025. These values are not total pharmaceutical market shares. No numeric denominator is printed, so that field remains unknown.
   ```

5. Select the review acknowledgment after completing your checks.
6. Click **Approve rows and create model**.
7. Open the newly created model in Studio.

## Expected result

```text
Original PDF, page 4
        |
        v
Five AI-proposed observations
        |
        v
Your row review and approval
        |
        v
New source: document_observations + document_sources
        |
        v
Semantic draft and provenance canvas
        |
        v
Separate Studio validation, review, and publication
```

The new model should contain five observation rows and their document provenance.
Its starter definitions include typed fields, a provenance relationship, one count metric, and five individual value metrics.
The canvas can show the new tables, metrics, and document evidence.
The PDF also remains a document in the supporting-material library.

Open the **new model** to inspect these tables. The existing pharmaceutical intelligence model does not receive them automatically.
Creating this model does not publish it. Publication requires the normal Studio review process.

## Local demo cleanup

On 13 October 2026, intermediate uploads, extraction records, and the generated FDA draft model were archived.
The pharmaceutical intelligence working drafts were also archived; its base dataset remains available.
The original four workspaces, manufacturing `v1.0`, and model configuration were preserved.
The archive is `/tmp/helios-document-cleanup-20261013-231833/`.
No approval or model creation was performed for this EFPIA preparation sheet.
