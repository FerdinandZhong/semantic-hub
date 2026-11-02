# Live CAI acceptance runbook

Status: ready for a disposable-project rehearsal; live multi-application acceptance remains pending.
Local tests and endpoint reachability do not establish hosted acceptance.
Use the [operator guide](amp-operator-guide.md) for configuration details.

## Target record

Complete these fields before testing. Leave unknown values blank.
Never record keys, cookies, or authorization headers.

| Field | Value |
| --- | --- |
| Test date / operator | |
| CAI workspace URL / version | |
| Disposable project ID | |
| Hub Git revision / provider Git revision | |
| Selected mode | |
| Standard Python runtime identifier | |
| Node.js / npm versions (bundled) | |
| Management identity / approved permissions | |
| Ingress identity-header verification evidence | |
| Test users / expected native model permissions | |
| Hub / Helios API / Helios UI application IDs | |
| Hub / Helios API / Helios UI HTTPS origins | |
| State backup / evidence directory | |
| Native backend / inference profile identifiers | |

## Prepare

1. Use a disposable CAI project with persistent storage and synthetic test data.
2. Select Standard Python 3.11 and confirm application quotas.
3. Select `bundled`, `external`, or `builtin_only` through `SEMANTIC_HUB_PROVIDER_MODE`.
4. Keep `SEMANTIC_HUB_STATE_DIR` stable; its manifest default is `/home/cdsw/state/semantic-hub`.
5. Keep authentication enabled for every exposed application.
6. For bundled mode, provide Node.js 20 or newer, npm, Git, and package-registry access.
7. For bundled mode, set the exact `SEMANTIC_HUB_RUNTIME_IDENTIFIER`.
8. Supply bundled provisioning with `CDSW_API_URL`, `CDSW_PROJECT_ID`, and an authorized management `CDSW_APIV2_KEY`.
9. Verify ingress authentication and replacement of client-supplied identity headers.
10. Set `HELIOS_CAI_PROXY_AUTH_CONFIRMED=1` only after that verification.

Bundled is the default mode. It creates independent Helios API and UI applications beside Hub.
Bundled application defaults total 6 CPUs and 24 GB memory.
Preparation requests 2 CPUs/8 GB; provisioning requests 1 CPU/2 GB and can overlap native startup.
These defaults do not establish measured capacity.

External mode requires exact HTTPS `HELIOS_UI_ORIGIN` and `HELIOS_API_ORIGIN` values.
It creates no native applications and does not change the external deployment.
Built-in-only mode skips native checkout, native dependencies, and native provider registration.
The built-in implementation remains installed in every mode.

## Launch and retry

```text
AMP import -> preparation -> provisioning -> Hub application
                                |                  |
                         Helios API + UI     authenticated checks
                                                   |
                                      browser + identity + restart evidence
```

1. Import this repository and select `.project-metadata.yaml`.
2. Record the exact repository revision and selected runtime.
3. Wait for `semantic-hub-setup`, then `semantic-hub-provision`, then the Hub application.
4. Inspect preparation and provisioning reports beneath the deployment state directory.
5. Record application IDs and actual HTTPS origins from Workbench.
6. If CAI omits origins, set both Helios origin variables and rerun provisioning.
7. Rerun the failed job after correcting its configuration; preserve `provision.json` and persistent state.
8. Confirm retries reuse owned application IDs without creating duplicates.
9. Open the actual Hub application URL from Workbench.
10. Run endpoint verification with an authorized caller key supplied through the environment.

The manifest contains five tasks: create/run preparation, create/run provisioning, and start Hub.
Its scripts are `deployment/cai/prepare.py`, `deployment/cai/provision.py`, and `deployment/launchers/hub.py`.
Application restarts do not provision resources or install packages.
Do not reimport the AMP as an idempotent upgrade procedure.

```bash
python deployment/cai/verify.py --hub-origin https://YOUR-HUB-APPLICATION
```

The verifier saves `verification.json` and rejects redirects, including login redirects.
It uses `CDSW_APIV2_KEY` as the caller key and never serializes it.
The verifier always leaves full CAI acceptance pending.
Preserve preparation evidence, `provision.json`, verification output, redacted logs, screenshots, and permission expectations together.

## Acceptance evidence

Enter an outcome and evidence reference for each applicable row.
Blank cells below mean no result has been recorded.
Use `pass`, `fail`, `blocked`, or `not applicable`, with an explicit reason.

| Check | Required evidence | Outcome | Evidence reference |
| --- | --- | --- | --- |
| A01 bundled install | Locked revisions, three ready applications, actual registered origins | | |
| A02 retries | Stable IDs after successful rerun and controlled partial-failure recovery | | |
| A03 browser and identity | Correct model navigation, unauthenticated denial, CORS, stripped identity headers | | |
| Picker authorization | Two callers' allowed models; denied/revoked access prevents saving; no key persistence | | |
| Shared catalog | Saved links visible to Hub users; native permissions still restrict model access | | |
| A04 independent restart | Hub and provider restart separately; credentials, versions, and uploaded material persist | | |
| A05 outage | Hub remains available; external actions fail explicitly without Built-in substitution | | |
| A06 external mode | No native resources created or changed; supplied origins work | | |
| A07 built-in-only mode | No native checkout/process needed; reviewed finance demo still works | | |
| A08 configured native Talk | Authorized backend and inference; native trace and real result, or explicit unavailable state | | |
| Consumer/MCP regression | Authorized caller inventory, context hash rejection, unchanged built-in publication behavior | | |

For picker checks, follow the [model-linking guide](helios-model-picker.md).
The picker uses the caller's explicit key and rechecks model access during save.
A catalog link grants no native permission and does not import a semantic release.

A01–A08 define Release A acceptance in the [acceptance plan](amp-preparation-plan.md#cai-acceptance-matrix).
If A08 lacks a configured backend, report linked-provider readiness only.
External release import, delegated queries, and external-only package extraction remain outside this release.
Do not record A09–A11 as passed from navigation or health results.
