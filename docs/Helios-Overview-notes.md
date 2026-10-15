# Reading the Helios overview deck

The [66-slide overview](Helios-Overview.pptx) is an architectural and product-story reference.
Its slide text was inspected during the documentation audit on 12 October 2026.
It is not a current walkthrough of local Semantic Hub and Studio.

Before presenting it as the current implementation:

1. Update slide 16's seven-tool statement and slide 35's MCP tool list.
2. Replace slide 36's `search_semantics → describe → run_query` flow with the current bounded workflow.
3. Use the [current builder guide](context-builder.md) for local navigation, document evidence, and approval.
4. Verify research citations and numerical claims separately before external reuse.

```text
discover_models → resolve_context → validate bundle → compile/run → result evidence
```

The conversation exposes five query tools, described in [MCP documentation](mcp-server.md).
Other MCP endpoints are separate capabilities, not automatically available to that conversation.
The audit did not revalidate the deck's literature statistics or regenerate slide images.
See [documentation alignment](DOCS_ALIGNMENT.md) for the implementation mapping.
