# HERMES Run Inspector PRD

Date: 2026-05-10
Status: Draft for implementation planning
Owner: Product Manager skill
Source outputs: `D:/product-manager/evals/results/T8-with-skill.md`, `D:/product-manager/evals/results/T3-with-skill.md`

## Decision Summary

Build **HERMES Run Inspector** first.

The first milestone should be a privacy-safe, read-only run snapshot contract plus one local operator surface. It should answer:

- What is running?
- What is stuck?
- What tool or MCP server is involved?
- What data is safe to show?
- What should the operator do next?

This should ship before deeper unattended orchestration or skill evaluation UI because those capabilities need reliable runtime visibility to be trusted and debugged.

## Target User And Workflow

Primary users:

- HERMES operators running long-lived CLI, gateway, ACP, or MCP-backed agent sessions.
- Agent builders debugging tool/MCP failures.
- PMs/evaluators validating whether an agent task is stuck, blocked, unsafe, or recoverable.

Current workflow:

- User sees that HERMES is slow, stuck, waiting, rate-limited, or failing.
- User must inspect logs, process state, gateway health, MCP details, and tool traces separately.
- Sensitive data can leak if raw prompts, tool arguments, logs, or file contents are copied into debug output.

Desired workflow:

- User runs one status command or queries one read-only API.
- HERMES returns a structured snapshot with run identity, state, last activity, active tool, MCP health, recovery hint, and privacy flags.
- Missing data is marked `unknown` or `degraded`, not guessed.
- The snapshot is safe to share by default.

## Source Evidence Map

| Source | Evidence Read | Product Pattern | HERMES Implication | Not To Copy |
| --- | --- | --- | --- | --- |
| `graykode/abtop` | Sessions include status, model, tokens/context, child processes, tool calls, file audit, pending/thinking timestamps | Runtime visibility should be structured, not log-only | Define a HERMES run snapshot contract | Rust/TUI stack or btop layout |
| `graykode/abtop` | Local privacy stance: show metadata, avoid prompt/file contents, redact tool inputs | Observability must have a privacy budget | Default snapshot must be redacted and local-safe | Raw transcript tails |
| HERMES via GitNexus | `gateway/status.py`, `hermes_cli/web_server.py:get_status`, `/health/detailed` tests | HERMES already has gateway/platform health surfaces | Extend current status paths rather than create a parallel status store | Duplicating status storage |
| HERMES via GitNexus | `MCPServerTask`, MCP dynamic discovery tests, MCP registration tests | MCP lifecycle is internally observable | Surface MCP server health, refresh failures, and affected tools | Exposing raw MCP payloads |
| HERMES via GitNexus | `ToolRegistry`, `ToolEntry`, tool progress/call paths | Tool availability and dispatch already have central contracts | Add read-only tool summary and active tool state | Dispatching or mutating tools during inspection |
| HERMES via GitNexus | `agent/redact.py`, Langfuse usage/cost hooks | HERMES has redaction and optional tracing pieces | Unify local privacy-safe observability before external export | Requiring Langfuse or cloud tracing |
| `openai/symphony` | Run status, workspace isolation, retries, status surface | Long-running work needs state and handoff | Run Inspector should become prerequisite for later orchestration | Full Symphony daemon |
| `Lucasmantou/phoenix-immortal` | Failure review and checkpoint/retry/report discipline | Failures should become future evals and guardrails | Add failure review to execution contract | Treating conceptual docs as implemented code |

## Current HERMES Reality

Evidence from GitNexus indicates HERMES already has useful building blocks:

- Web and gateway status surfaces such as `hermes_cli/web_server.py:get_status`.
- Detailed health endpoint tests around gateway/platform health.
- MCP server lifecycle and dynamic discovery tests.
- Tool registry and tool dispatch contracts.
- Optional observability/tracing hooks.
- Redaction utilities.
- Eval environments and benchmark-style tests.

Current gap:

HERMES has pieces of status, health, tool tracing, MCP lifecycle, and redaction, but not a single user-facing run inspector contract that explains a live run's state, risk, blockage, and next recovery action.

## Goals

- Make active and recently completed HERMES runs diagnosable without reading raw logs.
- Keep milestone 1 read-only and additive.
- Preserve privacy by default.
- Reuse existing status/API/tool/MCP surfaces where possible.
- Create a contract that later orchestration, skill evaluation, and dashboards can consume.

## Non-Goals

- No new scheduler.
- No automatic retry orchestration in milestone 1.
- No full abtop-style TUI.
- No full Symphony-style issue daemon.
- No GitNexus code graph product surface.
- No raw prompt, file body, secret, or full tool argument display.
- No durable schema migration unless explicitly accepted after design review.
- No required Langfuse or cloud tracing dependency.

## Requirements

### P0: Versioned Run Snapshot

HERMES must expose a versioned read-only snapshot:

```yaml
version: 1
run_id: string
source: cli | gateway | acp | mcp | eval | unknown
status: starting | thinking | executing_tool | waiting_input | waiting_approval | rate_limited | recovering | completed | failed | stopped | unknown
reason: string | null
workspace: string | null
session_id: string | null
last_activity_at: string | null
active_tool:
  name: string | null
  call_id: string | null
  duration_ms: integer | null
mcp_health: []
recovery_hint: string | null
privacy_flags: []
degraded_reason: string | null
```

Acceptance:

- Snapshot exists even when some fields are unknown.
- Missing or corrupt state returns `status: unknown` or `degraded_reason`, not an exception.
- Snapshot is read-only.

### P0: Privacy And Redaction

Default output must not expose:

- Raw prompts.
- Full tool arguments.
- File contents.
- Secrets or tokens.
- Raw logs.
- Attachment contents.

Acceptance:

- Secret-like values are redacted in nested structures.
- Tool arguments are summarized by type, key names, count, or size.
- Snapshot fields can be classified as `safe`, `redacted`, `local_only`, or `unknown`.

### P0: Status Taxonomy

Run state must distinguish:

- `thinking`
- `executing_tool`
- `waiting_input`
- `waiting_approval`
- `rate_limited`
- `recovering`
- `completed`
- `failed`
- `stopped`
- `unknown`

Acceptance:

- Rate-limit state is not confused with waiting for user input.
- Approval waiting is visible without exposing private approval payloads.
- Completed and failed states include final reason when available.

### P0: Tool And MCP Health Summary

Snapshot must summarize:

- Active tool name and duration when known.
- Tool availability state.
- MCP server connected/degraded/unknown state.
- Last MCP error class when known.
- Affected tools when known.

Acceptance:

- Inspector does not dispatch tools, reconnect MCP servers, or refresh remote state.
- MCP failures are shown as health facts, not raw payloads.

### P0: Operator Surface

Milestone 1 must expose the snapshot through at least one local operator surface:

- CLI command, or
- existing local API/status endpoint.

Acceptance:

- A user can request current status without starting, stopping, retrying, or resuming a run.
- Output includes recovery hint and degraded-state explanation when data is incomplete.

### P1: Resource Pressure

When available, expose safe metadata:

- Token totals.
- Context pressure.
- Cost estimate.
- Quota/rate-limit state.
- Active child process count.
- Open port count.

Acceptance:

- Missing resource data is `unknown`, not guessed.
- P1 resource fields must not block P0 release.

### P1: Runtime Event Stream

Runtime events should later include:

- Run state transition.
- Tool call start/end/failure.
- MCP health change.
- Approval requested/resolved.
- Redaction failure.
- Recovery hint emitted.

Acceptance:

- Event stream design does not require milestone 1 to store full history.

### P2: Exporters And Dashboard

Later milestones may add:

- Web/TUI panels.
- Langfuse/OpenTelemetry export.
- Historical run buffer.
- Stop/retry/resume actions behind preflight and approval.

## Metrics

- 95% of local test runs produce a valid snapshot.
- No known secret patterns appear in snapshot tests.
- Status command returns within 500 ms on local fixture data.
- A tester can answer "what is running and what is stuck?" within 30 seconds.
- No runtime behavior changes are introduced in milestone 1.

## Acceptance And Evaluation

| Case | Scenario | Pass Signal |
| --- | --- | --- |
| E1 | Normal running agent with no active tool | Snapshot shows `thinking` or equivalent active status with last activity |
| E2 | Agent executing a tool | Snapshot shows `executing_tool`, tool name, call id if available, duration |
| E3 | Approval prompt is pending | Snapshot shows `waiting_approval` without raw approval payload |
| E4 | MCP server is degraded | Snapshot shows server state, last error class, affected tools if known |
| E5 | Secret-like tool args exist | Snapshot contains redacted summary only |
| E6 | Session/resume state missing or corrupt | Snapshot returns degraded state, not crash |
| E7 | Context pressure is unknown | Snapshot marks field unknown without guessing |
| E8 | Local status command called repeatedly | No mutation, no tool dispatch, no MCP refresh |

## Delivery Slices

| Slice | Outcome | Type | Depends On |
| --- | --- | --- | --- |
| T1 | Versioned run snapshot schema exists | AFK | none |
| T2 | Session/resume state maps into snapshot | AFK | T1 |
| T3 | Tool and MCP health summarize safely | AFK | T1 |
| T4 | Redaction/privacy tests protect output | AFK | T1, T2, T3 |
| T5 | Local status surface exposes snapshot | AFK | T2, T3, T4 |
| T6 | Failure review captures blocked/failed implementation cases | AFK | T1-T5 |

## Risks

- Snapshot accidentally exposes sensitive data.
- Read-only inspector mutates runtime by reconnecting or refreshing MCP.
- Snapshot status taxonomy conflicts with existing gateway/platform status names.
- Adding API fields breaks clients if done without versioning.
- Tests depend on non-existent paths if HERMES structure changes before implementation.

## Open Questions

- Which surface owns milestone 1: CLI, API, TUI, or gateway message?
- What run identifier is stable across CLI, gateway, ACP, and MCP sessions?
- Should token/context pressure be P0 if it already exists in reliable code paths?
- Should P0 include active child process or open port count, or defer to P1?
- Should snapshots be current-only or include a short in-memory event buffer?

## HERMES Execution Contract

Implementation handoff is captured in:

`.hermes/task.yaml`
