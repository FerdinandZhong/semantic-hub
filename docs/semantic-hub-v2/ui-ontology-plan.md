# UI polish and ontology plan

Recorded 4 November 2026. Status: P0–P2 done locally (`36ed508`, `eb62311`, `5cfbcaa`); P3–P6 planned. Nothing here is pushed or deployed.
This plan combines the UI review, the ontology design review, and the OpenMetadata assessment.
Read the [project status](project-status.md) for what is deployed.

## Context

The chat canvas, answer checks, materials cleanup, and Studio restyle are done.
Commits `9c1acb1`–`4929695` are deployed in `cc4890e`. Commits `6960649`–`5cfbcaa` are local only.
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

Files: `semantic_hub/web/workspace.js`, `semantic_hub/web/chat-history.css`.

### P4 — Read-only ontology view

1. Add an "Ontology" tab between Studio and Validation, inside the main UI.
   The workflow becomes Overview, Source data, Studio, Ontology, Validation & review, Versions & releases.
   In Studio, a selected object offers "Open in Ontology", which focuses the same node in the tab.
2. Draw the version's existing ontology graph: classes, attributes, metric elements, `MAPS_TO`, and `RANGE`.
3. Group nodes in a framed box per dataset; show any glossary terms as overlays and list unmapped terms separately.
4. Show a counts header and an inspector with definition, mapped columns, using metrics, evidence, and status.
5. Lay the graph out left to right, which also fixes the unused canvas space.

New canvas work: group frames and a left-to-right layout option. Data comes from existing endpoints.
Check: rerun the route and OpenAPI comparison; it must stay identical.

### P5 — Glossary authoring in the draft

1. Add, edit, and remove terms in Studio with name, definition, synonyms, and mapped columns.
2. Reuse the existing check that rejects unknown source columns.
3. Make term edits invalidate prior validation and review, like other semantic edits.
4. Add terms to the review table and the version page.

Risk: changes the saved definition. Keep `glossary_terms` backward compatible with existing proposals.

### P6 — Typed term relations (requires a separate approval)

1. Add `term_relations: [{from, to, relation, status, note}]` to the definition, using a SKOS-style set: broader, narrower, related, part-of, synonym.
2. Add one ontology edge type, `RELATED_TERM`, with `relation` as a property.
3. Before shipping, check the Helios graph loader, the consumer API export, and MCP clients against the new edge.
4. Version the artifact schema if any consumer rejects unknown edge types.

## Verification for every phase

1. Run targeted tests for the changed behaviour and record their scope.
2. Run the regression suite listed in [local preview](local-preview.md).
3. Capture browser screenshots at 1440, 980, and 390 px; confirm no overflow and no page errors.
4. For P2–P6, rerun the route and OpenAPI comparison against the deployed commit.
5. Report local, mocked, and live results separately, then update the project status.

## Open questions

- P5: should term edits require the same reviewer sign-off as metric edits?
- P6: approve typed relations now, or after P4 and P5 ship?
