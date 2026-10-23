# Documentation ownership cleanup

Completed on the v2 branch on 23 October 2026.

## Result

The Helios provider is now a Git submodule at `external/helios`, pinned to `316f5d89926f96d366afaee641bd923af4ca6bf3`.
Its upstream documentation is authoritative for that provider.
The submodule contains no Hub-specific edits.

Thirteen byte-identical upstream documents were removed from the Hub's root documentation directory.
References now point to their copies in the provider checkout.
Fourteen locally modified guides were relocated to `docs/builtin/helios-compat/`.
These describe the inherited local implementation, including its stricter MCP publication and retrieval contracts.
Their content is preserved, with relative links adjusted for the new paths.

Hub guides, architecture diagrams, Agent Studio instructions, sample workflows, and v2 plans remain in `docs/`.
The independent transformation use case remains in its own directory.
Historical handoff copies and verification evidence were not rewritten.

The [ownership manifest](../documentation-ownership.json) records original paths, destination paths, Git blob IDs, and content hashes.

## Documentation readers

The local UI documentation generator and navigation assistant use the relocated sources.
The UI generator includes provider guides when the submodule is initialized.
It skips optional provider guides when the checkout is absent, preserving Built-in-only documentation builds.
The provider's own documentation generator remains unchanged.

Initialize the checkout from the repository root when needed:

```sh
git submodule update --init external/helios
```

Do not use `--remote` during reproducible setup; use the revision pinned by the parent repository.

## Verification

- All 27 ownership entries resolve to existing files.
- Thirteen upstream copies match their former Hub copies byte for byte.
- Fourteen local guides retain their text, apart from relative-link destinations.
- Index links and relative links in the relocated compatibility guides resolve.
- The UI documentation generator produces 20 pages with the provider checkout.
- An isolated build without that checkout produces 15 local pages.
- Navigation assistant tests pass: 17 tests in 2.22 seconds.
- The Helios submodule is clean and matches the recorded revision.
- `git diff --check` passes.

The assistant suite required an explicit shared-module path and temporary Helios state.
The package-local pytest path otherwise shadows the MCP SDK, and the default console state targets `/home/cdsw`.
No runtime source changes were needed for those test-harness conditions.

This completes documentation separation and the pinned checkout only.
Provider runtime isolation, provisioning, release export, and delegated query work remain in the [implementation plan](implementation-plan.md).
