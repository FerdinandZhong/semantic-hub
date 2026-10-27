# Semantic Hub v2 AMP operator guide

Status: implementation for local verification; live multi-application CAI acceptance is pending.
This release links Helios workspaces. It does not import Helios releases or delegate Hub MCP queries to Helios.

## Deployment sequence

```text
AMP import
  → Preparation job: Hub environment + optional pinned Helios environment/UI build
  → Provisioning job: create/reuse native API and UI → register provider origins
  → AMP task: start authenticated Hub application
  → Operator: endpoint checks → browser and identity acceptance
```

The provisioning job owns Helios applications. The AMP manifest owns the Hub application.
Application startup never provisions resources or installs packages.
Rerun the preparation or provisioning jobs for recovery; importing the whole AMP again is not an idempotent upgrade procedure.

## Select a mode

| `SEMANTIC_HUB_PROVIDER_MODE` | Preparation and provisioning |
| --- | --- |
| `bundled` (default) | Prepare the locked native checkout; create/reuse separate Helios API and UI applications |
| `external` | Prepare Hub; register supplied Helios UI/API origins; do not create or change external applications |
| `builtin_only` | Prepare Hub; skip native checkout, native dependencies, and provider registration |

The built-in builder remains installed in every mode. External-only dependency extraction is future work.
Changing modes does not delete applications or existing provider records.

## Prerequisites

1. Use a Standard Python 3.11 runtime and persistent project storage.
2. For bundled mode, provide Node.js 20 or newer, npm, Git access, and package registry access.
3. Set `SEMANTIC_HUB_RUNTIME_IDENTIFIER` to the exact runtime identifier for the native applications.
4. Supply `CDSW_API_URL`, `CDSW_PROJECT_ID`, and `CDSW_APIV2_KEY` through the CAI job environment for bundled provisioning.
5. Use a management identity authorized to list, create, inspect, and restart applications in that project.
6. Verify that CAI ingress authenticates users and replaces client-supplied identity headers before enabling native Helios.
7. Set `HELIOS_CAI_PROXY_AUTH_CONFIRMED=1` only after that verification.

The proxy setting records an operator assertion. It does not test authentication.
Native Helios trusts ingress identity headers and applies its own principal and model permissions.
The launchers reject development identity settings. Setup creates no users, model grants, source data, or published releases.

Management credentials are not written into deployment reports or application payloads by the provisioner.
Project-level CAI credentials can still be inherited by workloads according to platform policy.
Applications retain `bypass_authentication: false`.

Initial bundled allocations total 6 CPUs and 24 GB memory: 2 CPUs and 8 GB per application.
The preparation job requests 2 CPUs/8 GB; provisioning requests 1 CPU/2 GB and overlaps native application startup.
These are initial allocations, not measured capacity recommendations.

## Application origins

External mode requires `HELIOS_UI_ORIGIN` and `HELIOS_API_ORIGIN`.
Use exact HTTPS origins without paths, credentials, query strings, or fragments.

Bundled provisioning uses URLs returned by CAI when available.
Some API versions expose only subdomains. The provisioner does not infer a hostname from those values.
It creates both application records and retains their IDs before reporting missing URLs.

1. Copy each assigned application URL from Workbench.
2. Set `HELIOS_UI_ORIGIN` and `HELIOS_API_ORIGIN` in the provisioning job environment.
3. Rerun the provisioning job.

Native launchers wait a bounded time for both origins in the deployment checkpoint.
The API uses the UI origin for CORS. The UI uses the API origin for browser requests.
If an application stopped while waiting, retrying provisioning restarts the owned application.
Existing records with conflicting ownership, authentication, runtime, or launcher configuration are rejected.

## Persistent files

| Setting | Default relative to the Hub state directory |
| --- | --- |
| `SEMANTIC_HUB_STATE_DIR` | `/home/cdsw/state/semantic-hub` from the manifest |
| `HELIOS_STATE_DIR` | Sibling `helios/` directory |
| `SEMANTIC_HUB_DEPLOYMENT_STATE_DIR` | Sibling `deployment/` directory |
| `HELIOS_ARTIFACT_DIR` | `deployment/helios-ui/` |

Keep state locations stable across job reruns and application restarts.
Hub and Helios use separate environments and databases.
The native UI builds from a disposable copy, preserving the pinned tracked checkout.
The deployment directory holds preparation evidence, provisioned application IDs, and verification output.
Do not delete `provision.json` to resolve an error; it identifies the owned applications.
Back up both state directories and encryption keys before an upgrade.

The checkpoint pins the provider revision and runtime identifier.
A conflicting revision is rejected. Automated provider upgrades and migration rollback are outside this increment.
Provider origins cannot silently change under an existing registry ID.

## Verification

Local verification on 27 October 2026 passed 73 AMP and provider tests.
Lint and whitespace checks passed for the new deployment code.
Actual CLI checks confirmed built-in-only skip behavior and repeatable external registration without management credentials.
The native bootstrap loaded the pinned Helios API in its isolated environment and passed an in-process metadata health check.
These checks used disposable local state. No CAI applications were created.

```bash
.venv-semantic-hub/bin/python -m pytest tests/amp tests/providers -q
```

After Hub starts, run this command from the project root with an authorized caller key in the environment:

```bash
python deployment/cai/verify.py --hub-origin https://YOUR-HUB-APPLICATION
```

The verifier checks health response shapes and rejects redirects, including login redirects.
It saves `verification.json` without credentials.
It always reports full CAI acceptance as pending; endpoint reachability alone is insufficient.

Complete the [A01–A08 acceptance checks](amp-preparation-plan.md#cai-acceptance-matrix) in a disposable CAI project.
Verify authenticated browser navigation, CORS preflight, identity-header stripping, and native model permissions.
Also check independent restarts, persistent credentials, retry recovery, and provider outages.
Configure a permitted backend and inference endpoint before claiming native Talk works.
Optional document embeddings/vector evidence dependencies remain omitted from the pinned provider preparation.

## References

- [AMP project specification](https://docs.cloudera.com/machine-learning/cloud/applied-ml-prototypes/topics/ml-amp-project-spec.html)
- [CAI API v2 REST schema](https://docs.cloudera.com/machine-learning/1.5.5/rest-api-reference/index.html)
- [CAI API v2 usage examples](https://docs.cloudera.com/machine-learning/latest/api/topics/ml-apiv2-usage-examples.html)

Target CAI API compatibility still requires live verification. Offline fixtures do not certify a target deployment.
