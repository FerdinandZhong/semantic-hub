# Semantic Hub v2 UI draft

This is a review artifact, not a runtime UI change.
Open `index.html` in a browser. No build or network connection is required.
The draft contains illustrative data and makes no API calls.
Use **Next page** or **Page index** to review all 11 screens.

## Requirements review

The previous implementation made the version boundary visible as a product boundary.
It replaced the useful catalog with a selected-model inspector and sent editing into a second interface.
This draft corrects the navigation structure before production implementation.

| Requirement | Proposed design |
| --- | --- |
| Keep workspace cards as the first page | Workspaces opens a searchable, filtered card catalog. No model opens automatically. |
| Follow UOB guardrails card quality | Consistent card headers, status badges, short descriptions, metadata, and aligned action footers. |
| Keep the built-in editor in the main UI | Studio is an editable subtab within Semantic workspace. No legacy-editor link or second shell. |
| Keep editor workflow as subtabs | Overview, Source data, Studio, Validation & review, Versions & releases. |
| Improve sidebar icons | Consistent 24-pixel SVG geometry, 1.65-pixel strokes, 19-pixel display size, and text labels. |
| Review before implementing | Standalone clickable draft only. The running Hub and provider implementation remain unchanged. |

```text
Semantic Hub — one persistent application shell
├── Workspaces — card catalog; default landing page
├── Semantic workspace — selected workspace stays visible
│   ├── Overview
│   ├── Source data
│   │   ├── Tables and schema previews
│   │   └── Supporting documents and evidence
│   ├── Studio — object tree, relationship canvas, editable inspector
│   ├── Validation & review
│   └── Versions & releases
├── Talk to your data — same workspace; explicit published version
├── Builders & connections
└── Model configuration
```

## Page-by-page walkthrough

1. **Workspace catalog:** business purpose, model status, builder, and one Open workspace action per card.
2. **Workspace overview:** current state, publication summary, and clear next steps.
3. **Source data / tables:** table list, selected schema, and bounded preview together.
4. **Source data / documents:** document library and evidence inspector within the selected workspace.
5. **Studio:** the actual editing layout, with object tree, relationship canvas, and editable properties.
6. **Validation & review:** technical checks and human decisions remain separate.
7. **Versions & releases:** immutable version history, publication readiness, and consumer access.
8. **Talk to your data:** conversation history, published version, interpretation approval, and result provenance.
9. **Helios workspace:** consistent Hub identity and an explicit native-application handoff.
10. **Builders & connections:** configure providers independently of business workspace cards.
11. **Model configuration:** inference settings for the built-in workflow; Helios settings stay provider-owned.

The detailed walkthrough uses Payments & transfers.
Other Built-in cards show their own identity and a link to that design scenario.
The draft does not show finance results under another workspace name.

## Interaction decisions

- Opening a workspace leads to Overview. Studio remains one click away in the subtab row.
- Source tables and documents share Source data. Neither requires another application shell.
- Switching between tabs retains the selected workspace.
- Save, validation, approval, and publication controls are shown where the user needs them.
- Production implementation must preserve unsaved edits or ask before discarding them.
- A draft change never changes a published query version.
- Chat retains workspace identity and shows the selected published version.
- Editing the question removes the pending Run action.
- The review toolbar belongs only to this prototype, not the product.

The prototype simulates actions and does not persist editor fields across page changes.
It demonstrates the layout and approval sequence, not the underlying data operations.

## Architecture boundary

A shared UI does not require embedding Helios in the Hub.
Built-in authoring should render inside the Hub shell using its existing APIs and editor behavior.
An iframe or a link to a separately styled legacy editor would repeat the original problem.
Native Helios remains a separate application with its own identity and permissions.
The Hub labels that handoff explicitly; it does not pretend external releases are already imported.

## Reference inspected

The available UOB repository is `../uob-ai-data-operations-workspace`.
The card reference is `demo/static/guardrails-predefined.js` and its `.g-card` styles.
The current editor reference is `apps/helios/console/templates/demo-context.html`.
The reference projects and runtime application files were not modified.

## Draft verification

Browser checks covered all 11 screens at 1440, 980, and 390 pixels.
The checks found no horizontal page overflow, JavaScript errors, or API calls after the layout corrections.
The interaction check covered card filtering, opening Studio inside the shared shell, simulated approval, publication gating, and question-edit invalidation.
Screenshots were inspected for the card catalog and integrated editor.
