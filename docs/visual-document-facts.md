# Visual documents, reviewed facts, and Lance storage

Implemented locally on 13 October 2026.
The supporting-material library now accepts PNG/JPEG images and scanned PDFs.
Reviewers can turn extracted observations into a separate queryable source and semantic draft.

## Processing path

```text
Original image/PDF -> selected page images -> GPT-4o proposed observations
                                                       |
                                           Review, correct, select rows
                                                       |
                                                       v
Hub model <- typed facts + source provenance <- explicit creation approval
    |
    v
Studio validation -> object review -> immutable version -> publication

Extracted text -> OpenAI embeddings -> local Lance tables -> model-link matching
```

The existing semantic-drafting profile supplies the vision endpoint and model.
The implementation uses OpenAI-compatible Chat Completions with image inputs and strict JSON schema output.
GPT-4o was used for live checks.
OpenAI documents [image understanding](https://developers.openai.com/api/docs/guides/images-vision) and [PDF inputs](https://developers.openai.com/api/docs/guides/file-inputs).
The application renders selected PDF pages locally to preserve explicit physical-page provenance.

The embedding profile supplies `text-embedding-3-small` or another configured compatible text embedding model.
The [embeddings endpoint](https://developers.openai.com/api/reference/resources/embeddings/methods/create) receives extracted text, not raw images.
This increment does not use CLIP or claim image-vector similarity search.
Vision extraction identifies content; embeddings rank related semantic objects.

## Use the UI

1. Open **Supporting materials** and upload a PNG, JPEG, or PDF.
2. Find **1. Analyze pages with AI**. Page selection remains visible.
3. Enter up to six physical page numbers and select **Analyze selected pages with AI**.
4. Expand **Review page results** and inspect each proposed row beside its original page.
5. Correct entity, metric, value, unit, period, population, denominator, quotation, and uncertainty as needed.
6. Select the rows to retain.
7. Under **Create a new semantic model**, expand the approval form and enter title, reviewer, and note.
8. Confirm source-page review and select **Approve rows and create model**.
9. Open the generated model in Studio.
10. Validate SQL and relationships, review objects, then create and publish a version.

Creating facts approves only the selected extraction rows.
It does not approve or publish the semantic model.
The UI keeps reviewed rows read-only. Page analysis remains available on the latest document revision.
Repeating analysis creates a new revision while retaining earlier extraction results and model provenance.
The same results can also support existing semantic models through the separate evidence action.
An interrupted creation retains the review decision and offers **Finish reviewed model creation**.
Recovery reuses that exact decision; it does not accept changed rows.

## What is generated

| Output | Contents |
| --- | --- |
| `document_observations` | Reviewed values, units, population, period, denominator, page, source quotation, uncertainty, and reviewer |
| `document_sources` | Document ID, revision, original SHA256, extraction ID, extraction model, and review time |
| Semantic draft | Typed fields, business meanings, a source relationship, observation count, and individual value metrics |
| Evidence document | Original proposed rows, reviewer corrections, extraction pages, and reviewed links to other models |
| Canvas lineage | Observation-to-document relationship and source document evidence |

One exact-row value metric is generated for each numeric observation, up to 19 values plus the count metric.
The fact table can contain up to 128 reviewed rows.
Unknown numeric values remain SQL nulls.
Generated value metrics do not pool different units, periods, populations, or endpoints.
The existing AI proposal workflow can further enrich the draft from its schema and archived evidence.
The new source remains separate from existing models.
Shared-library links can support existing models without inventing cross-source SQL joins or enterprise entity identifiers.

Each generated source is immutable and stored under `STATE/document-models/`.
The Hub discovers these sources after restart.
Original fixture registries and existing published semantic versions remain separate.
The source has `data_origin=document_evidence`; an uploaded internal file is not mislabeled as a public dataset.

## Lance storage

Vectors are now written to `STATE/supporting-material-vectors.lancedb/` using embedded LanceDB.
Each table uses the Lance columnar format and a fixed vector dimension.
Rows store the source text, text SHA256, endpoint/model fingerprint, model, endpoint, dimensions, and vector.
Endpoint and model changes use separate namespaces.
Repeated text reuses its stored vector.
Valid entries in the previous SQLite vector cache migrate without another embedding request.
Malformed vectors and changed dimensions are rejected and cleared for a retry.

Document bytes, review decisions, and revisions remain in SQLite.
Typed facts use the existing immutable CSV snapshots and DuckDB runtime.
Lance stores embeddings; it does not replace review records or the SQL execution engine.
The current matcher still performs bounded cosine ranking over at most 1,000 semantic targets.
This increment does not claim ANN indexing or production-scale latency.

## Extraction and review limits

- Files are limited to 5 MiB. Images are limited to 20 million pixels.
- Visual PDF extraction supports up to 32 pages, with one to six explicitly selected pages per request.
- Larger text PDFs retain the existing text-only path where parsing succeeds.
- Encrypted PDFs remain unsupported.
- Page previews are bounded to 2,048 pixels on their longest edge.
- Output includes only selected pages. A successful request does not establish coverage of the full document.
- Vision quotations are marked `visual_unverified`. They are not claimed as exact machine-verified source text.
- The prompt requests printed numbers and nulls for missing values. Reviewers must still check possible model inference or omission.
- Unlabeled chart heights, ambiguous legends, and unreadable content require explicit uncertainty or omission.
- One bounded schema-repair attempt is allowed. Failed extraction leaves the previous analysis intact.
- A document revision creates one fact model. Repeat page analysis automatically creates the next revision.
  The latest revision permits different or repeated pages. Interrupted model creation must finish before another analysis.

## Pharmaceutical reference SQL

Use these queries with the corresponding original pharmaceutical intelligence metrics.

```sql
-- novel_approval_count: 46
SELECT COUNT(*) AS novel_approval_count FROM approval_events;

-- evidence_patient_count: 105, the original efficacy population
SELECT SUM(patient_count) AS evidence_patient_count FROM trial_cohorts;

-- no_prior_adc_orr_percent: 75 percent
SELECT value AS no_prior_adc_orr_percent
FROM trial_results WHERE result_id = 'beamion_no_prior_adc_orr';
```

The [pharmaceutical walkthrough](pharma-intelligence.md) contains all six reference queries.
The visual review also corrected two earlier curated chart assignments: Pharmerging is 2.9%; Rest of the World is 3.8%.

## Verification

Tests cover image/PDF limits, page provenance, provider failures, strict schemas, explicit review, corrections, nulls, typed queries, restart durability, and immutable releases.
They also cover interrupted creation recovery, Lance cache migration, dimension checks, and model isolation.
Browser checks cover desktop/mobile layout, source previews, editing, acknowledgment, historical read-only views, and escaped document content.
Live checks use public FDA and EFPIA evidence in isolated state.
Their automated review exercises the data flow and is not a user's semantic approval.
See [verification results](visual-document-verification.json).
