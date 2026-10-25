# Semantic Hub v2: independent Hub, pluggable builders

Status: local linked-provider preview in implementation, 25 October 2026.
The branch now includes the provider registry, workspace UI, and isolated local launcher.
See [local preview and implementation evidence](local-preview.md) for tested scope and launch commands.
Multi-application CAI deployment, external release import, and delegated queries remain later work.

## Recommendation

Make Semantic Hub a catalog and governance service for published semantic releases.
Keep the current builder as an optional built-in provider.
Run Helios independently and open its application for advanced building and Talk to Your Data.
Add versioned API adapters where release import and delegated queries require integration.

Default installation: one AMP provisions Hub and Helios applications from separate, pinned repositories within one CAI project.
Helios is an optional Git submodule; each application has a separate environment and state.
An external mode connects to an existing Helios deployment.

Stop using upstream source merges as the normal integration mechanism.
A shared repository history does not need to become a shared deployment lifecycle.

[Upstream inspection and merge result](upstream-review.md) · [Provider contract proposal](provider-contract.md) · [Bundled AMP deployment](deployment-layout.md)

[Documentation cleanup completed](documentation-cleanup.md): upstream guides now live in the pinned Helios checkout; local compatibility guides remain Hub-owned.

## Execution plans

The repository layout is accepted. The local preview implements the first runtime increment.

1. [Implementation plan](implementation-plan.md): work packages I0–I8 and release gates.
2. [Local smoke test plan](local-smoke-test-plan.md): fixtures, checks L00–L12, and evidence requirements.
3. [AMP preparation plan](amp-preparation-plan.md): setup sequencing, checks A01–A11, and recovery.

## Requirements interpreted

| Requirement | Proposed behavior |
| --- | --- |
| Preserve the current builder | Offer Built-in as a selectable provider, including installations without an external builder. |
| Reuse Helios improvements | Link to its independently deployed UI; use its APIs through one bounded adapter. |
| Avoid maintaining two advanced builders | Limit Built-in to existing capabilities, compatibility, and essential fixes. |
| Reuse Talk to Your Data | Launch Helios Talk first; add delegated API query support only after authorization and version checks pass. |
| Support other builders | Register providers with explicit capabilities; do not assume every provider can execute queries. |
| Run several CAI applications | Configure separate UI, API, and optional MCP origins per provider. |
| Keep the Hub useful | Own discovery, release registration, provenance, access rules, and the stable external consumer interface. |
| Sync upstream now | Fetch and merge the verified original upstream before redesign work; see the recorded no-op merge result. |

“Default” is a new-project preference, not an outage fallback.
Existing projects retain their assigned provider.
If Helios becomes unavailable, the Hub must not silently rebuild or execute its models with Built-in.

## Challenges to the initial direction

### A link alone does not integrate semantic context

Opening Helios solves UI reuse with little maintenance.
It does not let Hub MCP consumers retrieve a verified release or execute against that release.
The product must distinguish a linked workspace from an imported, query-capable model.

### Importing definitions does not import an execution engine

A portable metric definition may reference Helios-specific data sources or functions.
The Hub must retain the owning execution provider and explicit source bindings.
It must not run external models against local demo files.

### Maintaining two editable copies creates conflicting truth

The assigned builder owns its draft and its authoring history.
The Hub stores accepted immutable release snapshots, provider references, and Hub-level access policy.
Hub edits never silently overwrite the provider draft.
Switching builders requires an explicit supported export/import process that starts a new draft.

### “API available” does not mean “integration ready”

The inspected Helios API supports useful lifecycle operations.
It lacks the complete provider-neutral export and capability contract proposed here.
Cross-application identity and revision pinning also need proof against the deployed CAI applications.

### The legacy builder remains a maintenance cost

Retaining Built-in means preserving some local dependencies and tests.
Use an optional package boundary and freeze its feature scope.
Do not claim the Hub becomes lightweight until external-only installations can start without builder dependencies.

## Target architecture

```text
Business user / Agent Studio
              |
      Semantic Hub CAI app
      +-------------------------------------------+
      | Catalog, provider registry, access policy  |
      | Accepted release snapshots and provenance |
      | Search / context API / MCP routing         |
      +---------------------+---------------------+
                            |
                  Provider adapter contract
               +------------+--------------+
               |            |              |
        Built-in provider   |       Future provider
        Optional local      |       UI / API / export
        builder + demo      |
        execution           |
                    Helios CAI applications
                    +--------------------------+
                    | Builder and review UI    |
                    | Provider-owned APIs      |
                    | Talk to Your Data        |
                    | MCP / warehouse execution|
                    +--------------------------+

Hub state: relational database + immutable artifact storage
Provider state: remains private to each provider deployment
Browser: Hub -> approved provider UI URL
Backend: Hub adapter -> authenticated provider API / MCP
```

The diagram represents responsibility boundaries, not a claim that each box needs a separate process.
Helios may deploy its UI, API, and MCP service through different application origins.
The Hub must support that arrangement without assuming one base URL.
No application reads another application's database, local directory, or credential files.

## Ownership boundaries

| Area | Semantic Hub owns | Builder or query provider owns |
| --- | --- | --- |
| Workspace | Hub project, assigned provider, external IDs | Native project and workspace lifecycle |
| Authoring | Launch action and progress reference | Source registration, extraction, drafting, validation, review |
| Documents | Registered evidence references or authorized frozen excerpts | Uploads, originals, extraction, embeddings, review |
| Publication | Acceptance into the Hub catalog and Hub release identity | Native publication and native revision identity |
| Semantic contents | Immutable accepted snapshot and format validation | Authoritative authoring format and meaning |
| Query | Capability checks, access checks, provider routing, trace reference | Interpretation, compilation, execution, result policy |
| Security | Hub permissions and credential references | Native permissions and source access enforcement |
| Persistence | Hub relational database and artifact store | Provider-owned storage and migrations |

A provider publication and Hub acceptance are different events.
The Hub does not re-run every builder review or pretend it approved the business meaning independently.
It validates provenance, schema compatibility, publication evidence, hashes, and its own acceptance policy.

For built-in documents, retain today's workflow behind the built-in adapter.
For Helios workspaces, send users to Helios for document and model preparation.
Automatic transfer of raw uploaded documents between applications is outside the first release.

## User journeys

### Create or open a semantic workspace

1. Create a Hub project or open an existing project.
2. Select Built-in, Helios, or another configured provider.
3. For Helios, associate an authorized native organization and model.
4. Select **Build semantic model** to open the provider UI in a new tab.
5. Complete source preparation, review, and publication in that provider.
6. Return to Hub and select **Refresh published releases**.
7. Accept a compatible published revision into the Hub catalog.

If no release adapter exists, show a linked workspace with an **Open provider** action.
Do not show imported definitions, verified publication, or Hub query capability for that workspace.
Do not assume Helios can create a new model through a provider-neutral API; association with existing models is the first path.

### Ask a question

1. Select a model and inspect its provider and available capabilities.
2. For the initial external-provider release, select **Talk in Helios**.
3. Helios authenticates the user and owns its conversation and execution behavior.
4. For a later API integration, the Hub sends an authorized query with the exact accepted provider revision.
5. Return the result with provider, model, revision, source binding, and trace identity.

A Helios UI link opens its native model context; it does not prove that a specific historical Hub revision was queried.
Show this limitation until a pinned handoff is supported and verified.
Do not promise the current Hub Playground's explicit Run gate for Helios's native conversation flow.

### Use an external agent through Hub MCP

1. Discover only models authorized for the caller.
2. Select an accepted Hub release with a provider binding.
3. Retrieve immutable context and supported evidence.
4. Resolve and execute only through the bound query capability.
5. Reject unsupported execution instead of changing provider or substituting sample data.

Keep existing built-in model IDs and v1 request behavior during migration.
Add provider-qualified identity behind those IDs before introducing a new API version.
Link-only providers must not enter the existing executable-model catalog.

## Delivery plan and acceptance criteria

| Phase | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 0: baseline | Cleanup commits, separate v2 branch, upstream evidence | Clean tree; recorded upstream SHA; existing consumer regression tests pass |
| 1: provider links | Registry, per-project assignment, Built-in adapter, Helios launch URLs | Existing demos work; no secrets in URLs; two external origins work; outage has no silent fallback |
| 2: release exchange | Versioned export adapter, immutable imports, acceptance workflow | Reimport is idempotent; draft-only model rejected; changed hash rejected; evidence and native revision retained |
| 3: delegated query | Optional provider execution adapter and principal propagation | Exact revision verified; two users retain different permissions; source bindings preserved; no local sample substitution |
| 4: extraction | External-only Hub package and optional built-in package | Hub starts without Helios console, crawler, builder, or query-agent dependencies; Built-in remains usable when installed |
| 5: provider compatibility | Second adapter, compatibility suite, operational controls | Link-only and export-only providers work without pretending to support query; upgrade rollback succeeds |

Phase 1 is the smallest useful release.
It should not wait for generic model editing, full chat embedding, or a universal semantic format.
Phase 2 is required before external releases can serve as governed Hub context.
Phase 3 is required before Hub claims to execute those releases through a provider.

## Proposed code restructure

These paths are proposed destinations; this branch does not move runtime code yet.

```text
semantic_hub/
  core/                 Provider registry, catalog, policies, release acceptance
  contracts/            Provider manifests, capability and release schemas
  api/                  Consumer API, authoring orchestration, MCP routing
  providers/
    builtin/            Adapter to the preserved current implementation
    helios/             HTTP/MCP integration and UI URL construction only
  storage/              Relational repositories and artifact interfaces
optional-builders/
  builtin/              Extracted current builder and demo runtime
```

| Current location | First change | Later destination |
| --- | --- | --- |
| `cai_integration/application.py` | Add provider composition without changing current default | Hub bootstrap without importing Helios console |
| `apps/helios/console/demo_hub.py` | Wrap existing local runtime with Built-in provider | Optional built-in implementation |
| `shared/helios_core/demo/context.py` | Preserve publication and review behavior | Built-in authoring package |
| `shared/helios_core/demo/materials.py` | Preserve current document workflow | Built-in document package |
| `shared/helios_core/demo/playground.py` and `agent/` | Preserve local Playground behind its provider | Optional built-in query capability |
| `apps/helios/console/semantic_hub_api.py` | Keep v1 contracts; add provider-aware dispatch internally | Hub consumer API |
| `shared/helios_core/demo/consumer.py` | Separate common release access from local execution | Hub release service + built-in execution adapter |
| `mcp_server/` | Preserve existing tool contracts; report unsupported external capabilities | Provider-neutral Hub client |

Wrap existing behavior before moving files.
A mass rename would make the provider boundary harder to test and review.

## Migration and rollback

1. Back up the current state and record published release hashes before migration.
2. Create one Built-in provider record for each existing installation.
3. Associate existing model IDs with that provider without changing release contents.
4. Add external providers as separate records; never repurpose existing source IDs.
5. Enable external launch actions behind a feature flag.
6. Enable imports and delegated queries separately after their contract tests pass.
7. Extract dependencies only after both built-in and external journeys pass.

Store additive provider metadata in a relational repository.
Target PostgreSQL for production Hub state; retain an appropriate local repository for development and migration.
Do not include a database-engine replacement in the initial provider-link release.
Maintain separate databases or namespaces and credentials for independently deployed applications.

Rollback disables external integration and restores prior application code against compatible additive state.
It does not rewrite accepted releases or migrate remote projects into Built-in.
If external execution is unavailable, return an explicit unavailable status.
Cached release context is usable only while Hub policy still authorizes access and the release remains accepted.

## Integration and security decisions

Use top-level navigation first; avoid an iframe or a browser-side cross-origin API dependency.
The destination application owns login and session state.
Existing CAI access does not prove permission to a model or its underlying data.

Backend calls require a proven identity contract.
Do not manufacture trusted `remote-user` or `x-forwarded-user` headers from a browser-provided value.
A CAI API key may admit a request through ingress without representing the business user's provider permissions.
Until end-to-end delegation is verified, keep query execution in the provider UI.

Register allowed provider origins administratively and reject unexpected redirects or destinations.
Store credential references server-side; never include keys in launch URLs or callbacks.
Provider errors, timeouts, and authorization denials remain visible rather than becoming empty successful responses.

Use a manual refresh first, then bounded polling if needed.
Signed callbacks or webhooks can be added when the provider supports them.
Validate any callback against the registered origin, project, release, and caller before accepting artifacts.

## Release model and future interoperability

Preserve provider-native artifacts and a thin common release envelope.
Normalize only fields that the adapter can translate without changing meaning.
Ossie is the first supported semantic format, not a requirement that every future provider implement Helios internals.
Opaque unsupported content remains reference-only; it cannot silently become executable Hub semantics.

A source binding is not always a data snapshot.
For live warehouse queries, retain the execution timestamp and available data-version information separately from semantic revision identity.
A fixed semantic definition does not guarantee identical results against changing live data.

Define a supported adapter/API compatibility range and pin deployments to tested versions.
Provider upgrades should trigger contract checks, not source merges into the Hub.
Shared libraries, if needed, should be small versioned dependencies rather than a vendored application tree.

## Decisions proposed for review

| Decision | Recommended default |
| --- | --- |
| Who owns the draft? | The selected builder, exclusively |
| What does Hub publish? | Accepted immutable provider releases with provenance |
| How does a user reach Helios? | A new-tab deep link with native organization/model context |
| Where does external chat run first? | In Helios, with its own permissions and execution semantics |
| What happens when Helios is down? | Show unavailable; never silently switch providers |
| How broad is Built-in development? | Existing functionality plus essential fixes and compatibility |
| How do new providers join? | Explicit link, export, and query capabilities; implement only supported ones |
| How are upstream improvements consumed? | Independent provider upgrades plus adapter compatibility tests |

A deployed Helios UI/API/MCP URL set and a permitted identity strategy are needed for the integration spike.
They are not needed to review this design or retain the completed repository baseline.
