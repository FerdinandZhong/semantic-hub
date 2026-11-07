# Semantic Hub project status

Recorded 3 November 2026; local development status updated 7 November 2026. The independent Hub AMP is running in CAI.
The updated chat and validation UI are deployed. Full acceptance remains incomplete.
This record describes completed checks; it does not monitor the application continuously.

## Source and deployment

| Item | Recorded value |
| --- | --- |
| Repository | `FerdinandZhong/semantic-hub` |
| Branch | `fix/amp-provider-bootstrap` |
| Deployed application commit | `cc4890e9022f49ef68cd8523424c011537696460` |
| Previous deployed commit | `998904caaf053ec35a035384bc6162dc397dde0e` |
| Main branch | These branch fixes have not been recorded as merged into `main` |
| CAI project ID | `imgz-mrce-iohy-pjhf` |
| Application ID | `vak0-9xsv-45cm-pkql` |
| Application entry point | `deployment/launchers/hub.py` |
| Setup entry point | `cai_integration/setup_environment.py` |
| Runtime | `docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-jupyterlab-python3.11-standard:2026.04.1-b7` |
| Latest confirmed restart | 3 November 2026, 15:28:05 UTC / 23:28:05 Singapore |

[CAI project](https://ml-7ca67a86-1f3.qzhong-a.a465-9q4k.cloudera.site/qzhong/semantic-hub) · [Hub application](https://semantic-hub-yjs4ct.ml-7ca67a86-1f3.qzhong-a.a465-9q4k.cloudera.site)

Documentation changes after this record do not imply another application deployment.

### UI commits included in the latest deployment

Commits `9c1acb1` to `4929695` are pushed and deployed in `cc4890e`.

| Commit | Change |
| --- | --- |
| `9c1acb1` | Chat answers include a read-only semantic canvas of the tables, metric, and passages used |
| `9ff5394` | Chat answers include deterministic retrieval and generation checks and the agent tool trace |
| `d99bd6d` | The agent rejects repeated successful tool calls and records `tool_calls` and `stop_reason` |
| `80e5a05` | Supporting-material analysis shows counts, grouped claims, formatted locations, and status badges |
| `4929695` | Validation opens with an n/n check summary; Studio tabs match the workspace tabs |

### Local commits after the deployed commit

Commits `6960649` to `ddd53a4` are local. They are not pushed or deployed. Checked on 7 November 2026: the remote branch has no newer commits.

| Commits | Change |
| --- | --- |
| `6960649`, `f812f98`, `8ecf3d2`, `a01c33a` | Materials spacing; canvas node cards, pill edge labels and keyed legend; compact Studio and Validation pages |
| `6043abf` | Docs: the [UI polish and ontology plan](ui-ontology-plan.md) |
| `36ed508` | P0: name-keyed glossary terms become concept link targets in three readers |
| `eb62311`, `c5731f5` | P1: canvas Fit stays at 0.85 or larger, 25 px titles, Studio summary counts, normal-weight inspector values |
| `5cfbcaa`, `90127eb`, `3eef7b4`, `17620ca`, `28f22f7` | P2: one page frame and breadcrumb on all workspace pages; tabs at the same position; one header and sidebar position |
| `3609359`, `d704414`, `6e905b3`, `0b68dfc` | P3: chat answer details behind Table, Semantic canvas, SQL & checks and Provenance tabs; Overview breadcrumb names the workspace |
| `110e188`, `ce7428e` | P4: read-only Ontology tab built from the existing ontology graph |
| `958c089`, `ddd53a4` | P5: glossary authoring in Studio, save-time term checks, and per-term review items |

These commits change CSS, JavaScript, templates, browser checks, and Python.
The Python changes are the template patching in `semantic_hub/editor.py` and `semantic_hub/support_pages.py`,
the glossary key fix, and the P5 term checks and review items in `shared/helios_core/demo/context.py`,
`shared/helios_core/demo/proposals.py`, and `apps/helios/console/demo.py`.
No route was added and no consumer payload changed shape.

## Implemented architecture

```text
Hub AMP -> isolated setup -> authenticated Hub application
                                      |
                     +----------------+----------------+
                     |                                 |
             Built-in Studio/chat              Optional health checks
                     |                                 |
             Published releases                 Separate Helios project
                     |                                 |
             Consumer API / MCP                 Native builder navigation
```

The Hub AMP has three tasks: create setup job, run setup job, and start Hub.
It does not fetch or provision Helios. The repository has no tracked Git submodule.
Default `auto` mode checks explicitly configured Helios endpoints at startup.
A fresh installation without healthy endpoints retains only the built-in builder.
Existing provider records and workspace links survive outages and `builtin_only` restarts.

Healthy endpoints register `helios-external` for navigation.
The optional health key does not grant user access to native workspaces.
Workspace discovery uses the caller's credentials and native grants.
Detection runs at startup or explicit retry; it is not continuous monitoring.
External release import and delegated query execution remain planned.

## Latest UI and chat changes

- Workspace cards remain the entry page. The built-in editor remains inside the main UI.
- Validation uses compact inline progress, followed by success or failure feedback.
- **Ask & run** authorizes one checked, read-only query against the selected published version and source snapshot.
- Numeric answers include executed results. SQL, scope, and provenance remain inspectable.
- Natural-language suggestions replace metric-definition text. Document answers retain expandable citations.
- The chat streams actual stages: Find context, Check scope, Read data, and Answer.

The legacy Playground retains separate Interpret and Run actions.
Saved-metric execution does not require an LLM. Free-text and document answers require configured query inference.
Chat history remains in page memory and clears on reload.
Each question is planned independently; earlier turns do not provide conversational context to planning.

Retrieval displays relevance signals, not calibrated confidence percentages.
Document keyword scores measure matched query terms. Free-text semantic lookup exposes raw SQLite FTS5 lexical ranking within the release.
Direct saved-metric selection has no retrieval confidence score.

Each answer reports **Answer checks · n/n passed**:

- Retrieval checks: selected-metric rank among lexical matches, scope checks, and selected passages.
- Generation checks: read-only SELECT, published tables, grouping, filters, row limit, and returned rows.
- Document checks: verified citations, grounded numbers, the support check, and whether the bounded repair ran.
- A saved metric shows retrieval as not applicable.

These checks verify structure and evidence. They do not measure business correctness, and there is no LLM judge.

Local commits after `cc4890e` add the following. They are not deployed.

- One page frame on every workspace page: breadcrumb "Workspace / <workspace> / <page>", workspace bar, then workflow tabs at the same position.
- Chat answers keep the headline visible and move Table, Semantic canvas, "SQL & checks · n/n passed", and Provenance into tabs.
- An Ontology tab, between Studio and Validation & review, shows classes, fields, metrics and relationships read-only, grouped by dataset.
- Studio has a Glossary tab. Each term edit is a separate review item and must be approved before publication.

## Verification evidence

### Local checks recorded for these changes

| Scope | Recorded result | Limit |
| --- | --- | --- |
| Independent AMP and provider increment | 125 tests passed | Local startup, registration, failure, and credential-isolation checks |
| Chat/UI increment | 100 tests passed: 92 regressions, 6 new chat tests, 2 combined-route tests | Includes mocked LLM cases; not 100 live queries |
| Browser history checks | Passed at widths 1440, 980, and 390 | Page history, restoration, isolation, and reload behavior |
| Browser experience checks | Numeric query, validation, progress, and document presentation passed | Document presentation used a fixture |
| Local commits `9c1acb1`–`4929695` | 181 tests passed across the providers, AMP, retrieval, chat, document, playground, agent, and Studio suites | Chat and document inference were mocked; the harness test used a fake SDK through the real tool bridge |
| Local browser, local commits | Saved-metric chat showed 6/6 checks and a 2-node canvas; the restored history re-mounted the canvas; no page errors | Materials analysis used mocked results; no configured LLM |
| P0–P1, `36ed508`–`c5731f5` | 160 tests passed for P0, 75 for P1; P1 browser measurements showed canvas Fit 0.85, 25 px titles, no overflow and no page errors | Local only; inference mocked |
| P2–P3, `5cfbcaa`–`0b68dfc` | 75 tests passed; tabs at 110 px on every workspace page at 1440 and 980 px; chat history and chat experience browser scripts passed | At 390 px the Overview bar wraps more than the shared bar |
| P4, `110e188` | 75 tests passed; route list and OpenAPI identical; existing Studio, version and chat canvases render identical SVG | Draft view not tried on a fresh unvalidated draft |
| P5, `958c089` | 117 tests passed, plus 92 in the Playground, agent, document, consumer, Hub and AMP suites; add, edit, delete and rejection flow passed in the browser | Version page checked with a stubbed response; no CAI check |
| Browser smoke after P2–P5 | Passes chat and all page-route checks, then stops at provider registration, which needs external endpoints | Same stopping point as before this work |
| Exposed API, local commits | Route list and both OpenAPI documents are identical to `998904c` | JSON bodies gain the additive fields listed below |

Progress screenshots used delayed delivery of real backend events to capture transient states.
They do not establish production response time.

### Latest UI deployment: 15:28 UTC

The fast-forward update job `7tzs-o3vu-1v6p-8gm7` succeeded with run `xrytlxv2zn8za1bj`.
Its report verified commit `cc4890e9022f49ef68cd8523424c011537696460` before restart.
The application returned `APPLICATION_RUNNING` after restart.
Health, Swagger, OpenAPI, and published-model inventory returned HTTP 200.

Seven hosted UI assets matched the reviewed checkout:
workspace JavaScript, workspace CSS, chat CSS, editor CSS, generated editor JavaScript, materials JavaScript, and materials CSS.
The editor comparison used its normal server-generated navigation transformations.

The live saved finance query returned **SGD 686,572.96**, one semantic canvas node, and **6/6 answer checks passed**.
It used `v1.0` with context hash `ca2348d85fa8b76d3c555bbb631d2f3c1bb0610f216a6ff6e86b28c856a5269f`.
The response streamed progress and heartbeats and completed in 32.48 seconds for this observation.
These checks establish deployed saved-metric execution; they do not establish live free-text inference or general answer correctness.

Before deployment, 31 targeted local tests passed; three required loopback access outside the sandbox.
The local browser check passed numeric execution, progress, validation, and fixture-based document presentation without page errors.
The source update preserved persistent state and credential files. No project environment repair was needed for this update.

### Earlier CAI checkpoint: 08:55 UTC

| Check | Result |
| --- | --- |
| Application status | `APPLICATION_RUNNING` |
| `/healthz` | HTTP 200; ready; `cai_ingress` authentication mode |
| `/docs` | HTTP 200 |
| `/api/semantic-hub/v1/openapi.json` | HTTP 200 |
| `/api/semantic-hub/v1/models` | HTTP 200 |
| Workspace JavaScript | HTTP 200; updated Ask & run and chat endpoint present |
| Studio JavaScript | HTTP 200; updated validation progress present |
| Streaming saved-metric query | HTTP 200; progress, heartbeats, retrieval, and result events received |

The live query used `POST /demo/api/playground/chat?source=finance` with saved metric `total_amount_sgd`.
It returned **SGD 686,572.96** from finance `v1.0`.
The context hash was `ca2348d85fa8b76d3c555bbb631d2f3c1bb0610f216a6ff6e86b28c856a5269f`.
The response completed in 31.94 seconds for this single observation.
This proves saved-metric execution through the deployed chat endpoint; it does not prove live free-text inference.

These requests used authenticated access.
Anonymous-access rejection, caller isolation, and browser identity checks were not repeated during this deployment.
The published finance release remained queryable after restart.
This is not a complete persistence audit of uploads, profiles, and all releases.

### Deployment audit and environment repair

The setup job completed successfully with run `x0nzx84uwxfiywyo`.
The one-time update job `5xf4-ux59-g12t-c9j6` completed with run `1ukpllch6zrb0u0f`.
The updater checked for tracked changes, fetched the selected branch, and performed a fast-forward update to the expected commit.
It checked changed Python syntax and imported the new chat modules in the isolated environment.
The source update did not edit persistent state or credential files.

A malformed project environment value initially prevented the update job from starting.
`INFERENCE_MODEL` contained a serialized browser event object instead of a string.
CAI reported `json: cannot unmarshal object into Go value of type string`.
Only this project environment value was corrected to the documented default, `gpt-4o`.
Saved model profiles and credentials were not changed by that repair.

The earlier project-copy failure, exit status 24, remains unexplained.
The successful independent deployment does not prove that a Git submodule caused the earlier failure.

### Exposed API comparison for the local commits

The route list, the consumer OpenAPI document (16 paths), and the console OpenAPI document (161 paths) match `998904c` exactly.
The comparison used `create_app(local=True)` at both commits.
The consumer API for MCP and external agents uses no changed code.

Existing JSON responses gain only additive fields. No field is removed or renamed:

- The `/demo/api/playground/chat` result event adds `semantic_canvas` and `evaluation`.
- Document and hybrid answers from `/demo/api/playground/chat` and `/demo/api/playground/run` add `verification`.
- Agent metadata adds `tool_calls` and `stop_reason`.

## Remaining work

| Item | Next acceptance check |
| --- | --- |
| Optional external Helios | Deploy separately; verify health registration, browser identity, two-user grants, workspace linking, native building, and native chat |
| Hosted free-text chat | Run natural-language numeric and MAS document questions against configured inference; inspect results, citations, and relevance signals |
| Hosted authorization | Verify anonymous rejection, caller isolation, and the intended per-model authorization contract |
| Persistence | Check uploads, saved model connections, published versions, and provider links across restart |
| Hosted MCP / Agent Studio | Repeat the finance workflow against this exact deployment and pinned release |
| Hosted UI interaction acceptance | Complete manual browser review of materials and Studio validation; asset checks and saved-metric chat passed |
| Local UI and ontology commits | Push and deploy `6960649`–`ddd53a4`; repeat Studio, Ontology, Glossary, Validation, Materials and chat-tab checks on CAI |
| Drafts that already hold terms | Re-approve once after deployment; terms moved from the context review item to per-term items |
| UI polish and ontology | P0–P5 done locally; P6 typed term relations needs approval and a consumer and MCP compatibility check |
| Branch integration | Review and merge the fixes into `main`; this record does not claim that merge occurred |
| Later architecture work | External release import, delegated execution, and optional built-in package extraction |

The sibling Helios checkout was synchronized with upstream commit `72818c4` and merged locally as `3a46e18`.
The sibling AMP branch was pushed on 5 November 2026 at `0127f3b`. The Hub deployment does not depend on that checkout.

### Standalone Helios AMP preparation: 5 November 2026

The sibling checkout now has an AMP package on published branch `feat/standalone-amp`, commit `0127f3b`.
Upstream main was fetched again on 5 November at `72818c4`; the AMP branch contains that revision.
One authenticated Helios Application serves its native UI and API; Hub can use that origin for both provider settings.
The package includes isolated Python setup, a checksum-pinned Node build, native admin setup, and a kernel-preserving launcher.
Python 3.12 setup, production UI build, native imports, temporary metadata migration, and 13 packaging tests passed locally.
Native browser, fixture identity/grant, and graceful shutdown checks passed.
The upstream UI build reported 14 npm advisories, including one critical advisory.
The package is pushed but not deployed. Live CAI launch, SSO, persistence, native query, and Hub registration checks remain pending.
See the [standalone integration guide](standalone-helios.md).

Use the [live-test runbook](live-test-runbook.md) for acceptance and the [operator guide](amp-operator-guide.md) for startup and retry procedures.
Use the [local preview guide](local-preview.md) for development checks.
Earlier plans and dated reviews retain their historical evidence; this record supersedes their current-status statements.
