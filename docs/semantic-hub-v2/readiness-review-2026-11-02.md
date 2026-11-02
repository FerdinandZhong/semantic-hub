# Implementation and AMP readiness review — 2 November 2026

Decision: ready for a disposable CAI rehearsal with the prerequisites in the [live-test runbook](live-test-runbook.md).
This is not production acceptance. No cloud resources were created during this review.

## Scope and fixes

The review covered the Hub UI and consumer boundary, provider discovery, isolated launchers, AMP preparation, provisioning, and verification.
The pinned native Helios checkout remains unchanged.

| Finding | Change |
| --- | --- |
| The endpoint verifier accepted any JSON object containing `status`, including failed states | Accept only explicit `ok`, `ready`, or `healthy` statuses |
| Provisioning checked ownership and ingress settings before polling, but not on later reads | Recheck identity, ownership marker, and authenticated ingress before restart and during polling |
| Missing management configuration failed after expensive preparation | Validate project identifier, HTTPS management origin, and key before installing native packages |
| Picker ignored an operator-supplied CA bundle | Honor `SSL_CERT_FILE` while retaining TLS verification, redirect blocking, and disabled proxy inheritance |
| Operational documents contained stale provisioning and manual-ID guidance | Update current guides and add a per-file [documentation audit](documentation-readiness-audit.md) |

## Test evidence

| Suite | Result |
| --- | --- |
| `tests/amp tests/providers` | 101 passed |
| `tests/local_launcher` | 11 passed |
| Consumer API, retrieval service, and retrieval index regressions | 38 passed |
| Built-in context, Hub, connections, materials, visual materials, embeddings, and Playground agent | 118 passed |
| Workspace browser smoke | Passed; finance result SGD 686,572.96; responsive navigation; no JavaScript errors |
| Helios picker browser check | Passed; native local model link, denied/empty responses, credential cleanup, stale-response protection, return to cards |
| Chat-history browser check | Passed; conversation restore, no stale Run actions, workspace/version/hash isolation, reload clears history |

Total: 268 automated tests across the listed Python suites.
Two launcher checks initially failed because the execution sandbox denied process inspection and loopback binding.
The complete launcher suite passed with those permissions enabled.
Browser write checks used disposable Hub state and read the existing local native review model.
Lint, JavaScript syntax, documentation-relative-link, and whitespace checks passed for the reviewed changes.

## Live gates and scope limits

1. Record target CAI version, runtime identifier, quotas, trusted certificates, and disposable project ownership.
2. Verify ingress authentication and identity-header replacement before enabling bundled native Helios.
3. Verify management API compatibility, assigned origins, and recovery from partial setup.
4. Check two users' picker permissions and access revocation through actual CAI ingress.
5. Check native UI/API CORS, independent restarts, persistent credentials, and provider outages.
6. Configure approved native data and inference services before testing Helios Talk.

If the API omits application URLs, provisioning retains both application IDs and requires operator-supplied origins on retry.
Native model creation, external release import, delegated Hub/MCP queries, and external-only dependency extraction remain future work.
The Hub catalog remains shared among authorized application users; linking a model grants no native access.
Use the exact reviewed Git revision for the rehearsal. A local commit must be published or transferred before a remote AMP import can use it.
