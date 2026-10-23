# Provider contract proposal

Status: proposed interface, not an existing Helios API specification.
Implement the first provider adapter against observed native APIs and verified deployment behavior.

## Capability model

A provider supplies one or more independent capabilities.
Building a semantic model does not imply query execution support.

| Capability | Contract | Initial Helios treatment |
| --- | --- | --- |
| `launch_builder` | Return an allowed UI URL with native workspace context | Use existing model/discovery/canvas routes. |
| `launch_query` | Return an allowed native chat URL | Use the Talk route; label native revision behavior. |
| `list_models` | Return authorized provider model references | Adapt the model collection API after identity verification. |
| `list_releases` | Return published revision references and provenance | Native version listing needs publication evidence enrichment. |
| `export_release` | Return immutable native artifacts plus verified metadata | Requires an additional export contract or provider-owned bridge. |
| `read_evidence` | Return authorized evidence attached to a pinned release | Enable only if evidence identity, access, and revision semantics are verified. |
| `resolve_query` | Bind question and scope to an exact accepted revision | Requires adapter-specific compatibility work. |
| `execute_query` | Execute against the same revision, source bindings, and principal | Requires proven native execution/delegation contract. |

A capability remains disabled until its acceptance tests pass.
A link-only provider needs no automated access to remote artifacts.
A format-only importer may expose context without any execution capability.

## Provider registration

Example configuration, with placeholder origins:

```json
{
  "provider_id": "helios-primary",
  "kind": "helios",
  "adapter_version": "1.0",
  "ui_origin": "https://helios-ui.example.invalid",
  "api_origin": "https://helios-api.example.invalid",
  "mcp_url": null,
  "credential_ref": null,
  "capabilities": ["launch_builder", "launch_query"],
  "compatibility_status": "links_only"
}
```

The nullable MCP URL must be set from the deployed service, not inferred from the UI origin.
Credential references point to protected server-side storage.
Registration records the allowed origins, supported contract range, owner, and last successful compatibility check.
Administrative configuration cannot grant users permissions they lack in the provider.

## Project and model binding

The Hub stores an immutable provider reference for each accepted release.
A project can change its default builder only through an explicit migration decision.

```json
{
  "hub_project_id": "finance",
  "provider_id": "helios-primary",
  "external_organization_id": "native-org-id",
  "external_model_id": "native-model-id",
  "builder_mode": "external",
  "integration_status": "linked"
}
```

The same external model ID from two providers represents two distinct identities.
Use `(provider_id, external_organization_id, external_model_id)` as the qualified external identity.
Existing built-in IDs retain their public aliases.

## Release envelope

This is a proposed stored contract, not a payload accepted by current endpoints.

```json
{
  "contract_version": "semantic-hub.release.v2",
  "hub_model_id": "finance",
  "hub_release_id": "immutable-hub-release-id",
  "provider_id": "helios-primary",
  "external_model_id": "native-model-id",
  "external_revision_id": "native-published-revision-id",
  "publication": {
    "state": "published",
    "published_at": "provider-publication-time",
    "publisher_ref": "provider-actor-reference",
    "evidence_ref": "verified-provider-publication-record"
  },
  "native_format": "ossie",
  "native_format_version": "provider-declared-version",
  "native_artifact_sha256": "64-hex-characters",
  "hub_context_sha256": "64-hex-characters",
  "source_bindings": [],
  "evidence_manifest": [],
  "query_provider_id": "helios-primary",
  "execution_enabled": false
}
```

Native artifact hashes and Hub envelope hashes are different values with different meanings.
The Hub verifies native bytes against their declared digest.
It computes its own digest over a canonical envelope and artifact references.
It preserves original bytes so normalization cannot hide changes in meaning.

A release import follows these steps:

1. Authenticate and authorize the caller for both Hub import and the provider model.
2. Obtain an explicit published revision and its publication evidence.
3. Fetch that revision's artifacts through the supported export interface.
4. Verify hashes, artifact limits, format version, and required source/evidence bindings.
5. Reject incomplete, unreviewed, unsupported, or inconsistent artifacts.
6. Save the immutable snapshot and its qualified provider identity.
7. Accept the release into the authorized Hub catalog.

Repeated imports of the same provider revision and digest are idempotent.
The same provider revision with different bytes is a conflict, not an update.
A later provider publication creates a new Hub candidate; it never rewrites an accepted release.
Provider revocation and Hub access changes must be reflected before further retrieval or execution.
Store review evidence and provider status without presenting them as a second Hub business review.

## Query binding

A query request must bind:

- Hub caller and authorization context.
- Accepted Hub release and exact native provider revision.
- Provider-qualified model and source identities.
- Typed query scope or provider-native validated request.
- Execution limits and an audit correlation ID.

The adapter must return the executed revision, source binding, and result provenance.
Reject a mismatched revision or a provider that cannot prove the requested pin.
A semantic revision and a live data timestamp are separate provenance fields.

If the provider supports conversational execution only, keep it behind **Talk in provider** initially.
Do not pretend its API implements the Hub's existing resolve/coverage/compile/sample-query contract.
If two-stage execution is required, implement explicit prepare and execute semantics with a checked receipt.
Do not relabel a conversation response as a prepared plan after execution already occurred.

## Error behavior

| Condition | Hub behavior |
| --- | --- |
| Provider is down | Mark remote actions unavailable; no fallback execution. |
| Authentication expires | Require supported reauthentication; do not broaden identity. |
| Permission is denied | Return denial without leaking model names or cached content. |
| No published revision exists | Keep linked/draft status; exclude from published consumer discovery. |
| Export is unsupported | Keep link-only capability. |
| Native format cannot be translated | Keep reference-only or reject import; disable typed execution. |
| Requested revision is missing | Reject execution; never substitute latest. |
| Source credentials are missing | Provider reports configuration failure; Hub does not use sample fixtures. |
| Duplicate refresh/callback arrives | Apply idempotent release import. |
| Imported revision is revoked | Disable governed retrieval/execution according to the recorded revocation policy. |

## Contract tests required before enabling capabilities

1. Link generation uses encoded IDs, approved origins, and no secrets.
2. Model discovery respects two users with different permissions.
3. Publication import rejects unreviewed fallback content.
4. Export returns stable bytes and a verifiable revision digest.
5. Reimport is idempotent; changed bytes under the same revision fail.
6. Old accepted releases remain immutable after newer provider publications.
7. Query execution returns the requested revision and correct source binding.
8. Authorization changes cannot expose stale cached results or evidence.
9. Provider timeouts, redirects, and missing capabilities fail explicitly.
10. Built-in v1 consumer behavior remains compatible.
11. An external-only Hub starts without importing builder or query-agent runtimes.
12. A second provider with only export capability works without a query implementation.

## Minimum integration spike

Use one existing published Helios model and two test principals with different access.
First verify navigation and provider-side login.
Then verify model discovery, publication metadata, immutable export, and revision-pinned execution separately.
Record exact deployed versions and API responses with secrets removed.

If export or identity delegation needs changes, implement them at the provider boundary.
Do not copy the Helios application into the Hub to bypass the missing contract.
