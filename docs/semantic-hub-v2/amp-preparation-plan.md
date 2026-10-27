# AMP preparation and CAI acceptance plan

Status: preparation and provisioning implementation added, 27 October 2026; live CAI acceptance remains pending.
See the [operator guide](amp-operator-guide.md) for the implemented configuration and recovery procedure.
This plan does not itself run application provisioning.
Use the accepted layout and implementation milestones as the source of deployment scope.

[Implementation plan](implementation-plan.md) · [Local smoke tests](local-smoke-test-plan.md) · [Deployment layout](deployment-layout.md)

## Current baseline and supported specification

The current `.project-metadata.yaml` runs preparation and provisioning jobs before starting one authenticated Hub application.
The provisioning job creates or reuses native Helios applications only in bundled mode.
The existing launcher supervises an isolated Python child while preserving the CAI kernel.
Keep those isolation and lifecycle properties in the v2 launchers.

AMP project metadata supports an ordered task sequence after project import.
The manifest belongs at the project root. See the [Cloudera AMP project specification](https://docs.cloudera.com/machine-learning/cloud/applied-ml-prototypes/topics/ml-amp-project-spec.html).

Do not assume conditional tasks, automatic submodule initialization, or ready-to-use application URLs from task ordering alone.
Verify those behaviors against the target CAI version before selecting the exact orchestration implementation.

## Preparation deliverables

| Deliverable | Proposed location | Acceptance |
| --- | --- | --- |
| Pinned provider checkout | `.gitmodules`, `external/helios`, `deployment/provider-lock.json` | Checkout matches tested revision; mode without Helios skips it |
| Environment preparation | `deployment/cai/prepare.py` | Independent dependency environments and persistent state roots |
| Provisioning client | `deployment/cai/provision.py` | Uses verified CAI API; create/reuse is idempotent |
| Application launchers | `deployment/launchers/` | Correct working directory, imports, injected port, and kernel supervision |
| Provider registration | `deployment/cai/configure_providers.py` | Actual origins and protected credential references; verified capabilities only |
| Deployment verification | `deployment/cai/verify.py` | Readiness, identity, navigation, and persistence evidence |
| AMP metadata | `.project-metadata.yaml`, `METADATA.yaml` | Describes the implemented release scope and valid entry points |
| Operator guide | Versioned deployment documentation | Setup, retry, upgrade, recovery, and evidence locations |

The preparation, provisioning, launcher, registration, and verification files above now exist.
The root manifest references implemented scripts. Live deployment evidence is still required.

## Installation modes

| Mode | Resources to create | Required configuration |
| --- | --- | --- |
| `bundled` | Hub plus the required Helios application set | Locked revision, compatible runtimes, application-management permission |
| `external` | Hub only | Existing provider UI/API origins; optional MCP URL and approved authentication |
| `builtin_only` | Hub with Built-in | Current source packs and persistent Hub state |

Implemented settings include `SEMANTIC_HUB_PROVIDER_MODE`, `HELIOS_UI_ORIGIN`, and `HELIOS_API_ORIGIN`.
`HELIOS_MCP_URL` remains a future setting; native MCP deployment is outside this increment.
Keep secret values out of committed manifest defaults and logs.

## Deployment state and filesystem

```text
Project checkout
├── external/helios/              Locked provider code
├── .venv-semantic-hub/           Hub dependencies
└── .venv-helios/                 Provider dependencies

Persistent state
├── semantic-hub/                Hub records, releases, credentials, Built-in state
├── helios/                      Provider records and artifacts
└── deployment/                  Resource IDs, stages, compatibility and readiness
```

Separate state paths prevent accidental shared-database writes.
They are operational isolation, not a security boundary against users with access to the same project filesystem.
Use separate CAI projects if stronger filesystem or administrative isolation is required.
Never let the Hub adapter read provider databases directly.

## Provisioning sequence

```text
Preflight → prepare code and environments → create/reuse application records
                                                    |
                                       Start required Helios services
                                                    |
                                       Start Hub with provider pending
                                                    |
                                 Discover URLs → register → verify
                                                    |
                                      Ready or explicit degraded state
```

1. Verify the requested mode, repository revisions, network access, runtimes, and project quotas.
2. Initialize the pinned provider checkout only when bundled mode requires it.
3. Install dependencies and verify module origins in each environment.
4. Validate state directories and preserve existing credentials and published artifacts.
5. Create or reuse each required application using a persisted deployment identity.
6. Start provider services in their verified dependency order.
7. Start Hub without requiring a successful provider registration to bind its own port.
8. Obtain assigned origins from CAI application records, not guessed subdomains.
9. Register the provider and run capability-specific health and authorization probes.
10. Save a deployment report with links, readiness states, and next actions.

The exact Helios UI/API/MCP process topology is an I1 inspection output.
Do not promise a fixed application count before confirming the pinned provider launcher requirements.

## Choose one owner for resource creation

Prefer declarative AMP tasks for a fixed verified application topology.
Use a bounded provisioning job where installation modes require conditional creation or discovery.
Do not let both mechanisms create the same application.

The first implementation spike must inspect the available CAI management API and its authentication requirements.
Record request schemas, application identifiers, lifecycle states, and URL fields before implementing the client.
Do not invent SDK methods or treat the current Hub ingress key as proof of management authority.

If the platform cannot express the selected modes in one manifest, choose a documented installer configuration or separate generated manifests.
Do not create empty Helios processes merely to satisfy an unconditional task list.

## Idempotency and partial failure

Persist a deployment ID, project ID, mode, desired revision, and application IDs.
An application name alone is insufficient ownership evidence.
Before creating a resource, reconcile the recorded ID with platform state.
Reject conflicting ownership instead of adopting or deleting an unrelated application.

Use bounded polling with proposed budgets of 10 minutes per application readiness stage and 30 minutes for initial environment setup.
Adjust budgets using measured platform behavior; report timeout as a failure.
A retry resumes incomplete stages and never resets model state.

If Helios fails, preserve the running Hub and mark that provider unavailable.
A Hub restart must not repeat provisioning.
Cleanup targets only resources created by this deployment and never removes persistent state automatically.

## Runtime and credential preparation

Retain the current Hub allocation of 2 CPUs, 8 GB RAM, and no GPU as the initial baseline.
Measure Helios allocations from the pinned deployment and local rehearsal before declaring the full AMP quota requirement.
Document total concurrent application resources and setup-job peaks.
Do not assume every provider service needs the same allocation as Hub.

Pin Python and frontend build requirements from the inspected revision.
The currently inspected Helios UI declares Node.js 20 or newer; record the selected build version and lockfile identity.
Prefer building static assets during setup instead of using a development server in CAI.

Keep application-management credentials separate from provider API credentials and end-user delegation.
Preserve each application's persistent encryption keys across restarts.
Keep ingress authentication enabled for every exposed application.
A provider may require additional bearer or signed-assertion checks behind CAI ingress.
Verify both layers rather than assuming one key satisfies all of them.

## CAI acceptance matrix

| ID | Check | Pass condition |
| --- | --- | --- |
| A01 | Fresh bundled install | Expected applications reach readiness at locked revisions; actual origins are registered |
| A02 | Rerun after success and after a partial failure | Application IDs are reused; no duplicates or state loss |
| A03 | Browser navigation and authentication | Hub opens correct native Helios model; unauthenticated access is denied or redirected to login without data leakage |
| A04 | Restart Hub, then provider separately | Each restart affects only its application; releases and credentials persist |
| A05 | Provider outage | Hub remains available; external actions fail explicitly; Built-in is not substituted |
| A06 | External mode | Only Hub is provisioned; existing provider applications are not modified |
| A07 | Built-in-only mode | No Helios checkout/process is required; existing finance demo still works |
| A08 | Configured native Talk and operating evidence | Authorized test question succeeds with real provider trace, or capability remains explicitly unavailable |
| A09 | Published release import | Real provider export, publication evidence, exact hashes, and caller permissions verified |
| A10 | Delegated query | Two identities retain different entitlements; exact revision and source binding verified end to end |
| A11 | External-only package | Hub starts without installed builder runtime and can operate its verified external capabilities |

A01–A08 establish Release A readiness.
If A08 cannot exercise a configured backend, report only linked-provider readiness and do not advertise working query execution.
A09 is required for Release B, A10 for Release C, and A11 for Release D.
Use a disposable test project and synthetic data for the first deployment rehearsal.

## Upgrade and recovery rehearsal

1. Record current application IDs, provider revision, environment locks, and state backup references.
2. Check whether the provider upgrade requires state migrations.
3. Test the new provider revision and adapter contract before changing the active deployment.
4. Apply the approved upgrade and verify readiness and model access.
5. Rehearse restoration using compatible code and state when rollback is required.

Keep rollback evidence separate from basic restart evidence.
A database migration may prevent a simple code-pointer rollback.
Do not delete the previous known-good revision or backup until acceptance completes.

## Inputs needed before live deployment

The live rehearsal needs a target workspace/project, approved management identity, available runtime identifiers, quotas, and test users.
Configured Talk also needs an approved LLM endpoint and an authorized test query backend.
These values are not required to complete the implementation and test plans.
Do not insert credentials or assume live deployment approval from acceptance of this planning document.
