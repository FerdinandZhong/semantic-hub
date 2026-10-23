# Local smoke test plan

Status: test specification for the v2 implementation.
The v2 harness and tests listed as proposed do not exist yet.
Existing regression commands below can run now.

[Implementation plan](implementation-plan.md) · [AMP preparation](amp-preparation-plan.md)

## Test layers

```text
Existing regression tests
          |
Fake provider contract tests
          |
Real pinned Helios: separate processes + browser navigation
          |
Optional configured-model / query checks
          |
CAI acceptance: ingress + identity + provisioning + persistence
```

Local tests establish behavior and process isolation.
They do not certify CAI ingress, application-management permissions, or production data entitlements.

## Fixtures and isolation

Use a temporary directory for each run, with separate Hub and Helios state roots.
Record the Hub SHA, submodule SHA, adapter version, interpreter versions, and UI build identity.
Use loopback addresses and reserved ports; fail clearly if an explicit port is already occupied.
Never stop an unrelated listener to claim a port.

Keep the unchanged finance sample as the Built-in regression fixture.
Use a tiny synthetic external model with a different model ID and distinctive expected result.
This difference detects accidental routing to Built-in data.
Provide a draft-only external model, two published revisions, and two test users with different grants.
Use no production rows or copied credentials.

| Lane | Service dependencies | What it proves |
| --- | --- | --- |
| Offline | Existing fixtures and fake provider | Contracts, deterministic routing, error handling, migration |
| Real provider | Pinned Helios UI/API and native state | Imports, startup, native routes, compatibility at that revision |
| Configured Talk | Real provider plus approved LLM and test query backend | Actual native conversation behavior and provenance |
| CAI | Disposable deployed applications and test identities | Ingress, real identity propagation, managed lifecycle |

A local development identity must bind to loopback and remain disabled in CAI mode.
A fake conversation response cannot satisfy the configured Talk lane.

## Check matrix

| ID | Scenario and action | Required result | Evidence |
| --- | --- | --- | --- |
| L00 | Run current Built-in and AMP baseline tests | Existing request, publication, persistence, and supervisor contracts pass | Pytest output and SHA |
| L01 | Initialize provider checkout and compare lock; try a mismatch | Exact revision passes; mismatch stops setup before application launch | SHA report and failure output |
| L02 | Start Hub and Helios in separate environments | Imports resolve to the assigned checkout; state and ports do not overlap | Module `__file__`, interpreter, PID, and state-path report |
| L03 | Apply provider migration twice to a copy of existing state | No duplicate records; model IDs and published hashes stay unchanged | Before/after manifest and migration result |
| L04 | Open Built-in and Helios from Hub in a browser | Correct native model context; URL encoding works; no credential in URL | Screenshots and sanitized navigation log |
| L05 | Open native Talk on the real provider | Page opens with correct model; unavailable model/backend shows an honest configuration state | Screenshot and native model ID |
| L06 | Stop Helios, then retry its action; restart Hub | Hub remains available; no local execution fallback or duplicate Helios launch | PID inventory, request result, health states |
| L07 | Retry setup after an interrupted stage | Completed resources are reused; stored models and keys survive | Resource IDs and state hashes |
| L08 | Exercise external and built-in-only modes | External mode starts no provider process; built-in-only mode requires no external checkout | Process/checkout inventory |
| L09 | Import published, draft-only, duplicate, and tampered releases | Only valid published content is accepted; reimport is idempotent; tampering fails | Native and Hub hashes, error codes |
| L10 | Publish a later revision and revoke access to an earlier import | Earlier bytes stay immutable; revoked content is not exposed to the caller | Release manifests and authorization assertions |
| L11 | Execute an exact external revision as two users; request a missing revision | Correct user scope and external result; missing revision fails; no latest/sample substitution | Provider trace, executed revision, result assertions |
| L12 | Start an external-only package, then the optional Built-in package | Hub-core imports no builder stack; Built-in still works when installed | Installed-package and import reports |

L05 verifies navigation only when the LLM/backend is unavailable.
Before advertising working native Talk, add a successful configured Talk trace to L05 evidence.
L09–L11 require real provider contract verification as well as fake-provider negative cases.

## Additional negative cases

Test disallowed provider origins, unexpected redirects, expired authentication, malformed release payloads, and request timeouts.
Reject unsafe artifact paths, unsupported format versions, and artifacts exceeding configured size limits.
Ensure model names and cached evidence do not leak after authorization denial.
Check that provider responses cannot add capabilities outside the configured and verified capability set.

## Existing commands

Run from the repository root using the existing environment:

```sh
.venv-semantic-hub/bin/python -m pytest \
  apps/helios/tests/test_semantic_hub_consumer.py \
  apps/helios/tests/test_retrieval_service.py \
  apps/helios/tests/test_retrieval_index.py -q

.venv-semantic-hub/bin/python -m pytest tests/amp/test_amp.py -q

git diff --check
```

For an optional existing Hub-only browser rehearsal, use a fresh temporary state directory:

```sh
smoke_state=$(mktemp -d /tmp/semantic-hub-smoke.XXXXXX)
SEMANTIC_HUB_STATE_DIR="$smoke_state" \
  .venv-semantic-hub/bin/python -m cai_integration.application --local --port 8099
```

This command starts the current Hub only, not the planned multi-application harness.
Run it in a dedicated terminal and stop its own process after inspection.
Do not reuse this no-authentication local mode on a remotely accessible interface.

## Proposed harness behavior

Implement `deployment/local/run.py` in I4 with explicit `start`, `check`, and `stop` actions.
It should accept installation mode, output directory, provider lock, and a test-lane selection.
The interface itself requires implementation; no command here implies it already exists.

1. Verify code revisions and installed dependencies.
2. Allocate isolated state and reserve service ports.
3. Start selected processes and record their ownership.
4. Poll bounded readiness checks instead of waiting a fixed sleep duration.
5. Run the selected API and browser cases.
6. Write machine-readable and human-readable evidence.
7. Stop only owned processes and report any cleanup failure.

Use proposed readiness budgets of 120 seconds for local services and 10 seconds for individual HTTP probes.
Model-dependent checks use explicit provider timeouts and a separate configurable overall budget.
Persist logs on failure and exit nonzero if a required case fails or cannot run.
Do not retry indefinitely or hide the first failure behind a later success.

## Evidence format

Store results under a unique run directory outside tracked application state.
Each record contains test ID, lane, status, revisions, duration, expected outcome, actual outcome, and artifact paths.
Allowed statuses are `passed`, `failed`, `blocked`, and `not_run`.
A prerequisite failure marks dependent cases `blocked`, not `passed`.

```text
<run-directory>/
├── summary.json
├── summary.md
├── versions.json
├── processes.json
├── pytest/
├── requests/       Sanitized request/response evidence
├── screenshots/
└── logs/           Sanitized application logs
```

The existing 38-test consumer/retrieval result is baseline evidence only.
No v2 test is considered executed until its implementation and current-artifact report exist.

## Exit and handoff

Release A requires L00–L08 and the corresponding CAI checks.
Release B adds L09–L10; Release C adds L11; Release D adds L12.
Record optional service checks separately from required release acceptance.
Attach the local evidence manifest to the AMP rehearsal so deployment uses the same tested revisions.

## Planning-time verification record

On 23 October 2026, the existing AMP suite passed: **11 tests in 18.77 seconds**.
The earlier consumer/retrieval baseline passed **38 tests in 28.34 seconds**; it was not rerun for these documentation-only changes.
Plan links, work-package IDs, test-case IDs, referenced existing test paths, and whitespace checks passed.
All new v2 test cases remain `not_run` until the corresponding code exists.
