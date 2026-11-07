# Standalone Helios and optional Hub integration

Helios owns semantic building and native conversation in a separate CAI project.
Semantic Hub keeps its built-in builder and connects to Helios through configured HTTPS origins.

## Standalone AMP package: 5 November 2026

The sibling `../helios` checkout now contains a root `.project-metadata.yaml` on branch `feat/standalone-amp`.
This package serves the native React UI and API behind one authenticated CAI Application origin.
It does not change the Semantic Hub AMP or embed Helios into Hub.
The package is pushed at `0127f3b` on [feat/standalone-amp](https://github.com/FerdinandZhong/helios/tree/feat/standalone-amp).
Live CAI deployment and acceptance remain pending.

Read the [Helios AMP operator guide](https://github.com/FerdinandZhong/helios/blob/feat/standalone-amp/docs/amp-deployment.md).
Its local path is `../helios/docs/amp-deployment.md`, relative to the Semantic Hub repository root.

| Component | Helios repository path |
| --- | --- |
| AMP tasks | `.project-metadata.yaml` |
| Isolated Python setup and native UI build | `cai_amp/setup.py` |
| Kernel-preserving Application launcher | `cai_amp/launch.py` |
| Native UI/API dispatcher | `cai_amp/application.py` |
| Explicit native organization administrator setup | `cai_amp/admin.py` |
| Resolved Python dependencies | `cai_amp/requirements.lock` |

The package uses Standard Python 3.12 and checksum-pinned Node.js 22.23.3 for the UI build.
It includes missing native LinkML and crawler dependencies without editing upstream application code.
Setup passed locally, including dependency checks, production UI build, native imports, and disposable metadata migration.
All 13 packaging tests passed. Native browser and local identity/grant checks also passed.
The parent launcher shut down its child cleanly during the local termination check.
The upstream UI build reported 14 npm advisories, including one critical advisory; dependency upgrades remain separate work.

### Launch the new package

1. Import `FerdinandZhong/helios` and select the published `feat/standalone-amp` branch at `0127f3b`.
2. Create a separate Helios AMP project using its root manifest and Standard Python 3.12.
3. Wait for the setup job and authenticated `Helios` Application.
4. Use the explicit admin command from the Helios guide to establish native organization access.
5. Configure native data sources, inference, and MCP before testing building or chat.
6. Copy the assigned Helios Application origin into both Hub `HELIOS_UI_ORIGIN` and `HELIOS_API_ORIGIN`.
7. Restart Hub or run its connection retry, then verify caller-scoped workspace discovery.

The same origin provides UI `/healthz`, native API `/api/v1/healthz`, native documentation `/docs`, and API Swagger `/api/docs`.
Local fixture identity checks do not prove CAI SSO or cross-project authorization.
Optional document embedding dependencies remain outside the baseline installation.

## Upstream inspection

Inspected upstream: `Christopheraburns/helios`, `main`, commit `72818c4`.
Fetched again on 5 November 2026 into the sibling `../helios` repository; no newer upstream commit was available.
The local merge commit is `3a46e18`; existing local history was retained because upstream history diverged.
No upstream application-code change was introduced by this merge relative to the prior local checkout.

This upstream revision has no root `.project-metadata.yaml` AMP manifest.
It provides CAI application entry points and deployment guidance:

| Upstream path | Purpose |
| --- | --- |
| `MONOREPO.md` | Separate query, data-generation, and evaluation projects |
| `apps/helios/console/app.py` | API launcher with Workbench kernel support |
| `apps/helios/ui/app.py` | Built React UI server and runtime API URL |
| `apps/helios/console/requirements.lock` | Python deployment dependencies |
| `apps/helios/ui/package-lock.json` | UI dependency lock |
| `docs/ui-api-networking.md` | Browser identity, CORS, and verification |
| `docs/talk-to-your-data-architecture.md` | Native conversation and MCP dependencies |

The upstream revision predates the local AMP package described above.
Its separate API/UI launchers remain available as an alternative deployment.
Native chat also needs its own MCP, inference, data-source, and permission configuration.
Hub registration does not validate those features.

## Alternative: upstream two-Application setup

1. Create a CAI project from the Helios repository at the reviewed revision.
2. Select its documented Helios runtime and install its locked API dependencies.
3. Set `HELIOS_ROOT` to the repository root inside that project.
4. Use `/home/cdsw` for a root checkout, or the actual subdirectory for a nested checkout.
5. Install Node.js 20 or newer and build the UI in `apps/helios/ui`.
6. Create authenticated API and UI applications using the scripts listed below.
7. Set each application's connection settings using the actual assigned HTTPS origins.
8. Restart the applications and complete upstream's browser identity checks.

UI build commands, from the Helios repository root:

```sh
npm --prefix apps/helios/ui ci
npm --prefix apps/helios/ui run build
```

| Application | Script relative to repository root | Connection setting |
| --- | --- | --- |
| Helios API | `apps/helios/console/app.py` | `HELIOS_UI_ORIGINS=https://<actual-ui-host>` |
| Helios UI | `apps/helios/ui/app.py` | `HELIOS_API_URL=https://<actual-api-host>` |

Keep both applications authenticated. Do not enable `HELIOS_DEV` or `HELIOS_DEV_USER` in CAI.
Use distinct stable application subdomains and exact origins, without paths.
Keep the native metadata database and artifact directories in the Helios project.
The upstream launchers use `HELIOS_ROOT` for repository and artifact defaults; review its state configuration before deployment.
Use upstream's bootstrap and grants procedure to establish authorized organizations and models.

## Connect the Hub

1. Set Hub `HELIOS_UI_ORIGIN` to the running UI origin.
2. Set Hub `HELIOS_API_ORIGIN` to the running API origin.
3. Configure `HELIOS_HEALTH_API_KEY` if CAI ingress requires authenticated server health checks.
4. Restart the Hub with `SEMANTIC_HUB_PROVIDER_MODE=auto`.
5. Confirm `Optional Helios` reports `connected` in the application log.
6. Open the workspace flow and choose External Helios.
7. Supply your caller credential when requested and select an authorized workspace.

```text
Helios project:  UI <----> API ----> native sources / models
                   ^       ^
                   |       | health and authorized discovery
Hub project:    browser <-- Hub ----> built-in builder / Hub state
```

An unavailable Helios service does not block Hub startup.
On a fresh installation, failed checks leave only the built-in builder registered.
Existing links remain available for recovery; the Hub does not transfer their ownership to another builder.

## Remaining live checks

Verify the separate Helios project's API/UI health and browser identity on the target CAI release.
Verify caller-scoped workspace discovery across the two projects.
Verify native building and chat independently inside Helios.
The previous Hub project-copy failure occurs before setup; its root cause is still unconfirmed.
