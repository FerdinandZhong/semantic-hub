# AMP operator guide

Updated 3 November 2026. Semantic Hub and Helios run in separate CAI projects.
The Hub AMP never clones, installs, starts, or upgrades Helios.

```text
Hub AMP -> Hub setup -> Hub application -> Built-in builder
                              |
                       optional health checks
                              |
                       Helios API + UI
                       (separate project)
```

## Install the Hub

1. Import the Hub repository and select `fix/amp-provider-bootstrap` for this change.
2. Use the root `.project-metadata.yaml` manifest.
3. Select the Standard Python 3.11 runtime.
4. Retain the default persistent `SEMANTIC_HUB_STATE_DIR`.
5. Leave `SEMANTIC_HUB_PROVIDER_MODE=auto`.
6. Leave both Helios origins empty to start with only the built-in builder.
7. Wait for the setup job and Hub application.
8. Open the authenticated Hub application URL.

The manifest has three tasks: create setup job, run setup job, and start Hub.
Setup runs `cai_integration/setup_environment.py`.
The application runs `deployment/launchers/hub.py`.
It uses 2 CPUs and 8 GB memory. No GPU, Node.js, or application-management key is required for Hub setup.
Package installation still requires access to the configured Python package registry.

## Connect an existing Helios project

Follow [the standalone Helios guide](standalone-helios.md) first.

| Setting | Purpose |
| --- | --- |
| `SEMANTIC_HUB_PROVIDER_MODE=auto` | Check explicitly configured endpoints at each Hub startup |
| `HELIOS_UI_ORIGIN` | Exact HTTPS origin of the Helios UI |
| `HELIOS_API_ORIGIN` | Exact HTTPS origin of the Helios API |
| `HELIOS_HEALTH_API_KEY` | Optional secret for authenticated health checks through CAI ingress |
| `SEMANTIC_HUB_PROVIDER_MODE=builtin_only` | Skip automatic Helios registration |

Set both origins in the Hub application's project environment, then restart the Hub.
The health key must have access to the separate Helios project.
Configure it as a secret environment value; do not put it in Git or URLs.
The Hub never substitutes its inherited `CDSW_APIV2_KEY` for this key.
Workspace discovery still uses the calling user's credential and native Helios permissions.
The health key does not authorize workspace access.

The Hub checks UI `/healthz` and API `/api/v1/healthz`.
Each check has a five-second deadline. TLS verification remains enabled; redirects and login pages fail readiness.
Both checks must pass before registration as `helios-external`.
Registration adds navigation capabilities, not external releases or delegated query execution.
Select the provider in the workspace flow to create or link an authorized native workspace.

Missing configuration, failed authentication, or an unavailable service leaves a fresh Hub with only its built-in builder.
The application log records a credential-free `Optional Helios` result.
This is a startup check, not continuous discovery or a health monitor.
A Helios deployment started later requires a Hub restart or an explicit retry:

```sh
.venv-semantic-hub/bin/python deployment/cai/connect_external.py --retry
```

Existing provider records and workspace links survive outages and `builtin_only` restarts.
They are not deleted, converted, or silently redirected to the built-in builder.
A conflicting `helios-external` origin returns `provider_conflict`; register a different provider ID through the administrative flow.

## State and compatibility

Back up `SEMANTIC_HUB_STATE_DIR`, including the model encryption key, before upgrades.
Helios owns its own state in its separate project.
The optional local launcher and legacy bundled scripts remain for compatibility.
Neither participates in the current AMP manifest. Legacy `external` mode also uses the optional startup health check.
Do not select legacy `bundled` mode for a new AMP deployment.

## Verification status

Local AMP and provider tests cover startup wiring, health failures, timeout, repeat registration, and credential isolation.
The independent Hub launched successfully in CAI and last restarted at commit `cc4890e` on 3 November 2026.
Authenticated health, Swagger, OpenAPI, inventory, and saved-metric checks passed.
The finance query returned **SGD 686,572.96**.
The latest response included its semantic canvas and 6/6 answer checks. Seven updated UI assets matched the reviewed code.
Separate-project Helios authorization, browser identity, live free-text inference, and complete persistence checks remain required.
See the [deployment evidence and current status](project-status.md).
Use [the live-test runbook](live-test-runbook.md).
The reported project-copy exit status 24 remains unconfirmed; removing Helios provisioning cannot prove its cause.
