# HERMES Run Inspector Desktop Panel Requirements Register

Date: 2026-05-11
Status: Requirements and issue register before PRD
Owner: Product Manager skill
Related PRD: `docs/plans/hermes-run-inspector-prd.md`

## Purpose

This register organizes the requirements, risks, source evidence, issue evidence, and open questions for a HERMES desktop-facing Run Inspector panel.

It exists before implementation so the next PRD and `.hermes/task.yaml` slice do not miss the failure modes seen in adjacent desktop and web UI projects.

## Current Decision

Build the next milestone as an **observer-first Run Inspector panel**, not a full desktop installer or full desktop control center.

The first useful panel should help a HERMES operator answer:

- Is HERMES running, stuck, waiting, failed, or degraded?
- Which session or run is involved?
- Which tool or MCP server is active or unhealthy?
- Is gateway/session state available?
- What is safe to copy into a support or debugging report?
- What should the operator do next?

## Evidence Map

| Source | Code Evidence Read | Issue Evidence Read | HERMES Decision |
| --- | --- | --- | --- |
| `hermes-agent` | `hermes_cli/web_server.py:get_status`, `hermes_cli/main.py:cmd_dashboard`, `web/src/hooks/useSidebarStatus.ts`, `web/src/components/SidebarStatusStrip.tsx`, `web/src/pages/SessionsPage.tsx`, `web/src/pages/ChatPage.tsx` | Existing HERMES dashboard packaging issues were noted separately, but this register focuses on desktop panel input projects. | Add a read-only Run Inspector API and panel into existing dashboard surfaces before building a separate desktop shell. |
| `hermes-agent` Run Inspector P0 | `hermes_cli/run_inspector.py`, `hermes status --run-inspector`, tests for schema/session/tool/MCP/redaction/failure review | N/A | P1 UI should consume the P0 snapshot contract rather than define a parallel state model. |
| `fathah/hermes-desktop` | Electron main/preload event bridge: `onToolProgress`, `onChatToolProgress`; Gateway screen polling and start/stop controls. | #89 install stuck, #88 installed Hermes not detected, #87 Sessions infinite spinner, #85 Windows path detection hardcoded to Unix paths, #83 remote mode cannot read remote config/models, #91 macOS/API key/remote-local communication failures. | Borrow the event/progress display pattern, but do not build installer/config/gateway control into the first HERMES desktop panel. |
| `EKKOLearnAI/hermes-web-ui` | `TerminalPanel.vue` WebSocket reconnect/control handling, `ChatRunSocket`, `Job` state model, 113 API routes including sessions/jobs/gateways/logs. | #607 gateway port auto-increment and config mutation, #606 unauthenticated frontend retry loop causing 429, #598 Windows gateway management `spawn hermes ENOENT`, #587 tool call UI overflow and input readability. | Borrow run/session/job information architecture and terminal reconnect ideas, but require bounded retries, read-only config behavior, and layout constraints. |

## Problem Register

| Problem | Evidence | User Impact | Requirement Direction |
| --- | --- | --- | --- |
| Operators cannot quickly tell what HERMES is doing. | HERMES P0 needed `status --run-inspector`; dashboard status currently focuses on gateway/session summary. | Users inspect logs or guess whether HERMES is stuck. | Add a visible panel with run status, active tool, MCP/tool health, gateway/session state, and recovery hint. |
| Desktop-style apps easily get trapped in install/setup failures. | `hermes-desktop` #89, #88, #85. | User cannot reach the main product because setup blocks the UI. | P1 must not include installer ownership. If a desktop wrapper is later built, install detection must be a separate milestone. |
| Session views can hang forever when async loading fails. | `hermes-desktop` #87. | User sees an infinite spinner and loses trust. | Every panel load must have timeout, degraded state, retry, and manual refresh. |
| Gateway controls can mutate config or spiral ports. | `hermes-web-ui` #607, #598. | User config is corrupted or gateway cannot start on Windows. | First panel should be read-only for gateway. Any write action requires a later design with config-preserving writes and platform checks. |
| Unauthenticated or failing requests can retry indefinitely. | `hermes-web-ui` #606. | UI triggers rate limits and hides the real auth problem. | Stop polling on auth failure, use backoff, and surface a clear auth/degraded state. |
| Tool call UI can overflow and reduce readability. | `hermes-web-ui` #587. | Long tool names/args break layout. | Tool rows must have max widths, truncation, expandable details, and no raw argument dump. |
| Remote mode can diverge from local mode. | `hermes-desktop` #83 and #91. | Remote users cannot see models/config/state or cannot communicate with the agent. | Separate local-only data from remote-capable data and mark unsupported fields as degraded, not broken. |

## Requirements

### P1.1 Read-Only Run Inspector API

Expose a local dashboard API backed by the P0 snapshot contract.

Acceptance:

- `GET /api/run-inspector` returns the same privacy-safe fields as `hermes status --run-inspector`.
- The API never starts, stops, retries, resumes, reconnects, refreshes MCP, or writes config.
- Missing state returns `status: unknown` plus `degraded_reason`.
- Optional tool/MCP/session/gateway failures do not produce a 500 unless the API process itself is unhealthy.

### P1.2 Dashboard Panel

Add a Run Inspector panel to the existing HERMES dashboard.

Minimum visible fields:

- Run status and source.
- Session id and workspace when safe.
- Last activity time.
- Active tool name, duration, and summarized argument shape.
- MCP health summary.
- Tool health summary.
- Gateway/session availability.
- Recovery hint.
- Privacy flags and degraded reason.
- Last refreshed time and manual refresh action.

Acceptance:

- Loading state cannot spin forever.
- Empty/unknown/degraded states are explicit.
- Long tool names and summaries do not overflow the panel.
- The panel does not show raw prompts, raw logs, secrets, file bodies, or full tool arguments.

### P1.3 Sidebar Signal

Add a compact Run Inspector signal near the existing sidebar status surface.

Acceptance:

- Sidebar shows a small state signal such as running, waiting, failed, degraded, or unknown.
- Clicking the signal opens or routes to the full Run Inspector panel.
- Sidebar polling is slower or shared with panel polling to avoid duplicate load.

### P1.4 Session And Chat Entry Points

Add a diagnostic entry point from session and chat surfaces.

Acceptance:

- Sessions page can show whether the current/latest session has a run inspector snapshot.
- Chat page can link to the current run diagnostic when embedded chat is enabled.
- If no snapshot exists, the UI says so without treating it as an error.

### P1.5 Resilience Rules

The panel must be safe under failure.

Acceptance:

- Request timeout is bounded.
- Polling uses backoff after repeated failures.
- Auth failure stops polling and surfaces auth state.
- Network/server failure shows degraded state and manual refresh.
- No automatic gateway restart, config write, model refresh, or credential read happens from the panel.

### P1.6 Desktop Wrapper Constraint

If a separate desktop shell is considered later, it must start as a wrapper around the read-only panel, not as an installer/config manager.

Acceptance for later design:

- No hardcoded Unix `venv/bin/python` assumption on Windows.
- No `bash` requirement on Windows.
- Local and remote mode are explicit modes with separate capability flags.
- Config write actions are disabled until config-preserving writes are designed and tested.

## Non-Goals For First Desktop Panel Slice

- No full Electron app implementation.
- No HERMES installer.
- No provider credential manager.
- No direct `config.yaml` editor.
- No gateway start/stop/restart control.
- No automatic port reassignment.
- No terminal emulator or PTY streaming in the first slice.
- No raw transcript/log viewer inside the Run Inspector panel.
- No remote write operations.

## Risk Flags

| Risk | Trigger | Required Guardrail |
| --- | --- | --- |
| Config mutation | Any change to `config.yaml`, `.env`, profile files, gateway ports, or provider config. | Pause and require separate design. Preserve comments/order if later implemented. |
| Platform-specific execution | Any subprocess, shell, venv, Python, or Hermes binary detection. | Test Windows, WSL, macOS, Linux paths separately. |
| Infinite loading | Any async panel load or poll loop. | Timeout, backoff, explicit degraded state, manual refresh. |
| Auth retry loop | Any unauthenticated API call. | Stop polling on auth failure and route to auth state. |
| Privacy leak | Any prompt, raw tool args, file content, logs, credentials, or environment values. | Use P0 redaction/summarization and add UI tests for long/secret-looking values. |
| User-visible API contract | Adding `/api/run-inspector` or changing `/api/status`. | Prefer new additive API. If extending existing response, run API shape tests. |

## Open Questions

1. Should P1 expose a new `/api/run-inspector` endpoint, or nest it under `/api/status`?
   - Current recommendation: new additive endpoint to avoid changing existing `/api/status` consumers.

2. Should the first panel be a standalone page or embedded in Sessions/Chat?
   - Current recommendation: standalone panel plus sidebar entry; Sessions/Chat only link into it.

3. Should the first desktop surface be a true desktop shell?
   - Current recommendation: no. First ship dashboard panel; evaluate a wrapper after the panel is stable.

4. What polling interval should be used?
   - Current recommendation: panel refresh every 3-5 seconds while visible; sidebar refresh slower, around 10-15 seconds, or share cached state.

5. Should the UI include copy diagnostic bundle?
   - Current recommendation: yes, but only after a privacy-safe diagnostic payload is explicitly defined.

6. How much remote mode should P1 support?
   - Current recommendation: read-only remote snapshot if the API is reachable; mark local-only fields as unavailable/degraded.

## First Delivery Slices

| Slice | Outcome | Verification |
| --- | --- | --- |
| DP-01 | Add requirements register and issue-informed scope. | Manual review: code evidence, issue evidence, risks, non-goals present. |
| DP-02 | Add `GET /api/run-inspector` backed by P0 snapshot. | API unit tests for success, unknown, degraded, collector failure, privacy. |
| DP-03 | Add `useRunInspectorStatus` hook with timeout/backoff. | Client unit tests for success, loading, auth failure, retry stop, degraded state. |
| DP-04 | Add full Run Inspector dashboard panel. | Component tests for visible fields, overflow, empty state, secret-safe rendering. |
| DP-05 | Add sidebar state signal. | Component tests and manual screenshot check. |
| DP-06 | Add Sessions/Chat diagnostic links. | Route/component tests for presence and no-snapshot state. |
| DP-07 | Evaluate desktop wrapper separately. | Decision memo only; no installer or config manager in this slice. |

## Quality Gate Before PRD Finalization

- Code evidence and issue evidence are both present.
- Every issue-derived risk has a requirement, non-goal, or risk flag.
- First slice is read-only.
- Platform-specific behavior is not assumed.
- UI has bounded loading and retry behavior.
- Privacy-safe display is enforced in API and UI.
- Delivery slices are vertical and independently verifiable.
