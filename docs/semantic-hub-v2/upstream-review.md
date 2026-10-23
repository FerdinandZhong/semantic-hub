# Helios upstream inspection and integration baseline

Inspected on 23 October 2026.
This report records source inspection and local regression evidence, not a live deployment certification.

## Repository identity and merge result

| Reference | Verified value |
| --- | --- |
| Original upstream | `https://github.com/Christopheraburns/helios.git` |
| Existing fork remote | `origin` → `https://github.com/FerdinandZhong/helios.git` |
| Hub remote | `semantic-hub` → `https://github.com/FerdinandZhong/semantic-hub.git` |
| Added upstream remote | `upstream` → original Helios repository |
| Upstream main | `316f5d89926f96d366afaee641bd923af4ca6bf3` |
| Upstream commit | `Crawler mapping editor added`, 8 October 2026 |
| V2 branch | `design/semantic-hub-v2-providers` |
| Relationship after cleanup | 19 local-only commits, zero upstream-only commits |
| Merge result | `git merge upstream/main` → `Already up to date.` |

GitHub repository metadata confirms that `FerdinandZhong/helios` is a fork of `Christopheraburns/helios`.
The original upstream and the existing fork currently point to the same main revision.
A direct `git ls-remote upstream refs/heads/main` check confirmed the fetched SHA.
No source conflict resolution or new upstream code was required.
No artificial merge commit was created.

## Cleanup commits before branching

| Commit | Scope |
| --- | --- |
| `ad0fe72` | Updated Hub diagrams, context build flow, generators, and technical documentation |
| `94ed301` | Separate self-service transformation use case and technical walkthrough |
| `94453d7` | Ignore local agent state and stop tracking macOS metadata |

The previous branch remains `observability_semantic_context` at the cleanup baseline.
Local agent state and the local `.DS_Store` file were preserved on disk.
No push or remote deployment was performed for this task.

## What upstream already contains

| Capability | Source evidence | Integration consequence |
| --- | --- | --- |
| Model-scoped UI | [App routes](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/ui/src/App.tsx), [navigation context](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/ui/src/components/PrimaryNavigation.tsx) | Build links with native organization/model IDs. |
| Review and publication | [Console API](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/console/api.py) | Reuse the provider's review UI instead of duplicating review logic. |
| Crawler settings and mappings | [Crawler API](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/console/crawler.py), [ontology API](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/console/ontology.py) | Keep discovery, extraction, mappings, and ontology authoring in Helios. |
| Data source management | [Data source API](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/console/data_sources.py) | Provider owns connections and source credentials. |
| Talk to Your Data | [Conversation service](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/console/conversation.py) | Reuse native conversation behavior first. |
| Remote query tools | [MCP server](https://github.com/Christopheraburns/helios/blob/316f5d89926f96d366afaee641bd923af4ca6bf3/apps/helios/mcp/server.py) | Possible execution integration after publication, identity, and revision checks. |

These features are already present in the Hub repository's ancestry.
The Hub's current demo UI does not expose the full native Helios experience.
A lack of features in that demo UI does not establish missing upstream commits.

## Verified API and UI surfaces

The paths below come from the inspected source.
Their deployment base URLs and ingress behavior remain unverified.

| Operation | Existing surface | Limitation |
| --- | --- | --- |
| Discover authorized models | `GET /api/v1/models` | Requires authenticated provider principal and model access. |
| Model lifecycle summary | `GET /api/v1/models/{model_id}/overview` | Not a portable release package. |
| Native version listing | `GET /api/v1/models/{model_id}/versions` | Returns model version IDs and actions, not full immutable bytes. |
| Semantic identity | `GET /api/v1/models/{model_id}/semantic` | Returns model ID, semantic model ID, and available actions. |
| Review | `GET /api/v1/models/{model_id}/reviews/{run_id}` | Authoring workflow belongs to Helios. |
| Publish reviewed content | `POST /api/v1/models/{model_id}/reviews/{run_id}/publish` | Returns a manifest; local artifact paths are not downloadable Hub URLs. |
| Start a conversation | `POST /api/v1/models/{model_id}/conversations` | Runs a turn and stores the conversation; not a prepare-only endpoint. |
| Append a conversation turn | `POST /api/v1/models/{model_id}/conversations/{conversation_id}/turns` | Uses provider conversation state and expected version. |
| Crawl | `POST /api/v1/crawler/runs` | Specific discovery operation, not a universal remote builder-job API. |
| Open model | `/model-overview?organization=<id>&model=<id>` | UI route and context exist; verify deployed routing. |
| Open builder views | `/models?organization=<id>&model=<id>` or `/canvas?organization=<id>&model=<id>` | Different views of discovery and model review. |
| Open Talk | `/talk?organization=<id>&model=<id>` | Native model context, not a verified historical revision selector. |

Identifiers must be encoded with a URL builder.
Launch URLs contain no tokens or source credentials.
The query parameters above are native navigation parameters; callback and pinned-release parameters are not assumed to exist.

## Gaps that the adapter must address

### Portable publication export

The inspected `/semantic` and `/versions` routes are insufficient for complete release import.
A publication manifest includes revision identity and hashes, but artifact paths are local to Helios.
Add or negotiate an authenticated immutable export operation in Helios or a provider-owned integration service.
Do not mount its filesystem into the Hub or interpret an artifact path as a remotely accessible URL.

### Published-only semantics

Upstream `ModelStore.sources()` falls back to the latest proposal when no published model is available.
The fallback explicitly identifies its status as `proposed (unreviewed)`.
The Hub must never accept that fallback as a published release.

The Hub branch already tightens MCP publication and bounded-retrieval behavior beyond this upstream revision.
Therefore the Hub's local MCP implementation must not be treated as evidence of the deployed upstream contract.
Inspect upstream source and deployed capabilities separately.

### Identity

The console's `principal_from_request()` reads trusted Workbench identity headers.
Conversation service calls use a bearer token plus a signed `X-Helios-Principal-Assertion` for MCP delegation.
A Hub credential cannot simply replace the business user's native identity.
The integration spike must prove the supported trust boundary and per-model permissions on the actual deployment.

### Exact revision and execution behavior

The conversation service attempts to establish a published revision internally.
Its public conversation request is not a generic Hub release-pin contract.
The adapter needs a verified method to execute the exact accepted revision and report that identity.
Native conversation execution is not equivalent to the current Hub Playground's checked-plan plus explicit Run flow.

### CAI deployment composition

The user plans independently running CAI applications.
Upstream contains Workbench application architecture and separate API/UI/MCP surfaces.
The inspected upstream revision does not contain this Hub's root `METADATA.yaml` or `cai_integration/application.py` deployment wrapper.
Do not assume the separately deployed Helios AMP uses the same launcher, routes, or state configuration.

## Verification performed

- Fetched `origin`, `semantic-hub`, and the original `upstream` main refs.
- Verified original fork ancestry using GitHub repository metadata.
- Verified the upstream main SHA directly with `git ls-remote`.
- Executed the upstream merge on the new branch; it required no changes.
- Parsed diagram generators and checked editable diagram connector references before cleanup commits.
- Ran `git diff --check` for pending documentation and generator work.
- Ran the current built-in consumer and retrieval regression suites: **38 passed in 28.34 seconds**.

Regression command:

```sh
.venv-semantic-hub/bin/python -m pytest \
  apps/helios/tests/test_semantic_hub_consumer.py \
  apps/helios/tests/test_retrieval_service.py \
  apps/helios/tests/test_retrieval_index.py -q
```

No hosted Helios application was contacted, and no user records or deployed state were modified.
No remote provider authentication or release export test is claimed here.
