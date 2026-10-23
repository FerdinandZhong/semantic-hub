# Semantic Hub v2 implementation plan

Status: planned work following acceptance of the repository layout.
The plan does not claim that provider integration, the submodule, or multi-application deployment already exists.

[Architecture](README.md) · [Deployment layout](deployment-layout.md) · [Local smoke tests](local-smoke-test-plan.md) · [AMP preparation](amp-preparation-plan.md)

## Delivery boundaries

Deliver a useful linked-provider release before implementing release exchange or delegated execution.
The complete target still includes an independently deployable Hub and optional Built-in package.
Do not describe an early link integration as completion of the dependency extraction.

```text
I0 Baseline → I1 Checkout and isolation → I2 Provider registry
                                              |
                                     I3 Builder navigation
                                      /              \
                           I4 Local rehearsal     I5 AMP packaging
                                      \              /
                                       Release A
                                           |
                           I6 Release import → Release B
                                           |
                           I7 Delegated query → Release C
                                           |
                           I8 Package extraction → Release D
```

| Release | User-visible scope | Required evidence |
| --- | --- | --- |
| A: linked providers | Built-in remains usable; bundled or existing Helios opens for building and Talk | L00–L08 local checks, A01–A08 CAI checks |
| B: accepted external context | Published Helios releases can enter the Hub context catalog | L09–L10, A09; verified provider export contract |
| C: delegated execution | Authorized queries execute against an exact external revision | L11, A10; verified identity and revision contract |
| D: lightweight packaging | External-only Hub starts without the inherited builder stack | L12, A11; dependency inventory and built-in regression |

Local checks are defined in the smoke plan. CAI checks are defined in the AMP plan.
Native Talk may require an LLM and a configured warehouse even when provider navigation works.
Release A must report those dependencies explicitly rather than inventing a sample answer.

## Work packages

### I0 — Preserve and measure the baseline

1. Retain the cleanup commits and accepted design on `design/semantic-hub-v2-providers`.
2. Record the Hub SHA and inspected Helios SHA in an implementation evidence report.
3. Capture current tests, existing publication hashes, and public MCP request shapes.
4. Use disposable state for local tests; leave live project state untouched.

Existing evidence: 38 consumer/retrieval tests passed during design preparation.
Refresh affected baseline suites when implementation changes their code or dependencies.
Do not refresh every unrelated suite after documentation-only changes.

**Exit:** baseline evidence identifies the tested artifact and migration invariants.

### I1 — Add the independent Helios checkout and isolated launchers

Partial progress: the pinned submodule and documentation ownership cleanup are complete.
The compatibility lock, isolated provider environment, and launchers remain to be implemented.

1. Add `external/helios` as a submodule at the verified upstream revision.
2. Add `deployment/provider-lock.json` with revision, supported adapter version, and runtime requirements.
3. Add checkout verification that rejects missing, dirty, or mismatched provider revisions during reproducible setup.
4. Create separate Python environments and state roots for Hub and Helios.
5. Inspect upstream entry points and build its UI from its own dependency lock.
6. Add provider launch wrappers outside the upstream checkout.
7. Verify import origins for `apps.helios` and `helios_core` in both processes.

Proposed files: `.gitmodules`, `deployment/provider-lock.json`, `deployment/checkout.py`, and `deployment/launchers/`.
Do not add wrapper patches inside Helios merely to simplify Hub imports.
If provider functionality needs a patch, submit a provider change or use a separately versioned provider-owned bridge.

**Exit:** a pinned provider process starts from its own checkout without importing Hub's inherited packages.

### I2 — Introduce provider records and the Built-in adapter

1. Create provider registration, project assignment, and capability models under `semantic_hub/core/` and `semantic_hub/contracts/`.
2. Store provider identity, allowed origins, credential references, health, and compatibility status.
3. Add an additive migration that assigns existing projects to Built-in.
4. Preserve existing model IDs, release bytes, hashes, and v1 consumer behavior.
5. Wrap the existing `DemoHub` through `semantic_hub/providers/builtin/`.
6. Add a Helios adapter with navigation capabilities first.

Use the current persistence engine for the initial migration behind a repository interface.
PostgreSQL remains the production target; an engine migration is a separate implementation decision.

**Exit:** existing models remain unchanged; external models cannot enter local sample execution by accident.

### I3 — Add provider selection and native navigation

1. Add provider selection when creating a project and show the selected provider on existing projects.
2. Bind Helios projects to verified native organization and model IDs.
3. Generate allowed builder and Talk URLs with encoded identifiers.
4. Display linked, unavailable, and unsupported states distinctly.
5. Keep Built-in editing and query actions behind the Built-in adapter.
6. Add provider connection settings without exposing secrets to browser responses.

Existing Helios route families include `/models`, `/canvas`, `/model-overview`, and `/talk`.
Use native `organization` and `model` parameters.
Do not assume callback parameters or historical-release selectors exist.
Default-provider changes affect new projects; outages never change an existing project's provider.

**Exit:** browser smoke evidence demonstrates both builders and correct failure behavior.

### I4 — Build the local rehearsal harness

1. Add `deployment/local/run.py` to start selected services on reserved loopback ports.
2. Track child processes and terminate only test-owned processes on teardown.
3. Add a deterministic fake provider for error and contract cases.
4. Add real pinned-Helios navigation checks with its own UI and API processes.
5. Add an optional configured-model test lane for native Talk.
6. Produce one machine-readable report with per-check status, revisions, logs, and screenshots.

Proposed test paths: `tests/providers/`, `tests/smoke/`, and `tests/fixtures/providers/`.
A fake provider cannot prove Helios compatibility or CAI authentication.

**Exit:** local L00–L08 checks pass for Release A, with live-service prerequisites identified separately.

### I5 — Prepare repeatable AMP provisioning

1. Extend `.project-metadata.yaml` and update `METADATA.yaml` for the selected release scope.
2. Implement preparation, provisioning, provider registration, and readiness checks as separate setup responsibilities.
3. Support `bundled`, `external`, and `builtin_only` modes.
4. Verify the target CAI application-management interface before coding its client.
5. Persist application IDs and setup checkpoints for safe retry.
6. Preserve the kernel supervisor pattern in each required launcher.
7. Update `tests/amp/test_amp.py` to cover the new task graph and modes.

The current test asserts exactly three tasks: create setup job, run setup job, and start Hub.
Replace that assumption with mode-specific lifecycle and dependency assertions.
Keep authentication, persistent-state, import-isolation, and supervisor checks.

**Exit:** AMP preparation artifacts pass local validation; a disposable CAI deployment passes A01–A08 before Release A acceptance.

### I6 — Import immutable published releases

1. Implement or negotiate a provider-owned export contract for exact published revisions.
2. Add release envelopes, immutable artifact storage, and a publication acceptance policy.
3. Verify original bytes, native digest, source bindings, and publication evidence.
4. Make repeated imports idempotent and reject changed bytes under the same revision.
5. Exclude draft fallback content from Hub discovery.
6. Report context-only capability where execution is unsupported.

Proposed code: `semantic_hub/core/releases.py`, `semantic_hub/contracts/releases.py`, and the Helios export adapter.
Upstream `/semantic` currently returns identifiers; it cannot substitute for this export contract.

**Exit:** Release B passes import, provenance, authorization, and revocation checks.

### I7 — Delegate queries with verified identity and revision

1. Prove the supported end-user identity path through Hub, provider, and data engine.
2. Bind each request to an accepted native revision and source configuration.
3. Preserve provider authorization and result limits.
4. Reject unavailable revisions instead of using latest.
5. Separate native conversational execution from prepare/execute contracts.
6. Return result provenance and a cross-application trace reference.

**Exit:** Release C passes two-user access tests and exact-revision execution tests on the target environment.
A shared application credential does not satisfy this acceptance condition by itself.

### I8 — Extract the inherited builder stack

1. Move built-in authoring, document processing, and local query code into the optional package boundary.
2. Remove Hub-core imports of the Helios console, crawler, and agent runtime.
3. Split dependency locks for Hub, Built-in, and external Helios.
4. Preserve migration adapters for current built-in state.
5. Test an external-only installation and a Built-in installation independently.
6. Add a second provider with a narrower capability set to validate the abstraction.

**Exit:** Release D starts Hub without builder dependencies and preserves existing Built-in behavior when installed.

## Commit and review sequence

Use one reviewable commit or PR per work package, splitting larger packages by dependency boundary.
Include code, migration, relevant tests, and evidence together.
Keep provider functionality changes separate from Hub adapter changes.
No phase upgrades the Helios revision implicitly.

## Scope exclusions for Release A

Release A does not add universal model editing, generic SQL execution, or automatic cross-provider model migration.
It does not replace SQLite with PostgreSQL or duplicate Helios chat inside the Hub UI.
It does not claim export or query compatibility from successful navigation alone.

## Completion rule

A work package completes when its artifacts exist and its listed acceptance checks pass against those artifacts.
A skipped required test is not a pass.
A release can ship only with its verified capability subset clearly presented to users.
