# Semantic Hub: agent handoff

## Current status

Recorded 3 November 2026. Read the [project status](docs/semantic-hub-v2/project-status.md) before changing deployment or reporting readiness.

- Active branch: `fix/amp-provider-bootstrap`.
- Deployed application commit: `cc4890e9022f49ef68cd8523424c011537696460`.
- The branch is pushed to the `semantic-hub` remote. These fixes are not recorded as merged into `main`.
- The independent Hub AMP runs in CAI. Its latest restart and authenticated HTTP checks passed.
- Live saved-metric execution returned **SGD 686,572.96** for finance `v1.0`.
- Separate-project Helios acceptance and live free-text chat verification remain pending.
- UI commits `9c1acb1` to `4929695` are pushed and deployed in `cc4890e`.
  They add the answer canvas, per-answer checks, harness stop reasons, the materials cleanup, and the validation summary.
- The 23:28 Singapore restart passed seven UI asset comparisons and a live finance query with a canvas and 6/6 answer checks.
- Four later commits, `6960649` to `a01c33a`, are local only. They are not pushed or deployed.
  They give the materials stages consistent spacing, restyle the semantic canvas, and compact the Studio and Validation pages.

This is a dated handoff, not a continuous health check. Verify current Git and application state before deploying.

## Repository and architecture

The project remote is `semantic-hub`, at `https://github.com/FerdinandZhong/semantic-hub.git`.
The `origin` remote points to the older Helios fork. Check remote destinations before pushing.

```text
Hub AMP -> setup job -> Hub application -> built-in Studio and chat
                              |
                     optional endpoint checks
                              |
                     separate Helios API + UI
```

The active AMP never clones, installs, starts, or upgrades Helios.
The manifest has three tasks: create setup job, run setup job, and start Hub.
Optional Helios registration requires both configured endpoints to pass health checks.
Registration supports navigation; external release import and delegated execution remain planned.
Preserve existing provider links during outages and `builtin_only` restarts.
Legacy bundled scripts and the ignored `external/helios` checkout are not the current AMP deployment path.

## Important code locations

| Area | Location |
| --- | --- |
| AMP tasks and setup | `.project-metadata.yaml`, `cai_integration/setup_environment.py` |
| Hub application launcher | `deployment/launchers/hub.py` |
| External provider registration | `deployment/cai/connect_external.py` |
| Unified workspace UI | `semantic_hub/web/` |
| Built-in Studio and streaming transport | `apps/helios/console/` |
| Checked chat orchestration, answer canvas, and answer checks | `shared/helios_core/demo/chat.py` |
| Agent harness, tools, and budget | `shared/helios_core/demo/agent/` |
| Document answer verification | `shared/helios_core/demo/document_answers.py` |
| Supporting materials UI | `apps/helios/console/static/demo-materials.js` |
| Provider and deployment tests | `tests/providers/`, `tests/amp/` |
| Chat regression tests | `apps/helios/tests/test_chat.py` |

## Implementation and verification rules

1. Keep the workspace cards as the first page and the built-in editor within the main UI.
2. Preserve explicit publication, pinned context, source identity, and query execution checks.
3. Show actual progress events without invented progress percentages.
4. Describe retrieval scores as relevance signals, not calibrated confidence.
5. Do not assign a retrieval confidence score to direct saved-metric selection.
   Answer checks report pass, fail, or warning counts from real checks. Do not add an LLM judge.
6. Distinguish live queries, local browser checks, and mocked inference tests in reports.
7. Preserve state, uploads, saved profiles, and encryption keys during source updates.
8. Never commit credentials or reuse provider health credentials for user workspace authorization.
9. Run targeted tests for changed behavior and record their scope.
10. Update the project status after deployment or acceptance changes.

The agent uses the DeepSeek Harness SDK with 12 tool calls or 120 seconds per turn.
Rejected calls return feedback and stay retryable. Repeated successful calls are rejected.
Each result records `tool_calls`, `stop_reason`, and the tool trace.

Chat history currently lasts only for the browser page session.
Each question is planned independently; persistent conversations and contextual follow-up inference are not implemented.

Use short, active sentences in technical explanations. Put the answer first.
Use numbered steps for procedures and ASCII diagrams for processes with more than three parts.

## Operational references

- [Current project status and remaining checks](docs/semantic-hub-v2/project-status.md)
- [UI polish and ontology plan](docs/semantic-hub-v2/ui-ontology-plan.md)
- [AMP operator guide](docs/semantic-hub-v2/amp-operator-guide.md)
- [Live acceptance runbook](docs/semantic-hub-v2/live-test-runbook.md)
- [Local preview and test commands](docs/semantic-hub-v2/local-preview.md)
- [Standalone Helios](docs/semantic-hub-v2/standalone-helios.md)
