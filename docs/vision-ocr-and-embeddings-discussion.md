# Vision, OCR, and embeddings: discussion and decisions

Recorded: 19 October 2026.
Scope: document understanding and retrieval in Semantic Hub.
This record distinguishes implemented behavior from recommendations. It does not change model settings.

## Answer and terminology

GPT-4o can understand images through the OpenAI API.
It is a vision-language model (VLM): a model that processes images and language together.
It can read visible text, describe diagrams, interpret charts, and propose table values.
A separate OCR model is optional for this workflow.
OCR means optical character recognition. Its main task is converting image text into machine-readable text.

Image understanding and image embeddings are different capabilities.
Understanding produces text or structured observations. Embedding produces numeric vectors for similarity search.
OpenAI's documented public embedding models accept text, rather than direct image inputs.
The `text-embedding-3-large` model explicitly lists images as unsupported.
We have not identified a public OpenAI embedding endpoint for a shared image-and-text vector space.

## Discussion sequence

1. The user requested compatibility with older and newer OpenAI models.
2. The implementation added model-family request routing and verified three models against bounded Playground cases.
3. The user asked for an OpenAI model that supports multimodal embeddings.
4. We distinguished direct image embeddings from embeddings of extracted visual descriptions.
5. The user noted that GPT-4o already understands images and asked about OCR or a VLM.
6. We confirmed that GPT-4o can perform document understanding directly through image input.
7. We recommended separate document-understanding and embedding configurations.

The earlier embedding answer did not mean that OpenAI cannot understand images.
It addressed direct vector generation from images through the public embeddings API.

## Recommended architecture

```text
PDF pages / PNG / JPEG
          |
          v
Vision model: text + chart context + proposed observations
          |
          v
Human review + document revision + source-page lineage
          |
          +----> New draft semantic model from reviewed rows
          |
          +----> Evidence attached to an existing semantic model
          |
          +----> Optional text embeddings ----> Lance search index
```

The two model actions are independent. A user can perform both.
Attaching evidence does not insert observations into an existing source table.
Creating a draft model does not publish that model.
Embedding similarity proposes relevant links. It does not validate a document claim.

## Model configuration

| Function | Recommendation | Status |
| --- | --- | --- |
| Understand PDF page images and uploaded images | GPT-4o with image input and structured output | Existing implemented visual workflow |
| Run Playground interpretation and bounded tools | Configured compatible query model | GPT-4o, GPT-5.4, and GPT-6.1 Sol passed recorded live checks |
| Embed extracted text and visual descriptions | `text-embedding-3-large` for a quality-oriented option | Recommendation; no profile changed |
| Lower-cost text embeddings | `text-embedding-3-small` | Existing default embedding model; historical live checks passed |
| Direct joint image/text embeddings | Separate multimodal embedding model if needed | Not implemented by the OpenAI text-embedding client |
| Dedicated OCR service | Add only if measured document requirements justify it | No dedicated OCR service integrated |

The current configuration has separate draft, Playground, and embedding profiles.
Visual extraction currently uses the draft profile. It does not have an independent OCR profile.
The selected draft model must support image input and the extraction output contract.
An embedding profile is unnecessary for a vision model to read an uploaded page.
Lance is storage, not the model that understands the document.

## Implemented code and boundaries

- [Visual extraction](../shared/helios_core/demo/visual_documents.py) renders selected pages and requests structured visual observations.
- [Supporting materials](../shared/helios_core/demo/materials.py) manages revisions, extraction, review, and evidence/model actions.
- [Embedding client](../shared/helios_core/demo/embeddings.py) sends text arrays to an OpenAI-compatible `/embeddings` endpoint.
- [Model compatibility](../shared/helios_core/llm/openai_compat.py) selects model-family generation controls and protocol behavior.

Current uploads support TXT, Markdown, PDF, DOCX, PNG, and JPEG within the documented limits.
Visual PDFs contain at most 512 pages. A visual request selects one to six pages.
The upload size limit is 5 MiB.
Extraction can repeat with different pages. Revisions preserve prior review and model provenance.
See [supporting materials](supporting-materials.md) and [visual facts](visual-document-facts.md) for exact behavior.

## Extraction quality and review

Small text, complex charts, and unclear scans can produce incorrect proposals.
Retain the original page beside proposed rows during review.
Preserve units, geography, time windows, categories, and source locations.
Leave values unknown when the source does not print them.
For example, do not infer a demographic denominator merely by adding category counts.
Use semantic SQL validation after reviewed rows become queryable structured facts.
SQL cannot establish whether a chart was read correctly. Source-page review remains necessary.

## Verification status

Historical live GPT-4o image/PDF extraction and Lance reuse passed.
See [visual verification](visual-document-verification.json).
The latest compatibility increment passed 120 regression tests and nine live Playground cases across three models.
See [compatibility verification](model-compatibility-verification.json).
Those nine cases tested connections, supported scope, missing periods, and unsupported geography.
They did not establish GPT-6 visual extraction accuracy or a multimodal embedding benchmark.
No new live extraction or embedding benchmark ran for this discussion record.
No deployed model profile, document, or published version changed.

## Official references

Checked on 19 October 2026.

- [OpenAI images and vision](https://developers.openai.com/api/docs/guides/images-vision): image understanding, input handling, and limitations.
- [GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o): image-input model capabilities.
- [OpenAI text embeddings guide](https://developers.openai.com/api/docs/guides/embeddings): text embedding models and vector generation.
- [text-embedding-3-large](https://developers.openai.com/api/docs/models/text-embedding-3-large): text support; images unsupported.

## Remaining work

1. Keep VLM and embedding explanations explicit in configuration help and demonstrations.
2. Evaluate extraction accuracy on the actual HSBC, DOE, FDA, and EFPIA pages before broader claims.
3. Verify newer-model visual extraction separately from Playground text/tool compatibility.
4. Add direct multimodal embeddings only if image similarity becomes a measured product requirement.

These items are planned follow-ups. This documentation update does not implement them.
