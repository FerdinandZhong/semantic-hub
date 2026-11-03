# Bundled AMP deployment with an independent Helios repository

> Deployment update, 3 November 2026: Helios now runs in a separate CAI project.
> The Hub AMP uses optional endpoint checks and never provisions Helios.
> Earlier bundled deployment plans below are historical.
> Use the [current operator guide](amp-operator-guide.md) and [standalone Helios guide](standalone-helios.md).

Status: implemented deployment layout, reviewed 2 November 2026; live CAI acceptance remains pending.
The pinned `external/helios` checkout is fetched during setup and owns upstream Helios documentation.
Mode-aware preparation and separate Helios API/UI provisioning are implemented.
Full built-in package extraction remains planned.
Use the [operator guide](amp-operator-guide.md) and [live test runbook](live-test-runbook.md) for current operations.

## Recommended installation modes

The default bundled mode installs Semantic Hub and a pinned Helios checkout in one CAI project.
AMP setup provisions the required CAI applications and registers their connection details.
Each application retains its own runtime environment, state, and lifecycle.

The external mode connects Hub to existing Helios applications without downloading or launching another copy.
Built-in-only mode remains available without Helios.
These modes share the same provider adapter contract.

## Repository layout

```text
semantic-hub/
├── semantic_hub/                   Hub application and provider adapters
├── apps/helios/                    Inherited built-in implementation (not yet extracted)
├── external/
│   └── helios/                     Separate Git repository, fetched at a pinned commit
├── deployment/
│   ├── provider-lock.json          Tested provider revisions and compatibility
│   └── cai/
│       ├── provision.py            Create or reuse CAI applications
│       ├── configure_providers.py  Resolve URLs and register provider settings
│       └── verify.py               Health, authentication, and capability checks
└── docs/
```

The provider lock, CAI scripts, and launchers exist. The optional built-in package remains future work.
The provider lock records the original repository URL and a tested commit.
Changing the provider lock selects a revision; it does not merge Helios source into Hub packages.
The bootstrap fetches that exact commit after CAI creates the Hub project; the Hub repository contains no Git submodule.
If that clone behavior is unsuitable, use a managed checkout at the same locked revision instead.

`provider-lock.json` records the tested revision and adapter compatibility, not a second independently selected source version.
Setup rejects an existing checkout that differs from the compatibility lock.
Do not follow moving `main` automatically during startup.

The current inherited Helios files remain until the built-in extraction phase completes.
Adding `external/helios` alone does not remove that inherited code or finish the lightweight-Hub migration.

## Runtime layout

```text
One CAI project / one AMP installation
│
├── Hub application
│   ├── Hub UI / API / consumer interface
│   ├── Hub environment and state
│   └── Provider registry
│              |
│              +-------- authenticated provider calls --------+
│                                                            |
├── Helios UI / API application(s) <---------------------------+
│   ├── Separate environment and provider state
│   └── Builder, review, publication, Talk to Your Data
│              |
└── Helios MCP application, when required
    └── Native query and warehouse access

Browser: Hub -- model-specific link --> Helios UI
```

Use the application topology supported by the selected Helios deployment revision.
If UI, API, and MCP require separate applications, provision and record each origin separately.
Do not assume their entry points, ports, or dependency environments match the Hub launcher.

The Git checkout can be shared on disk while Python imports and application state remain isolated.
Each launcher sets an explicit working directory, environment, and module path.
This matters because the inherited Hub code and Helios both contain `apps.helios` and `helios_core` packages.
Cross-importing the wrong checkout would defeat the provider boundary.

## AMP setup sequence

1. Select bundled, external, or built-in-only mode.
2. Resolve and verify the locked Helios revision when bundled mode is selected.
3. Prepare independent Hub and Helios environments and state locations.
4. Create or reuse the required CAI applications using stable deployment identifiers.
5. Start applications through CAI lifecycle controls and wait for bounded readiness checks.
6. Discover the actual UI, API, and MCP URLs from the provisioned applications.
7. Configure server-side credential references and the supported identity integration.
8. Register Helios as a Hub provider with only verified capabilities enabled.
9. Verify model-specific navigation and any enabled API operations.
10. Present the Hub landing URL and individual application readiness states.

Steps must be safe to rerun without duplicating applications or replacing provider state.
A partial failure records completed resources and allows targeted retry.
Provider registration can be updated after provisioning; the Hub can start with external capabilities disabled.
Application IDs and URLs are deployment state, not values committed into source control.

Provisioning requires an authorized CAI application-management identity.
The management client is implemented; its API compatibility and permissions still require target-environment verification.
No CAI management credentials belong in browser links or Git configuration.

## Setup versus restart

AMP installation creates and connects the applications.
A Hub restart starts only the Hub process.
A Helios restart starts only the relevant Helios process.
Neither application silently upgrades, duplicates, or restarts its peer.

The manifest uses `deployment/launchers/hub.py`, which retains the Hub child-process supervisor.
Keep that responsibility narrow and place multi-application orchestration in the deployment setup layer.
The setup orchestration must account for CAI-injected ports and application-specific launch commands.

## Provider upgrades

1. Select a new Helios revision and update the provider lock in a dedicated change.
2. Run adapter compatibility and deployment checks against that revision.
3. Update the compatibility lock after the checks pass.
4. Back up provider state and follow the provider's supported migration procedure.
5. Restart only affected provider applications and rerun capability checks.

Do not promise code-only rollback if a provider upgrade changes its database format.
Rollback must use a compatible code-and-state recovery plan.
Hub release snapshots and provider bindings remain immutable across upgrades.

## Acceptance checks

- Fresh bundled setup creates the intended application set exactly once.
- Rerunning setup does not duplicate applications or erase models.
- Hub and Helios import packages only from their assigned environments and checkouts.
- Provider origins come from deployed application metadata, without hardcoded ports or URLs.
- A Hub restart does not launch another Helios instance.
- External mode creates no Helios applications and changes no external provider state.
- Provider outage leaves Hub available and disables only affected capabilities.
- Built-in-only mode runs without checking out or installing Helios.
- The deployed identity flow preserves model permissions; ingress admission alone is insufficient.
- Release import and query execution remain disabled until their separate contract tests pass.
