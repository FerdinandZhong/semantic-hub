# Manufacturing evidence: real DOE maintenance guide

Use the U.S. Department of Energy's **Operations & Maintenance Best Practices, Release 3.0** (August 2010).
It provides maintenance definitions, condition-monitoring context, and equipment thermal images.

- [Official full PDF](https://www.energy.gov/sites/default/files/2020/04/f74/omguide_complete_w-eo-disclaimer.pdf)
- [Upload-ready excerpt](demo-inputs/manufacturing-real/doe-maintenance-evidence-excerpt.pdf): nine pages, approximately 1.64 MiB.
- [Download the excerpt from GitHub](https://raw.githubusercontent.com/FerdinandZhong/semantic-hub/main/docs/demo-inputs/manufacturing-real/doe-maintenance-evidence-excerpt.pdf)
- [Provenance manifest](demo-inputs/manufacturing-real/manifest.json): original/excerpt checksums and physical page mapping.

The complete source exceeds the app's 5 MiB upload limit.
The excerpt retains the source cover, authorship, disclaimer, and selected unchanged pages.
Only page selection and PDF metadata changed. The source text and figures were retained.

## Select pages and targets

These numbers refer to physical PDF positions, rather than printed section page numbers.

| Uploaded excerpt page | Original PDF page | Content | Candidate semantic target |
| --- | --- | --- | --- |
| 1 | 1 | Cover | Source attribution |
| 2 | 3 | Authorship and publisher | Source attribution |
| 3 | 4 | Disclaimer | Source context |
| 4 | 51 | Section 5.3: preventive maintenance | `work_orders` dataset: scheduled maintenance context |
| 5 | 52 | Section 5.4: predictive maintenance | `sensor_readings` dataset: condition measurements supporting maintenance decisions |
| 6 | 59 | Predictive technologies and equipment application matrix | `assets` dataset: equipment-monitoring context |
| 7 | 60 | Thermography introduction | `sensor_readings` dataset: general measurement context |
| 8 | 64 | Thermal images of motors, gearbox, conveyor, and steam trap | `sensor_readings` dataset: visual condition-monitoring context |
| 9 | 65 | Further thermal examples and bearing trends | `sensor_readings` dataset: visual condition-monitoring context |

Start with excerpt page **4** and the **`work_orders` dataset** link.
This is the clearest document-evidence demo for the current manufacturing model.
Use page **5** for the sensor-measurement story, and page **8** for an image-analysis demonstration.

## Attach evidence to the existing model

1. Upload `doe-maintenance-evidence-excerpt.pdf` in **Supporting materials**.
2. Analyze excerpt page **4**.
3. Review the preventive-maintenance passage beside the original page image.
4. Expand **Add evidence to an existing semantic model**.
5. Find model links using the analyzed pages.
6. Filter to **Manufacturing sample context** and search `work_orders`.
7. Select the dataset-level link for page 4's preventive-maintenance passage.
8. Review and approve the selected link with your reviewer name and note.
9. Apply the approved evidence to the manufacturing draft.
10. Save, validate, review, and publish the updated model in Studio.

Model links are candidates. Select the passage and target that actually match.
Do not select a downtime-value field simply because the passage mentions reducing downtime.
If only unrelated field links appear, do not approve those links.

Suggested decision note:

> Checked uploaded excerpt page 4 against original DOE PDF physical page 51, section 5.3. This passage supports preventive-maintenance terminology and scheduled-activity context for the work_orders dataset. It does not verify any synthetic work order, downtime value, or observed equipment failure. Original and excerpt checksums and page mapping are recorded in the source manifest.

The app versions the uploaded excerpt and its reviewed evidence.
The app does not automatically ingest the sidecar manifest.
Include the original source URL and page mapping in your review note when you need that attribution in the published evidence.

## Demo questions

After publishing the reviewed passage, ask:

- According to the attached DOE guide, how is preventive maintenance scheduled?
- How does the attached guide distinguish preventive maintenance from predictive maintenance? (Attach pages 4 and 5.)
- What kinds of equipment problems do the thermal images illustrate? (Analyze, review, and attach page 8.)

Separately, run the saved metric `planned_downtime_minutes` against the unchanged source pack.
Its independent reference SQL is:

```sql
SELECT SUM(downtime_minutes) AS planned_downtime_minutes
FROM work_orders;
```

The unchanged sample returns **312 minutes**.
The existing expression sums all work-order rows without a status predicate.
The guide does not establish this total or change the metric's SQL.

## Evidence boundaries

The manufacturing source contains synthetic assets, sensor readings, and work orders.
The guide provides real engineering context. It does not describe those particular assets or events.
Thermal surface images are not equivalent to `process_temperature_k` or `air_temperature_k`.
Do not use an image's temperature scale as a threshold for those fields without a separate engineering definition and unit review.
The model contains no vibration field; do not invent one from the guide's application matrix.
Evidence attachment does not insert work orders, sensor readings, or extracted fact rows into the existing model.
