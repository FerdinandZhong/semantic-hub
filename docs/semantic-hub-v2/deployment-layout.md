# Bundled AMP deployment with an independent Helios repository

Status: proposed v2 deployment layout, 23 October 2026.
This refines the installation plan; no submodule or additional CAI applications have been provisioned yet.

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
├── optional-builders/builtin/      Preserved local builder
├── external/
│   └── helios/                     Separate Git repository, pinned submodule
├── deployment/
│   ├── provider-lock.json          Tested provider revisions and compatibility
│   └── cai/
│       ├── provision.py            Create or reuse CAI applications
│       ├── configure_providers.py  Resolve URLs and register provider settings
│       └── verify.py               Health, authentication, and capability checks
└── docs/
```

These are proposed paths, not the current repository structure.
The Helios submodule points to the original repository at a tested commit.
A submodule update changes a commit pointer; it does not merge Helios source into Hub packages.
The bootstrap must explicitly initialize the checkout if the AMP clone does not initialize submodules.
If that clone behavior is unsuitable, use a managed checkout at the same locked revision instead.

`provider-lock.json` records the tested revision and adapter compatibility, not a second independently selected source version.
Setup rejects disagreement between the submodule pointer and the compatibility lock.
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
Its exact API and permissions must be verified in the target environment before implementation.
No CAI management credentials belong in browser links or Git configuration.

## Setup versus restart

AMP installation creates and connects the applications.
A Hub restart starts only the Hub process.
A Helios restart starts only the relevant Helios process.
Neither application silently upgrades, duplicates, or restarts its peer.

The current `cai_integration/start_application.py` supervises the Hub process only.
Keep that responsibility narrow and place multi-application orchestration in the deployment setup layer.
The setup orchestration must account for CAI-injected ports and application-specific launch commands.

## Provider upgrades

1. Select a new Helios revision and update the submodule pointer in a dedicated change.
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
