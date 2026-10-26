# Unified Semantic Hub UI

The approved card-first design now uses the existing Hub APIs and editor behavior.
The implementation keeps one navigation shell across catalog, authoring, evidence, settings, and questions.
The approved review artifact remains in [ui-draft](ui-draft/README.md).

```text
/ → /v2 — workspace cards
       ├── Overview — current source, draft, and publication state
       ├── /v2/editor — Source data | Studio | Validation & review | Versions & releases
       ├── /v2/materials — source-linked evidence library
       ├── Talk to your data — published version and approved execution
       ├── Builders & connections — local or external providers
       └── /v2/settings — built-in inference configuration
```

## What changed

- The landing page shows workspace cards with real names, status, counts, and provider ownership.
- Search and builder/status filters work against the returned catalog.
- New workspace creates an independent draft using the existing source-connection API.
- Remote connector profiles retain their explicit import-required state.
- The built-in editor uses the shared sidebar and workspace subtabs.
- Settings and supporting materials use that same shell.
- Navigation uses consistent SVG icons instead of text symbols.
- Native Helios opens through an explicit external-provider handoff.

The editor is not an iframe or a separately styled application.
It uses ordinary internal page navigation and the existing editor scripts.
The shared sidebar comes from `semantic_hub/shell.py`.
Page adapters change navigation and presentation while retaining the original DOM contracts and API requests.
This keeps one implementation of validation, review, evidence, and publication behavior.

## State and safeguards

Draft changes use the existing revision checks and unsaved-edit protection.
The query flow remains pinned to a published version and context hash.
Users inspect the interpretation before selecting Run.
Question edits invalidate the pending Run action.
Conversation history is scoped to workspace, version, and context hash.
History remains in page memory and clears when the page reloads.
Restored conversations contain no executable Run actions.
No chat history is written to disk by this UI feature.

Existing legacy URLs remain available for compatibility.
New navigation and the default application landing route use the unified shell.
The v1 consumer API and native Helios checkout remain unchanged.

## Manual check

1. Open `http://127.0.0.1:8099/v2` and inspect the workspace cards.
2. Open Finance sample and select Studio in the workspace subtabs.
3. Edit a draft field and save it without leaving the shared UI.
4. Open Source data, inspect a table, and open supporting materials.
5. Use Validation & review and Versions & releases for the existing governed publication flow.
6. Open Talk to your data and select a published saved metric.
7. Inspect the interpretation, select Run, and inspect the result provenance.
8. Start another conversation and reopen the first from the page-session history.
9. Open Model configuration and return through the same sidebar.

Use a disposable workspace for write tests.
A starter workspace has no published release until its review and publication steps complete.
Native Helios still requires its own data source and inference setup for live queries.

## Verification

The combined Python regression run passed all 73 tests.
After the final layout changes, all 24 provider and UI adapter tests passed again.
Browser checks passed at 1440, 980, and 390 pixels with no JavaScript errors.
The governed finance fixture returned SGD 686,572.96.
An editor check saved and restored a draft field and confirmed that published versions stayed unchanged.
It also confirmed that dismissing the unsaved-edit prompt prevented navigation.
Conversation checks covered restored results, scope isolation, and removal of stale Run actions.

The Python regression suite covers shared routes, preserved editor controls, source escaping, provider authorization, and existing consumer behavior.
Browser checks cover actual workspace creation, navigation, finance execution, and responsive layouts.
The browser scripts use an isolated finance fixture rather than the manual-review state.
The fixture seed refuses to modify a nonempty directory.

```bash
.venv-semantic-hub/bin/python -m pytest tests/providers tests/amp/test_amp.py \
  apps/helios/tests/test_semantic_hub_consumer.py \
  apps/helios/tests/test_retrieval_service.py \
  apps/helios/tests/test_retrieval_index.py -q
python tests/providers/browser/smoke.py --base-url http://127.0.0.1:8299
python tests/providers/browser/chat_history.py --base-url http://127.0.0.1:8299
```

Playwright and Chromium must be installed for browser checks.
Use the smoke script's `--chromium` argument for a custom browser path.
