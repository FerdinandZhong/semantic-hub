# UI polish and ontology plan

Recorded 4 November 2026. Status: P0–P6 done locally (`36ed508`, `eb62311`, `5cfbcaa`, `3609359`, `110e188`, `958c089`, `72e0839`). Nothing here is pushed or deployed.
This plan combines the UI review, the ontology design review, and the OpenMetadata assessment.
Read the [project status](project-status.md) for what is deployed.

## Context

The chat canvas, answer checks, materials cleanup, and Studio restyle are done.
Commits `9c1acb1`–`4929695` are deployed in `cc4890e`. Commits `6960649`–`72e0839` are local only.
A review against the UOB reference app and OpenMetadata screenshots scored the current UI 6.5/10.
A review of the first ontology design scored it 5.5/10, because three assumptions were wrong in the code.

References are style examples only:

- UOB reference: `../uob-ai-data-operations-workspace`, mainly `DESIGN.md` tokens, layout, and type scale.
- OpenMetadata: user screenshots of Lineage and Ontology Explorer. Semantic Hub does not connect to any UOB or OpenMetadata instance.

## Findings this plan acts on

| Finding | Evidence |
| --- | --- |
| Materials and Studio use two different page frames | Materials puts the workspace bar and tabs under the breadcrumb; Studio puts the title first. Breadcrumbs differ. |
| Canvas text is too small at Fit | Fit scale is 0.66, so node titles render about 10 px tall |
| Title sizes are inconsistent | 25 px on workspace pages, 26 px on Materials, 22 px on Studio and Validation; UOB specifies 25 px with an eyebrow |
| Studio lacks summary counts | UOB shows summary cards; the OpenMetadata explorer shows term, metric, and relation counts |
| Inspector values look like labels | Input text uses weight 600, and field gaps are wider than the rest of the page |
| Chat stacks answer details | UOB uses tabs for the answer, table, canvas, and SQL; the single-value table repeats the headline number unformatted |
| The sample has no glossary terms | Finance draft and `v1` have 0 terms; the `v1` graph has 1 GlossaryTerm, 6 Class, 26 Attribute, 7 OssieElement nodes |
| Studio has no glossary editor | Terms arrive only through AI proposals (`shared/helios_core/demo/proposals.py`) |
| The ontology artifact reaches external consumers | `shared/helios_core/demo/consumer.py:61` exports it; MCP reads the consumer API |
| Probable term-key bug | `builder_artifacts.py:76` reads `term['term']`; `propose.py:100` and walkthrough data write `name`. Not yet confirmed by a test. |

## Decisions recorded

- Do not embed `openmetadata-ingestion`. Version 2.0.7.2 declares the Collate Community License, has 45 unconditional dependencies, and strict pins that conflict with the Hub setup. Its glossary and ontology features run in the Java server.
- Build the glossary and ontology experience natively, using OpenMetadata as a design reference.
- Keep publication explicit. Every new term or relation goes through draft, validation, review, and publication.
- Show statuses and counts, never confidence percentages.
- An OpenMetadata export-file importer stays deferred until a licence review and a redacted sample export exist.
- The ontology view is its own workflow tab, decided 4 November 2026. A Studio canvas lens was rejected as too crowded:
  the Studio canvas has about 620 × 460 px, while the finance `v1` ontology needs about 40 objects
  (6 dataset frames, 26 attributes, 7 metric elements, plus terms). The tab gets about 1150 px at 1440 px width
  and reuses the same `HeliosCanvas` component. The existing Metadata lens already covers column detail in Studio.

## Delivery sequence

```text
P0 bug fix -> P1 quick UI fixes -> P2 shared page frame -> P3 chat answer tabs
                                         |
                                         v
               P4 ontology view -> P5 glossary authoring -> P6 typed relations
```

Each phase is one or more commits with its own tests. P0–P4 add no routes and change no exposed payloads.

### P0 — Confirm and fix the glossary term key

1. Write a failing test: a definition term keyed `name` must produce a `concept:<name>` link target.
2. If the test fails, read both `name` and `term` in `builder_artifacts.py`, preferring `name`.
3. Check other readers of `glossary_terms` for the same mismatch, including `materials.py:386`.

Files: `shared/helios_core/demo/builder_artifacts.py`, a new test in `apps/helios/tests/`.
Status: Done in `36ed508` — confirmed by `test_name_keyed_glossary_term_is_a_concept_link_target` and `test_name_keyed_glossary_term_is_a_concept_candidate`; `proposals.py` had the same mismatch and is fixed too.
Risk: published artifacts change only for definitions that hold terms. The finance sample holds none.

### P1 — Quick UI fixes (CSS and small JS)

1. Clamp the canvas Fit scale to at least 0.85, and let the canvas scroll or pan instead of shrinking.
2. Restore 25 px page titles everywhere, and restore the Studio eyebrow label.
3. Add a header summary to Studio and Validation, such as "6 datasets · 1 metric · 5 relationships", from data already on the page.
4. Set inspector input text to normal weight and tighten field spacing to the 12 px rhythm used in Materials.

Files: `apps/helios/console/static/demo-canvas.js`, `semantic_hub/web/editor-shell.css`, `apps/helios/console/static/demo-context.js`.

Done: `eb62311`. Fit stays at 0.85 or larger, titles are 25 px, the Studio and Validation header shows object counts, and inspector inputs use weight 400 with 12 px spacing.

### P2 — One shared page frame

1. Use one breadcrumb format: "Workspace / <workspace> / <page>".
2. Place the workspace bar, title, and workflow tabs in the same order on Materials, Studio, Validation, and Versions.
3. Make tab switching keep the frame fixed, so only content changes.

Files: `semantic_hub/editor.py`, `semantic_hub/support_pages.py`, `semantic_hub/web/editor-shell.css`, `semantic_hub/web/support-shell.css`.
Risk: both files patch inherited templates with regexes. Keep the existing patch tests passing.
Status: Done in `5cfbcaa`.

Follow-up `3eef7b4`: one header (API reference link) and the same sidebar position on all workspace pages. Verified locally: tabs at 110 px and h1 at 204 px on Materials, Studio, Validation and Versions; 75 tests passed; the browser smoke passes chat and page-route checks, then stops at provider registration as before. Open: the Overview tab's taller workspace selector puts its tabs at 132 px, so switching to Overview still shifts the layout by 22 px.

### P3 — Chat answer tabs

1. Replace the stacked disclosures with tabs: Answer, Table, Semantic canvas, SQL & checks, Provenance.
2. Hide the table for a single-value result, or format its value like the headline.
3. Keep restored history working; the canvas tab re-mounts from its saved payload.

Status: Done in `3609359`. The headline answer stays on top; the tabs are Table, Semantic canvas, SQL & checks and Provenance. The browser smoke now opens the Table tab before reading the value.

Files: `semantic_hub/web/workspace.js`, `semantic_hub/web/chat-history.css`.

Follow-ups: `28f22f7` gives the Overview bar the shared 50 px height, so workflow tabs sit at 110 px on every workspace page at desktop widths; at 390 px the Overview bar still wraps more than the shared bar. `6e905b3` updates the chat history browser check for tabbed results and names the workspace in the Overview breadcrumb. Local checks after P3: chat history and chat experience browser scripts pass; the smoke passes chat and page routes and stops at provider registration, as before. A restored conversation reopens with tabs closed, because history is saved when the answer completes.

### P4 — Read-only ontology view

1. Add an "Ontology" tab between Studio and Validation, inside the main UI.
   The workflow becomes Overview, Source data, Studio, Ontology, Validation & review, Versions & releases.
   In Studio, a selected object offers "Open in Ontology", which focuses the same node in the tab.
2. Draw the version's existing ontology graph: classes, attributes, metric elements, `MAPS_TO`, and `RANGE`.
3. Group nodes in a framed box per dataset; show any glossary terms as overlays and list unmapped terms separately.
4. Show a counts header and an inspector with definition, mapped columns, using metrics, evidence, and status.
5. Lay the graph out left to right, which also fixes the unused canvas space.

New canvas work: group frames and a left-to-right layout option. Data comes from existing endpoints.

Status: Done in `110e188`. The Ontology tab reads `/demo/api/context/artifacts` (draft or a reviewed version) and mounts `HeliosCanvas` with `{readOnly:true, layout:'grouped'}`; Studio, version and chat canvases render byte-identical SVG. Finance `v1` shows "6 classes · 26 attributes · 1 metric · 5 relationships · 0 glossary terms". Metric-to-field links come from the metric expression. Studio offers "Open in Ontology" for datasets, fields and metrics. The route and OpenAPI comparison is identical.
Deferred: the read-only version page (`/v2/editor?...&version=v1`) has no workflow tabs, so it has no Ontology tab; the tab's version selector covers reviewed versions instead. Unmapped terms are listed only, not drawn. At Fit scale 0.85 the finance graph needs panning.
Check: rerun the route and OpenAPI comparison; it must stay identical.

### P5 — Glossary authoring in the draft

1. Add, edit, and remove terms in Studio with name, definition, synonyms, and mapped columns.
2. Reuse the existing check that rejects unknown source columns.
3. Make term edits invalidate prior validation and review, like other semantic edits.
4. Add terms to the review table and the version page.

Risk: changes the saved definition. Keep `glossary_terms` backward compatible with existing proposals.

Status: Done in `958c089`. Studio has a Glossary inspector tab (name, definition, synonyms, mapped columns from the draft's source fields) and a "Glossary terms (n)" tree group. Terms save through the existing draft save route; no route or OpenAPI change. The save handler rejects a term with no name, no definition, a duplicate name (case-insensitive), an unknown column, or a name over 160 or definition over 1,000 characters. It skips terms identical to the stored draft, so old proposal-shaped terms (`term` key, `confidence`, empty definition) still save. The column check is shared with proposals (`ContextWorkspace.unknown_term_columns`).
Review: each term is its own review item (`term:<name>`, kind `glossary`), and the context item no longer carries `glossary_terms`. A save clears validation and item decisions, so a changed term must be approved before a version is published. Published bundles list glossary items only for definitions that hold terms. Consumer payloads keep their shape. Authored terms carry no `confidence`.
The version page lists each term with definition, synonyms and mapped columns.
Fix found on the way: the Ontology tab failed with "Cannot read properties of undefined (reading 'y')" once a term mapped to a field, because term nodes used a `columns` key that the canvas read as dataset columns. Term nodes now use `mappedColumns`.
Deferred: term edits are not drawn in the Studio canvas; no import or export of terms; the Ontology tab reads saved drafts only, so unsaved terms appear after Save draft.

### P6 — Typed term relations

1. Store `term_relations: [{from, relation, to, note}]` in the draft definition next to `glossary_terms`, capped at 200. Relation types are `broader`, `narrower`, `related`, `part_of` and `synonym`.
2. Relations live in the definition only. The ontology graph, its edge whitelist, the Helios loader and the artifact hashes are unchanged.
3. Consumers see an additive `definition.term_relations` in the version detail. Definitions without relations omit the field, so existing context, definition, artifact and review hashes stay identical.
4. Graph and Memgraph support is deferred to a separate, versioned change.

Status: Done in `72e0839`. The save handler rejects an unknown type, an endpoint that is not a term in the draft, a self relation, a duplicate, a broader/narrower cycle, and a delete or rename of a term that a relation still uses (the message names the relation). Names match case-insensitively. LLM proposals fail rather than drop a term that relations use. Each relation is a review item (`relation:<from>|<relation>|<to>`, kind `term_relation`), so edits clear validation and need approval. Studio shows relations per term with a count in the term list. The Ontology tab draws related terms with labelled edges and adds "· N term relations" to the counts line. The version page lists relations under the terms. Only the console OpenAPI changes, by an optional `term_relations` property.

## Verification for every phase

1. Run targeted tests for the changed behaviour and record their scope.
2. Run the regression suite listed in [local preview](local-preview.md).
3. Capture browser screenshots at 1440, 980, and 390 px; confirm no overflow and no page errors.
4. For P2–P6, rerun the route and OpenAPI comparison against the deployed commit.
5. Report local, mocked, and live results separately, then update the project status.

## Open questions

- Decided 5 November 2026: term edits require the same review as other semantic edits.
