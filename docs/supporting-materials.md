# Supporting materials in Semantic Hub

The shared library stores document revisions independently of a data source.
A document can support several semantic models through separately reviewed links.
Applying evidence changes a draft only. Studio validation, version review, publication, and query activation remain separate actions.

The page starts with shared analysis, followed by two independent actions:

1. **Analyze pages with AI:** select pages and review proposed rows beside the originals.
2. **Create a new semantic model:** approve checked rows to create a typed dataset and semantic draft.
3. **Add evidence to an existing semantic model:** review links and attach supporting passages to a model draft.

Both actions can use the same analysis revision. Neither action requires the other.
“Dataset” refers to the stored rows. “Semantic model” includes definitions, metrics, and relationships over those rows.
Text summarization is optional and covers all extracted document text, not only the selected visual pages.
The evidence action stays collapsed by default for PDFs and images.
Its three steps find links, review links, and apply approved evidence.
After page analysis, matching defaults to the analyzed pages. Select **All extracted document text** for broader matching.
Previously reviewed links remain available when the matching scope changes.

Applying evidence does not merge extracted fact rows, change metric SQL, or publish a model.
Candidate links can be collapsed, filtered by model or status, and sorted by relevance or model name.
**Search candidate links** searches every generated candidate across model names, targets, page labels, quotations, and matching reasons.
All entered terms must match. Search works locally and preserves selection, including hidden selections.
The list reports selected links outside the current filters. Clearing the search restores the full matching list.
Analysis results start collapsed with a claim count. The document summary and each claim can be expanded separately.
Candidate links keep their selection, status, source page, and score visible; expand each link to inspect its quotation and matching reason.
Sorting preserves link selection and expanded evidence within the current document revision.
Highest relevance is the default order across all document sections. Scores indicate relevance, not factual confidence.
Keyword matching supplies the score unless embedding matching was used; embedding matching combines keyword and vector scores.
Repeat page analysis creates a new document revision with the same original bytes and a fresh extraction.
Earlier extractions, models, reviewed links, and attachments remain unchanged. Failed analysis saves no revision.
Select the latest revision to analyze again. Enter all desired pages together; separate runs do not accumulate rows.
Text summarization of reviewed evidence requires a new revision; existing text remains available for matching.

```text
Upload -> Analyze pages -> Review results
                              |-- Create dataset + semantic draft -> Studio
                              `-- Review model links -> Attach evidence -> Studio
Repeat analysis -> New document revision (earlier evidence remains unchanged)
```

## Use the library

1. Open **Supporting materials** from the Hub, or **Add supporting material** from Studio.
2. Upload TXT, Markdown, DOCX, PDF, PNG, or JPEG content.
3. Inspect the extracted sections and their source locations.
4. Select **Analyze content** to extract proposed definitions, rules, entities, and context using the drafting model.
5. Select **Find model links** to match passages to model definitions.
6. Enable embedding matching when its profile is ready under **Model configuration**.
7. Review each suggested passage, target, and explanation. Select relevant links and enter your reviewer name and note.
8. Approve the selected links, then choose their target model and add them to its draft.
9. Open Studio to inspect the supporting documents and canvas links. Validate and review the model before publication.

Studio now presents one primary upload route through the shared library.
The optional legacy text-note form remains collapsed.
Opening the library from Studio preserves the source selection and provides a return link.
After applying evidence, select **Open Studio to draft with AI**.
Then select **Draft semantic definitions with AI** to stage a candidate using the structured schema and document evidence.
Inspect and explicitly apply the candidate before validation.
Navigation does not generate proposals or modify definitions automatically.

Keyword matching works without an LLM or an analysis result.
Content analysis scans every extracted section in bounded batches.
Each extracted claim must cite an exact passage from its source section.
The validator can recover original PDF whitespace, including spaces around punctuation, while preserving words, numbers, and punctuation.
It stores the recovered source span, not the model's reformatted quotation.
One bounded repair attempt handles invalid schema or unsupported citations in each batch.
An unresolved error leaves the previous analysis unchanged.
An exact quotation proves the text exists; a reviewer must still verify the interpretation and applicability.

## Visual extraction and reviewed fact sources

The [visual-document workflow](visual-document-facts.md) adds GPT-4o extraction from images and selected PDF page images.
Select one to six physical pages from a PDF containing at most 512 pages.
Image-only and scanned pages use the same bounded visual workflow.
Upload transcribes them automatically with the draft model: images use page 1, and PDFs use their first six image-only pages.
Text pages in a mixed PDF keep their extracted text; transcripts are added as labeled `vision` sections.
If the draft model is missing or rejects the request, the upload is kept and a notice asks for manual page analysis.
Original page previews accompany proposed observations and retain their physical page numbers.
Reviewers correct and select rows, confirm source-page review, and create a new typed fact source with a semantic draft.
The source retains units, periods, populations, denominators, uncertainty, original checksum, extraction, and reviewer decisions.
Creating reviewed facts does not publish the semantic model.
Studio validation, object review, version creation, and publication remain separate actions.

## Model configuration

The configuration page has three independent profiles:

- Semantic draft generation: model proposals and document content analysis.
- Model playground: question interpretation and sample-result explanations.
- Supporting-material embeddings: optional vector matching between document sections and semantic objects.

New workspaces default the embedding profile to disabled with model `text-embedding-3-small`.
The current local review instance enables inherited mode and has passed the embedding connection test.
Inherited mode reuses the launch endpoint and credential, while retaining the separately selected embedding model.
Custom mode supports an OpenAI-compatible embeddings endpoint and an environment-variable credential reference.
The connection test calls the embeddings API and reports vector dimensions.
Credentials are never returned by configuration APIs or stored in the document library.

## Matching and local vector storage

The matcher searches model descriptions, metric metadata, field and table meanings, and declared ontology/glossary concepts.
Keyword matching weights distinctive terms and requires stronger overlap for short field descriptions.
Generic identifiers receive lower priority unless the evidence explicitly names their field.
Optional vector matching adds cosine similarity to candidate ranking.
Scores express relevance, not factual confidence or approval.
The matcher proposes at most four targets per section, with at most two from one model. Reviewers must check for missing or incorrect suggestions.

Vectors are stored locally in Lance format, keyed by text SHA256 and an endpoint/model fingerprint.
Fixed-size vector tables separate provider fingerprints and dimensions.
Each vector retains its source text, model, endpoint, and dimension metadata.
Valid legacy SQLite cache entries migrate to Lance without provider calls.
Document revisions and review records continue to use SQLite.
Repeated matching reuses unchanged vectors. A different endpoint or model creates a separate cache namespace.
Invalid or incompatible cached dimensions are rejected and cleared for retry.
Embedded LanceDB writes on-disk Lance tables without a separate server.
It scans at most 1,000 semantic objects per match and is not a production-scale retrieval benchmark.

## Revision and review guarantees

- Document bytes, extracted sections, and original checksums are retained by revision.
- New document revisions keep previous content and model attachments intact.
- Analysis validates all citations before saving results; invalid model output leaves prior analysis unchanged.
- Reviewed links retain their reviewer and decision note. Updating reviewed evidence requires a new document revision.
- Link review and draft application check source snapshot and model-definition hashes.
- Draft application also checks the expected draft revision to prevent overwriting concurrent edits.
- Applied attachments contain selected source sections, document revision, original checksum, target links, and review attribution.
- The generated attachment has its own checksum, separate from the original uploaded file.
- Published versions freeze these artifacts through the existing Studio release mechanism.
- Canvas document edges show reviewer-linked supporting assertions. They do not assert observed entity relationships.

The library records which draft received each material revision.
A newer document revision does not automatically update those drafts or published versions.
The UI displays earlier applications so reviewers can identify models requiring a new evidence review.

## Current limits

Uploads are limited to 5 MiB, extracted text to 256 KiB, and sections to 128 with 2,000 characters each.
Visual extraction supports PNG/JPEG and scanned PDFs through selected page images.
PDFs contain at most 512 pages; each visual request selects one to six pages.
Images are limited to 20 million pixels and rendered page previews to a 2,048-pixel maximum edge.
Encrypted PDFs, unsupported files, unsafe DOCX compression, and nested Word tables are rejected with an explanation.
The library covers imported local models. Remote connection profiles still require source import adapters.
Review attribution is local. Enterprise identity, document permissions, external repositories, and automated policy enforcement need adapters.
Material links enrich context; they do not automatically rewrite metric SQL or establish a causal explanation.
The playground continues to calculate from published definitions and treats documents as background evidence.

## Verification

The [earlier verification record](supporting-materials-verification.json) records the original text-material increment.
The [visual verification record](visual-document-verification.json) tracks the new visual and Lance increment.
The final backend regression passed 207 tests.
Live OpenAI image/PDF extraction and Lance reuse passed. Desktop/mobile workflow checks also passed.

- `test_document_parser.py`: extraction, source locations, limits, and malformed documents.
- `test_materials.py`: cited analysis, model matching, review gates, cache behavior, and immutable releases.
- `test_materials_api.py`: routes, profile separation, request validation, and safe provider errors.
- `test_demo_llm_settings.py` / `test_demo_embeddings.py`: model profiles and bounded embedding requests.
- `check_materials_browser.py`: desktop/mobile upload, review, application, revision inspection, and escaped content.

Verified on 13 October 2026: 141 backend tests and the desktop/mobile materials workflow passed.
A live isolated test used GPT-4o for six exact-cited statements and text-embedding-3-small for 1,536-dimensional vectors.
Hybrid matching proposed finance and manufacturing targets; repeating the request reused cached vectors with zero provider calls.
The live test used a synthetic policy document and did not modify user model state.

The final browser run also verified Studio provenance display and a rendered semantic evidence edge at desktop size.

The [pharmaceutical intelligence walkthrough](pharma-intelligence.md) demonstrates clinical denominator evidence and the unified AI drafting flow.
The follow-up regression run passed 123 tests across runtime, Hub, connections, dataset, builder, and supporting-material behavior.
A live GPT-4o check of the original EFPIA PDF verified 53 claims across 30 extracted sections.
The curated trial brief also produced a six-metric candidate using attached evidence.
These checks ran in isolated state and did not approve any user release.

## Query applied evidence after publication

Reviewed library links can now support Playground document answers.
Apply the reviewed evidence to the draft, publish that version, and select it in Playground.
Choose Auto or Document evidence to inspect passages and request a cited answer.
The answer reads frozen published attachments. Later library revisions and draft edits do not replace those passages.
No new reference SQL is needed for document answers. Existing metric validation remains required for publication.
See [the Playground contract](model-playground.md) for supported attachment types and evidence-check limits.

## Vision, OCR, and embedding decisions

See [the discussion record](vision-ocr-and-embeddings-discussion.md) for model roles and implemented boundaries.
Visual understanding uses the draft model; optional retrieval uses a separate text-embedding profile.
A separate OCR service is not required for the existing visual workflow.
