# Local sector demo runtime

The first runtime increment implements pack selection, explicit local review, typed DuckDB loading and predefined query examples.
The existing Helios console hosts Semantic Hub at `/demo`, queries at `/demo/query`, and Studio at `/demo/context`.
Use `?source=manufacturing` (or another connection ID) to open a source-specific query or Studio page.
Read [the context-builder guide](context-builder.md) for inspection, authoring, SQL validation and local version review.
Finance, manufacturing, pharma and power use the same launcher and execution code.
The power pack supplies the SP Group prototype title through registry configuration.

```text
Selected registry entry -> verified serving snapshot -> explicit sample review
                                                            |
                                                            v
Console example -> bound request -> Helios compiler -> bounded DuckDB -> result evidence
```

## Run locally

1. Install the local runtime dependencies into your project environment.

   ```sh
   python -m pip install -r apps/helios/demo-requirements.txt
   ```

2. Inspect the selected definitions and copy the `snapshot_sha256` value.

   ```sh
   python start_demo.py --dataset power --inspect
   ```

3. Review the definitions, then record the decision against that exact snapshot.
   Replace `SNAPSHOT_HASH_FROM_INSPECT` and `YOUR_NAME` with the reviewed hash and operator name.

   ```sh
   python start_demo.py --dataset power --review \
     --release SNAPSHOT_HASH_FROM_INSPECT --reviewer YOUR_NAME
   ```

4. Verify the reviewed example, then start the console.

   ```sh
   python start_demo.py --dataset power --check
   python start_demo.py --dataset power --ui-mode query
   ```

5. Open `http://127.0.0.1:8080/demo/query?source=power`.
   Select the example and choose **Run example**.
   Open `/demo` for the multi-source Hub.

Replace `power` with `finance`, `manufacturing` or `pharma` to select another pack.
`HELIOS_DEMO_DATASET` supplies an environment default; an explicit `--dataset` takes precedence.
Each pack requires its own review.
Launching an unreviewed pack permits inspection but blocks execution.
Restarting creates a fresh request binding, so old browser requests are rejected.

Review receipts live under `state/demo/<pack>/<snapshot>/review.json` by default.
`--state-dir` or `HELIOS_DEMO_STATE` selects another state directory.
The launcher also puts console metadata and dependency caches in that state directory.
`--registry` and `--fixtures-root` accept alternate explicitly prepared packs.
Their environment defaults are `HELIOS_DEMO_REGISTRY` and `HELIOS_DEMO_FIXTURES`.
An optional `--settings` file must contain exactly the selected `pack_id` and `snapshot_sha256`.
The launcher rejects mismatched saved settings instead of changing the selected pack.

## Review and source boundaries

The review command records an operator-declared decision for local sample examples.
It does not authenticate that operator or publish an enterprise semantic release.
Fixture manifests and Ossie drafts remain `IN_REVIEW`.
Tests create temporary receipts labeled as automated test reviews; those receipts are never installed as operator approvals.

The runtime registry pins source-manifest and model checksums.
The snapshot fingerprint also covers branding, timezone, examples and adapter selection.
The loader validates each declared serving asset and snapshots its bytes before execution.
It rejects symlinks, path escapes, changed files, undeclared CSV schemas and mismatched row counts.
It never opens evaluation files or discovers arbitrary neighboring files.
The runtime works when the entire evaluation directory is absent.

SQL column types come from Ossie declarations, with decimals stored as `DECIMAL(28,8)`.
Empty CSV cells become SQL nulls.
No CSV type inference runs during loading.
The local database contains only tables from the selected pack.
Document manifests are validated, but document retrieval remains disabled.

The browser sends a predefined example identifier bound to the pack, snapshot and current process token.
The query endpoint accepts only a configured example or a metric identifier from the active reviewed context.
The context builder has separate authoring endpoints for draft definitions and bounded reference SQL.
Helios compiles the configured metric using its existing compiler.
The local adapter rejects writes, multiple statements, undeclared sources, nested queries and unsupported functions.
It disables DuckDB external access and caps memory at 256 MB.
Queries use a five-second deadline and a maximum of 1,000 returned rows.
Original examples return one aggregate row; reviewed context metrics return at most 200 rows.
Results include SQL, result, model and source-manifest hashes.

Sample mode exposes its Hub, source configuration, LLM configuration, query page, Studio, required static assets, and listed local APIs.
Legacy conversation and live-source endpoints return 404 in this mode.
Ordinary console launches retain their existing routes and ontology-cache restoration.
The local sample server is intended for one operator; its process token is not user authentication.

## Verification

On 11 October 2026, the context-builder increment passed 78 focused tests.
Eight complete browser workflows passed across all four packs at desktop and mobile widths.
The power Docker preview passed both widths, and the updated local container passed query and builder checks.
The builder preserves existing state and stores no automated test versions in the operator workspace.


On 10 October 2026, 58 focused tests passed.
These covered runtime isolation, fixture integrity, compiler results, document traces, console authorization, health and the existing observability extension.
Eight browser cases passed: all four packs at 1440-pixel and 390-pixel widths.
The inherited seven fixture checks are included in the test count.

Run the focused runtime, inherited fixture and compiler regressions:

```sh
PYTHONPATH=shared:apps/helios-ds-generation/src HELIOS_ROOT="$PWD" \
python -m pytest -o pythonpath=shared apps/helios/tests/test_demo_runtime.py \
  apps/helios/tests/test_compiler.py apps/helios/tests/test_trace_documents.py \
  apps/helios-ds-generation/tests/test_sector_demo.py -q
```

The generator test environment also requires pytest and PyIceberg.
The explicit pytest path prevents the application MCP directory from shadowing the installed MCP SDK.
The browser check requires Playwright and its Chromium browser:

```sh
python apps/helios/workbench/check_demo_browser.py --output /tmp/helios-demo-browser
```

That check launches all four actual console processes.
It compares displayed results against separate evaluation references at desktop and mobile widths.
It checks page errors, horizontal overflow, cross-pack request rejection and blocked legacy routes.
It retains screenshots and JSON results in the output directory, then stops the test processes.

## Container configuration

The container uses the same launcher, registry and review receipt contract.

```sh
docker build -f apps/helios/Dockerfile.demo -t helios-demo .
docker run --rm -p 127.0.0.1:8080:8080 \
  -e HELIOS_DEMO_DATASET=power \
  -v "$PWD/state/demo:/state" helios-demo
```

Mount the state directory containing the explicitly reviewed sample receipt.
An absent receipt leaves the page in review mode.
On 11 October 2026, the Docker image built and the power demo passed CLI and browser execution checks.
Both paths returned 8,547.282 kWh, with no browser JavaScript errors.
The container uses the supported lifespan context for cleanup; two lifecycle/isolation tests passed inside the image.
All 19 local runtime tests also passed after that compatibility fix.
The image build excludes evaluation directories, local environment files and Python caches.
Container acceptance for the other three packs remains pending.

The following container details are a historical 11 October snapshot, not a current process inventory.
The earlier container preview ran as `helios-demo` at `http://localhost:8080/demo`.
Its named volume is `helios-demo-state`.
The context builder is available at `http://localhost:8080/demo/context`.
The current image is `helios-demo:context-builder`; `helios-demo:latest` points to the same build.
The stopped container `helios-demo-before-context` preserves the previous runtime for rollback.
Its power snapshot has an explicit review labeled `Codex verification: local synthetic sample only`.
This enables the predefined example without changing the source fixture's draft status.
Use `docker stop helios-demo` to stop this instance and `docker start helios-demo` to resume it.

The newer Semantic Studio and Hub run as a local process for development review:

```sh
python start_demo.py --dataset power --state-dir /tmp/helios-builder-review --port 8084
```

Open `http://localhost:8084/demo` for Semantic Hub.
Open `/demo/context?source=power` for Studio or `/demo/context?source=power#hub` for that source's Versions & releases.
The `#hub` fragment names the older version tab; it is not the multi-source Hub.
Prefer this local process for development; Docker rebuilds are optional deployment checks.
This increment adds canvas editing, item review, version comparison, local publication and separate query activation.
See [Studio workflow and verification](context-builder.md).
The container image has not been rebuilt for this increment.

## Next milestone

The shared indexed retrieval core and MCP bundle checks are implemented; see [retrieval status](semantic-retrieval.md).
The four-pack query page still uses predefined or active-reviewed metrics.
Connecting it to a general planner needs explicit retrieval and policy integration.
Studio now links documents to canvas evidence, review items, and version artifacts.
Scoped combined SQL/document answers and held-out agent improvement measurements remain pending.
Use [reference SQL examples](demo-reference-sql.md) to complete starter-metric validation.
