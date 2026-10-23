# Built-in Helios compatibility guides

These guides describe Helios code inherited and modified by this Semantic Hub repository.
They are Hub-owned documentation, not documentation for the independently deployed upstream Helios provider.

The local MCP, retrieval, and conversation contracts differ from upstream.
Keep these guides while the current implementation remains supported.
Do not copy them into the upstream submodule or assume they describe that provider's API.

For the provider itself, use [upstream Helios documentation](../../../external/helios/README.md).
For the current Hub experience, use the [Hub documentation map](../../README.md).

| Area | Local compatibility guide |
| --- | --- |
| Discovery workflow | [Walkthrough](helios-walkthrough.md), [runs](console-runs.md), [proposals](console-propose.md), [review](console-review.md) |
| Query and security | [MCP](mcp-server.md), [conversation](talk-to-your-data-architecture.md), [security](SECURITY_ARCHITECTURE.md) |
| Interfaces | [UI/API contract](ui-backend-contract.md), [graph API](model-graph-api.md) |
| Operations | [Deployment](ui-deployment.md), [networking](ui-api-networking.md), [metadata](operational-metadata.md) |
| Design history | [UI migration](legacy-ui-migration.md), [ontology proposal](ontology-authoring.md) |

Original paths and content fingerprints are recorded in [the ownership manifest](../../documentation-ownership.json).
The migration preserves document content and adjusts relative links for the new location.
