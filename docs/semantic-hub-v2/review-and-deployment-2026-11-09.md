# P0–P6 review and CAI deployment: 9 November 2026

The reviewed changes are pushed and deployed at `17d03b96b44a0e8598a2c0143765ac91f2b9d6a2`.
The branch remains `fix/amp-provider-bootstrap`; it is not merged into `main`.
The current MCP adapter remains compatible. No MCP configuration change is required.

## Review finding and correction

**Publication review blocker, fixed:** relation review IDs concatenated unescaped names with `|`.
Two valid relations could produce the same ID:

- `Alpha|related` → `related` → `Beta`
- `Alpha` → `related` → `related|Beta`

Both produced `relation:Alpha|related|related|Beta`.
One relation disappeared from the review map, so independent approval was not enforced.
Commit `17d03b9` URL-encodes each component before joining it.
The regression also covers a literal `%7C` in a term name.
It confirms that a pending relation blocks final review until every required item is approved.

The correction changes review identifiers, not published relation payloads or graph formats.
Existing approval decisions for affected names can require approval again.
The normal `Alpha`/`Beta` relation ID remains unchanged.

## MCP compatibility

The deployment changes no MCP adapter code or consumer routes.
A nonempty relation list appears as the optional `definition.term_relations` property.
Definitions without relations omit that property.
Relations do not yet become graph edges in published Helios artifacts or Memgraph.
No new graph retrieval behavior is claimed.

The actual stdio adapter passed all 12 tools against three targets:

| Target | Result |
| --- | --- |
| CAI before update | 12 tools passed; finance total SGD 686,572.96 |
| Local published finance fixture with a typed relation | 12 tools passed; relation returned in definition; same total |
| CAI after restart | 12 tools passed; same existing release and total |

The calls covered status, models, versions, lineage, documents, keyword search, coverage, resolution, compilation, and query execution.
These checks performed no model writes or generation LLM calls.
Tool schemas hashed identically across all three runs:
`2a6e202f1d3f00a0e71a872e91b25122f937f0ea5a87b0c0375ae377b8af571f`.

The consumer OpenAPI hash stayed unchanged:
`77f6f7b96982dcf1269c642105605cbbd6f1ea5bc59d0f5b4c9a8a635f97fc8e`.
The stored finance `v1.0` release retained its context hash:
`ca2348d85fa8b76d3c555bbb631d2f3c1bb0610f216a6ff6e86b28c856a5269f`.
Every returned release field matched its pre-update hash, including definition, semantic model, metadata, and ontology.
This compares one existing release before and after deployment, not independently generated releases.

## Verification scope

| Check | Result | Limit |
| --- | --- | --- |
| Targeted context, glossary, relation, artifacts, materials, consumer, and provider suites | 120 passed | Run before adding the collision regression |
| Complete relation suite after the fix | 11 passed | Includes independent approval regression; overlaps the earlier suite |
| MCP adapter suite | 15 passed | Includes actual stdio and loopback HTTP transport |
| Local browser | Passed | Disposable state; relation create/save/reload/review display and Ontology edge; editor widths 1440/390; saved-metric chat and history |
| Hosted browser | Passed; no JavaScript page errors | Source data, Studio, Ontology, Validation, Versions at 1440/390; chat details and restored canvas at desktop; materials page loads |
| Hosted assets | All 10 matched reviewed source | Includes server-generated editor JavaScript |
| Hosted health, Swagger, consumer OpenAPI | HTTP 200 | Authenticated requests |
| Hosted finance query | SGD 686,572.96; 6/6 answer checks in browser | Saved metric; no free-text inference |

The test suites overlap; their totals must not be added into a unique test count.
The earlier reported 155-test P6 run remains historical evidence, not a new full-suite run.
Hosted browser checks did not change drafts, approve items, or publish versions.
They did not recheck Overview alignment, phone chat, or detailed materials analysis controls.

## Deployment record

| Item | Value |
| --- | --- |
| Previous application commit | `cc4890e9022f49ef68cd8523424c011537696460` |
| New application commit | `17d03b96b44a0e8598a2c0143765ac91f2b9d6a2` |
| Update job | `q51j-mc20-szu2-oyen` |
| Update run | `w0rb0z0mvlwk7uo8` |
| Update result | `ENGINE_SUCCEEDED`; report verified the target commit |
| Restart | 9 November 2026, 06:26:06 UTC / 14:26:06 Singapore |
| Application result | `APPLICATION_RUNNING` |

The updater used a fast-forward merge and checked imports before restart.
It preserved persistent state, uploads, profiles, and credential files.
No project environment repair or dependency reinstall was required.
Documentation commits after this application revision do not require another application restart.

[Open the Hub application](https://semantic-hub-yjs4ct.ml-7ca67a86-1f3.qzhong-a.a465-9q4k.cloudera.site).
Credential-free endpoint hashes and tool results are saved in [verification evidence](verification/2026-11-09.json).

## Remaining acceptance

Live relation authoring and publication must still be exercised in a disposable CAI workspace.
Separate-project Helios acceptance, live free-text inference, caller isolation, and full persistence checks remain pending.
The actual MCP adapter passed; the hosted Agent Studio workflow itself was not executed in this run.
See the [live-test runbook](live-test-runbook.md) for these checks.
