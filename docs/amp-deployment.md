# Semantic Hub AMP deployment

The AMP follows the isolated-environment and ordered-task pattern in `../ray-serve-cai`.
The AMP entry point is [`.project-metadata.yaml`](../.project-metadata.yaml).
Catalog metadata is in [`METADATA.yaml`](../METADATA.yaml).
The manifest follows the [Cloudera AMP project specification](https://docs.cloudera.com/machine-learning/cloud/applied-ml-prototypes/topics/ml-amp-project-spec.html).

## Deployment flow

```text
GitHub checkout
      |
      v
Setup job --> project virtual environment --> verify five source packs
                                                   |
                                                   v
CAI authenticated ingress --> Semantic Hub Application (one process)
                                  |       |       |
                                Studio  Swagger  Consumer API <-- MCP / CAI agent
                                  \       |       /
                               persistent project state
```

The application requires two CPUs, 8 GB memory, and no GPU.
Use a Standard Python 3.11 runtime. Setup also accepts Python 3.12.
The setup job installs the pinned `cai_integration/requirements.lock` into `.venv-semantic-hub` on the shared project filesystem.
The lock derives from `apps/helios/demo-requirements.txt`.
It clears inherited Python import paths and pip target/prefix settings.
Setup and startup invoke Python with `-I` to exclude notebook paths and user packages.
Setup disables system-site-packages and checks the origin of installed distributions.
It preserves CAI credentials, proxy/CA settings, and explicit package-index environment variables.
A successful setup job precedes application startup.
No setup step requires a model-provider key.
No setup step approves, publishes, or activates a semantic version.

## Import and launch

1. Make the AMP files available in your deployment repository revision.
2. In CAI Workbench, import the repository as an AMP.
3. Use `https://github.com/FerdinandZhong/semantic-hub.git` as the repository URL.
4. Select `.project-metadata.yaml` and a Standard Python 3.11 runtime.
5. Set `SEMANTIC_HUB_STATE_DIR` to a persistent project directory.
6. Keep the default `/home/cdsw/state/semantic-hub` for a standard Workbench project.
7. Leave application authentication enabled.
8. Wait for the setup job and the Semantic Hub Application to start.
9. Open the Application URL from Workbench.
10. Configure drafting, query, and embedding profiles under **Model configuration**.
11. Review and publish the versions you want remote agents to discover.

The initial source defaults to finance. The Hub also lists manufacturing, pharma, power, and pharmaceutical intelligence.
The install contains repository source packs. It does not copy your laptop's uploads, saved credentials, or published versions.
Use the Application URL returned by Workbench. Its subdomain can contain a generated suffix.

## URLs and authentication

| URL | Purpose |
| --- | --- |
| `https://<application-host>/` | Semantic Hub UI |
| `https://<application-host>/docs` | Swagger UI |
| `https://<application-host>/api/semantic-hub/v1/openapi.json` | Consumer OpenAPI schema |
| `https://<application-host>/api/semantic-hub/v1/capabilities` | Published-context capabilities |
| `https://<application-host>/healthz` | Application readiness |

CAI authenticates browser sessions and remote API requests at its Application ingress.
The manifest sets `bypass_authentication: false`.
The application binds `0.0.0.0` on the injected `CDSW_APP_PORT`.
The launcher keeps the Workbench Jupyter kernel alive and supervises the isolated server as a child process.
It forwards shutdown to the server process group and reports server exit errors in the Application log.
It does not create a separate Semantic Hub bearer token.
It does not compare a caller's CAI key with the job owner's `CDSW_APIV2_KEY`.
The backend trusts the authenticated ingress. Do not expose its container port through another unauthenticated route.

Remote callers supply their own CAI API v2 key as `Authorization: Bearer <key>`.
This is the credential sometimes stored locally as `cdsw_v2_key`.
The filename is not an environment variable or a credential value.
CAI determines whether the caller can access the Application.
All authorized Application users share this Hub workspace. Per-model authorization is not implemented.
The CAI ingress/key behavior still requires a live workspace acceptance check.

## MCP configuration

The existing twelve stdio MCP tools call the same Application origin.
Import [the AMP MCP configuration](../apps/semantic-hub-mcp/agent-studio.mcp.json).
It pins published AMP implementation commit `bb6a518`.
Replace the Application URL placeholder, then configure the MCP subprocess secret `CDSW_APIV2_KEY`.
The JSON omits that secret so the subprocess inherits it from its runtime environment.
Unset a stale `SEMANTIC_HUB_API_TOKEN` before using CAI credentials.

```json
{
  "mcpServers": {
    "semantic-hub": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/FerdinandZhong/semantic-hub.git@bb6a51848614b8100580d165066c97526f0c8a61#subdirectory=apps/semantic-hub-mcp",
        "semantic-hub-mcp"
      ],
      "env": {
        "SEMANTIC_HUB_URL": "https://<application-host>"
      }
    }
  }
}
```

`CDSW_APIV2_KEY` is the new adapter fallback when `SEMANTIC_HUB_API_TOKEN` is unset.
An explicit `SEMANTIC_HUB_API_TOKEN` still takes precedence for existing standalone deployments.
Do not paste credentials into Git-tracked JSON files.
The MCP transport sends the key only to the configured origin and does not follow redirects.

## Persistence and restart

`SEMANTIC_HUB_STATE_DIR` holds the workspace's durable files.
These include SQLite databases, document originals, extracted pages, reviewed rows, generated models, versions, ontology, metadata, and Lance indexes.
The current stores retain their existing formats. This increment does not introduce a new database.
Retain the entire directory, including `.model-secrets/key`, when backing up or moving the workspace.
That key decrypts API keys saved through Model configuration.
Stop the Application before a filesystem backup, or use consistent database backups.
Do not copy live SQLite files independently of their WAL files.

Restarting the Application retains this directory and the virtual environment.
Rerunning setup validates source hashes and reconciles dependencies. It does not reset workspace state.
Run one Application process for each state directory. Uvicorn uses one worker.
Do not start a separate legacy consumer process against the same live workspace.
The combined Application shares its in-memory Hub between authoring and consumer routes.

Lance files currently use the project filesystem beneath the state directory.
An external object-store location requires a separate storage adapter and credentials.
Atlas synchronization is also a separate integration increment.

## Local rehearsal

Use the same installed runtime as the demo:

```bash
SEMANTIC_HUB_STATE_DIR=/tmp/semantic-hub-amp-test \
  python -m cai_integration.application --local --port 8099
```

Local mode binds loopback only and requires an explicit port.
CAI mode rejects startup without `CDSW_APP_PORT`, `CDSW_PROJECT_ID`, and `CDSW_DOMAIN`.
Local mode does not prove ingress authentication.

## Acceptance checks

1. Open the UI and Swagger through the authenticated CAI Application URL.
2. Confirm an unauthenticated remote request cannot read model inventory.
3. Confirm an authorized CAI API v2 key can read capabilities and inventory.
4. Configure a model profile and test its saved connection.
5. Publish a reviewed finance version using the documented reference SQL.
6. Run the saved metric and confirm `686572.96` SGD for the unchanged source pack.
7. Connect MCP and inspect that version's definitions and lineage.
8. Restart the Application and confirm the version and uploaded material remain available.
9. Verify the API rejects an incorrect context hash.
10. Confirm unavailable periods return missing data rather than another period's value.

Local checks cover manifest ordering, persistent settings, startup guards, shared runtime, and combined UI/API/Swagger routes.
Live CAI launch, ingress authorization, and restart persistence remain unverified until these checks run in Workbench.

## Recovery: CAI packages reported by pip check

A setup failure can mention `cml`, `mlflow-skinny`, or `mlflow-cml-plugin` dependencies.
These packages belong to the CAI runtime, rather than the Semantic Hub application dependency set.
An inherited `PYTHONPATH` can expose them even when a virtual environment disables user-site packages.
The 18 October isolation fix reproduces and prevents this failure locally.

1. Stop the failed setup job.
2. Update the project checkout to the latest Semantic Hub commit.
3. Rerun `semantic-hub-setup` with `cai_integration/setup_environment.py`.
4. Confirm the log reports `Virtual environment isolation passed; CAI runtime packages excluded.`
5. Confirm `pip check` and all five source-pack checks pass.
6. Start or restart the Semantic Hub Application.

Setup rewrites the virtual environment configuration to exclude system packages.
It preserves a contaminated application environment as `.venv-semantic-hub.before-isolation-<timestamp>` before rebuilding.
It retains the Hub state directory, uploads, reviewed versions, and credential encryption key.
It does not uninstall or downgrade Workbench's platform packages.
Use `PIP_INDEX_URL` or `PIP_EXTRA_INDEX_URL` when your deployment requires a custom package index.
The isolated installer ignores inherited pip configuration files and install target overrides.

## Recovery: Jupyter kernel stops when the Application starts

The previous launcher replaced the Workbench kernel process using `os.execve`.
Workbench then observed a lost or restarting kernel and stopped the workload.
The 18 October launcher fix retains the kernel and runs the server as a supervised child process.
It also removes the bootstrap project argument before the server parses its command line.

1. Update the project checkout from `main`.
2. Confirm the Application script is `cai_integration/start_application.py`.
3. Restart the Application.
4. Check for `Semantic Hub server started as child process` in the log.
5. Confirm the Uvicorn startup message and open the Application URL.

No dependency reinstall is required if the repaired setup job already passed.
This fix passed local supervision, child-failure, and shutdown tests.
A live CAI Application restart remains the deployment acceptance check.
