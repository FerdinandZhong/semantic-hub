# Local v2 preview

This increment adds a provider workspace at `/v2`.
It retains the existing Built-in Studio and v1 consumer API.
External workspaces open in native Helios through links with organization and model identifiers.
The Hub does not import external releases or execute delegated queries yet.

```text
Hub /v2 workspace
   +-- Built-in Studio --> existing Hub state and sample queries
   +-- Provider registry --> separate providers.sqlite
   +-- Helios links --> native Helios UI --> native Helios API
                                             |
                                      separate Helios state
```

## Start and inspect

Run commands from the repository root.
The existing Hub environment `.venv-semantic-hub` must already exist.
Initialize the pinned submodule before preparing the provider environment.

```bash
git submodule update --init external/helios
python deployment/local/run.py prepare
python deployment/local/run.py start --helios-ui-port 8200 --helios-api-port 8201
python deployment/local/run.py check
```

Open `http://127.0.0.1:8099/v2` for the Hub workspace.
Open `http://127.0.0.1:8200` for native Helios.
The alternate provider ports avoid an existing listener found during local testing.
Default ports remain Hub 8099, Helios UI 8100, and Helios API 8101.
An occupied port causes an error; the launcher does not stop another process.

1. Select a Built-in workspace to inspect its definitions and table previews.
2. Open the editor to validate, review, and publish a Built-in model.
3. Open Talk to your data and select a saved metric.
4. Inspect the interpretation, then select Run.
5. Open Builders & connections, then select Open builder for native Helios.
6. Select a native organization and model provisioned by your Helios administrator.
7. Link that workspace using its native organization and model identifiers.

Saved metric queries do not require an LLM.
Free-text interpretation and document answers require configured inference.
Native Helios requires its own backend and model configuration for live data queries.
The Hub never substitutes a Built-in sample for a failed native query.

An empty native installation has no organization grants.
For local review only, create an authorized empty draft with:

```bash
.venv-helios/bin/python -I deployment/local/init_review.py
```

This opt-in command creates organization `local-review` and model `empty-review` for the local development identity.
It also creates an explicitly unconfigured Impala connection profile because native Helios requires a model data-source reference.
It creates no source data, semantic artifacts, published release, or query result.
Link those identifiers through Builders & connections in the Hub.
The command refuses to change existing records with those identifiers.

Stop only this launcher's processes with:

```bash
python deployment/local/run.py stop
```

State remains under `state/local-v2/hub` and `state/local-v2/helios`.
Logs and process ownership records remain under `state/local-v2`.
Native UI build output lives under `state/local-v2/native-ui/apps/helios/ui/dist`.
Preparation rebuilds that output without changing tracked files in the pinned provider checkout.
Pass the same `--state` value to every command when using another directory.
Stop, prepare, and start again after updating dependencies or backend code.

## Other modes

Use a separate state directory when changing provider origins.
Provider IDs cannot silently change origins after registration.

```bash
python deployment/local/run.py start --mode builtin_only --state state/local-builtin --hub-port 8300
python deployment/local/run.py start --mode external --state state/local-external --hub-port 8301 \
  --helios-ui-origin https://YOUR-HELIOS-UI \
  --helios-api-origin https://YOUR-HELIOS-API
```

External mode starts only the Hub and stores explicit provider origins.
It does not copy credentials, provision applications, or fall back to bundled Helios.
The local harness uses loopback-only access without Hub authentication.
Do not use the local harness as a CAI deployment launcher.

## Implementation scope

| Area | Implemented behavior | Remaining work |
| --- | --- | --- |
| Provider registry | Persistent origins, workspace links, immutable provider identity, Built-in assignment | Credential references, live compatibility negotiation, controlled origin updates |
| Studio | Compact definition list and inspector; link to existing editor | Integrated editing and full builder package extraction |
| Sources and tables | Source inventory, schema inspection, bounded sample previews | External metadata import |
| Talk | Published Built-in versions, explicit execution approval, results and provenance | External delegated execution |
| Native Helios | Independent environment, state, UI/API processes, pinned revision | Configured live backend and inference acceptance |
| Deployment | Bundled, external, and Built-in local modes | Multi-application CAI provisioning and acceptance |

Provider registration uses additive tables in `providers.sqlite`.
Existing source IDs and release bytes remain unchanged.
Consumer tokens remain read-only for registry writes.
The local application and CAI-authenticated application can register providers.
Cross-site browser writes are rejected.

## Verification

Baseline Hub commit: `2dd91315228d3ec5bed617888375b0953dee5490`.
Pinned Helios commit: `316f5d89926f96d366afaee641bd923af4ca6bf3`.
The implementation is the change following that baseline on `design/semantic-hub-v2-providers`.
The link adapter version and provider dependency overrides are recorded in `deployment/provider-lock.json`.

The first increment passed these checks:

- 9 provider registry/API tests, including token restrictions and origin validation.
- 11 local launcher tests, including occupied ports, process ownership, checkout validation, and mode isolation.
- 49 existing AMP and consumer/retrieval tests.
- Browser checks at 1440, 980, and 390 pixels without horizontal overflow or JavaScript errors.
- Table schema and bounded preview loading.
- Provider registration, project linking, and encoded native navigation.
- Question edits invalidated the pending execution action.
- Explicit execution returned SGD 686,572.96 from an isolated, reviewed synthetic finance fixture.
- The result remained visible above the chat composer.
- Three real local applications passed readiness and an owned stop/restart cycle with state retained.
- Native Helios Canvas, Data Sources, and Talk loaded the authorized empty draft with no JavaScript errors.
- Native browser API requests returned HTTP 200 for identity-scoped organizations, models, graph, sources, and conversations.
- The native UI was rebuilt with `npm ci` and `npm run build -- --outDir` targeting isolated state.

The native empty model correctly reports `degraded` because it has no published model or discovery run.
Optional native embeddings and vector evidence search are omitted from the local dependency preparation.
The build reported upstream npm dependency advisories and a Vitest engine warning; the TypeScript/Vite production build passed.
These checks establish a local preview, not production deployment acceptance.

The browser fixture uses test review helpers; it does not certify a production release.
No configured-LLM, live warehouse, or CAI multi-application result is claimed.

Run the API regression suite with:

```bash
.venv-semantic-hub/bin/python -m pytest tests/providers tests/amp/test_amp.py \
  apps/helios/tests/test_semantic_hub_consumer.py \
  apps/helios/tests/test_retrieval_service.py \
  apps/helios/tests/test_retrieval_index.py -q
```

For browser automation, create a new disposable state directory.
The fixture command refuses to modify a nonempty directory.

```bash
PYTHONPATH=.:shared .venv-semantic-hub/bin/python tests/providers/browser/seed.py --state /tmp/hub-v2-browser-new
SEMANTIC_HUB_STATE_DIR=/tmp/hub-v2-browser-new .venv-semantic-hub/bin/python -m cai_integration.application --local --port 8299
# In another terminal with Playwright and Chromium installed:
python tests/providers/browser/smoke.py --base-url http://127.0.0.1:8299
```

The browser script registers test providers and workspace links in that disposable state.
Use `--chromium /path/to/chromium` when Playwright's default browser is unavailable.
Screenshots default to `/tmp/semantic-v2-browser`.

## Reference designs

The workspace follows the compact sidebar, white panels, blue actions, and restrained spacing in the adjacent reference projects.
The UOB reference available locally was `../uob-ai-data-operations-workspace`.
The second reference was `../vehicle_manufacturing_blueprint`.
Neither reference repository was modified.
