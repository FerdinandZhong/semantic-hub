# Separate-project AMP live-test runbook

Updated 3 November 2026. Use branch `fix/amp-provider-bootstrap` for this implementation.
The Hub repository has no tracked Git submodule. The AMP never fetches Helios.
The previous copy failure with exit status 24 remains unexplained until CAI supplies detailed clone/copy logs.

## Recorded checkpoint: 3 November 2026

The independent Hub AMP launched successfully and was last updated to `cc4890e` on `fix/amp-provider-bootstrap`.
Its restart, authenticated health, Swagger, OpenAPI, inventory, and updated-asset checks passed.
The streamed saved finance metric returned **SGD 686,572.96** from published `v1.0`.
The latest response included its semantic canvas and 6/6 answer checks. Seven updated UI assets matched the reviewed code.
See the [status record](project-status.md) for application identity, context hash, test scope, and environment repair.

This checkpoint does not complete the procedures below.
Separate Helios acceptance, live free-text inference, caller isolation, full persistence, and hosted Agent Studio checks remain open.

## First install: built-in only

1. Create a new project from this branch using `.project-metadata.yaml`.
2. Keep `SEMANTIC_HUB_PROVIDER_MODE=auto` and leave Helios origins empty.
3. Confirm project creation completes before diagnosing any job failure.
4. Confirm the setup job succeeds and only the Hub application is created.
5. Open the workspace cards, built-in Studio, supporting materials, and Playground.
6. Build, review, publish, and query the finance sample.
7. Restart Hub and confirm the published release and credentials remain usable.

Record the source commit, runtime identifier, task logs, application URL, and results.
Do not record credentials in test evidence.
If project copying fails again, collect the CAI server clone/copy logs; no application code has run at that point.

## UI checks after deploying commits past `cc4890e`

Run these after deploying the UI polish and ontology commits. Record each result in the [project status](project-status.md).

1. Open Overview, Source data, Studio, Ontology, Validation & review, and Versions & releases for finance.
   Confirm the breadcrumb reads "Workspace / Finance sample / <page>" and the tabs do not move between pages.
2. Ask the saved finance metric in Talk to your data. Confirm the headline shows **SGD 686,572.96** once.
   Open Table, Semantic canvas, and "SQL & checks · 6/6 passed", then Provenance.
3. Start a new conversation, reopen the first one, and confirm its tabs and canvas still work.
4. Open Ontology. Confirm the counts line, one framed box per dataset, and that selecting an object fills the inspector.
5. In Studio, add a glossary term mapped to `payments.amount_sgd` and save.
   Confirm validation becomes stale, the term appears in the review table, and Ontology counts one glossary term.
6. Delete the test term and save, so the published finance release stays unchanged.
7. Open Supporting materials and confirm the analysis counts, grouped claims, and **Edit values** controls.
8. Repeat steps 1, 2, and 4 at a phone width and confirm there is no horizontal scrolling.

Drafts that already hold glossary terms need their review decisions approved again once, because terms now have their own review items.

## Optional provider checks

Prepare the independent project using [the standalone Helios guide](standalone-helios.md).

| Case | Expected result |
| --- | --- |
| No origins | Hub starts; fresh registry contains only Built-in |
| Only one origin | Hub starts; optional connection reports incomplete configuration |
| Unreachable origin | Hub starts; no new provider record |
| Login redirect or rejected key | Hub starts; optional connection reports failed health |
| Both endpoints healthy | One `helios-external` provider is registered |
| Repeat startup | No duplicate provider or workspace |
| Helios starts after Hub | Restart Hub or run the explicit retry, then refresh the browser |
| Existing linked workspace, Helios outage | Preserve its binding; never redirect it to Built-in |
| `builtin_only` | Skip network checks; preserve existing state |

After successful registration:

1. Verify both Helios applications require CAI authentication.
2. Confirm Helios diagnostics show the signed-in browser user.
3. Test authorized workspace discovery with two callers who have different Helios grants.
4. Confirm each caller sees only authorized organizations and models.
5. Create or link a workspace and confirm its card appears in Hub.
6. Open Helios from that card and verify the native model selection.
7. Test native building and chat using Helios's own setup and permissions.
8. Confirm Hub MCP still excludes link-only external models from executable releases.

Health probes prove endpoint readiness only. They do not prove browser identity or native query readiness.
Live optional-provider acceptance remains pending until these results are recorded.

## Diagnostics

Use the `Optional Helios` startup log for the connection result.
A missing registration key can produce HTTP 302, 401, or 403 through authenticated CAI ingress.
Set the dedicated `HELIOS_HEALTH_API_KEY` in the Hub environment and retry.
Do not disable authentication or reuse a shared key for user workspace discovery.

To inspect Hub and configured provider endpoint readiness:

```sh
.venv-semantic-hub/bin/python deployment/cai/verify.py --hub-origin https://<actual-hub-host>
```

This command uses `CDSW_APIV2_KEY` for Hub and `HELIOS_HEALTH_API_KEY` for Helios.
It writes a credential-free report to the deployment state directory.
A failed optional provider check makes this diagnostic command fail, but does not prevent Hub startup.
