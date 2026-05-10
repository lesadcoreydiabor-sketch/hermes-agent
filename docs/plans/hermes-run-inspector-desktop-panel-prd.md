# HERMES Run Inspector Desktop Panel PRD

Date: 2026-05-11
Status: Draft for P1 implementation
Owner: Product Manager skill
Related:

- `docs/plans/hermes-run-inspector-prd.md`
- `docs/plans/hermes-run-inspector-desktop-panel-requirements.md`
- `.hermes/task.yaml`

## Summary

Build the next Run Inspector milestone as a read-only desktop-facing dashboard panel inside the existing HERMES web UI. The panel should help an operator understand whether HERMES is running, stuck, waiting, failed, degraded, or unable to report state, without starting/stopping runs, mutating gateway config, reading secrets, or assuming a specific desktop runtime.

This is not a full Electron desktop app, installer, terminal emulator, or gateway control center. The first milestone converts the existing P0 Run Inspector snapshot into an observable UI surface and leaves desktop shell decisions for a later design.

## Why Now

Run Inspector P0 added a privacy-safe snapshot and CLI surface. That proves HERMES can summarize run/session/tool/MCP state without mutating runtime behavior. The next problem is operator visibility: users should not have to inspect logs, infer gateway state manually, or guess whether a long task is still active.

Adjacent HERMES desktop/web UI projects show recurring failure modes that this PRD must explicitly avoid:

- Install and path detection can block the product before users reach the main workflow.
- Session pages can spin forever when async loading fails.
- Gateway management can mutate config or break on Windows.
- Polling can become an unauthenticated retry loop.
- Tool-call UI can overflow or reveal too much detail.

Therefore P1 must be observer-first, bounded, privacy-safe, and additive.

## Source Evidence

### HERMES Current Code

- `hermes_cli/run_inspector.py` already defines the P0 snapshot contract and redaction/failure-review behavior.
- `hermes_cli/status.py` and `hermes_cli/main.py` expose `hermes status --run-inspector`.
- `hermes_cli/web_server.py:get_status` is the current local dashboard status surface.
- `web/src/hooks/useSidebarStatus.ts` and `web/src/components/SidebarStatusStrip.tsx` are the current sidebar status integration points.
- `web/src/pages/SessionsPage.tsx` and `web/src/pages/ChatPage.tsx` are the natural diagnostic entry points for session/chat context.

### External Code Patterns Read With GitNexus

- `fathah/hermes-desktop`
  - `src/main/index.ts:onToolProgress` bridges tool progress events to the renderer.
  - `src/preload/index.ts:onChatToolProgress` exposes a renderer subscription API.
  - `src/renderer/src/screens/Gateway/Gateway.tsx` shows gateway state, polling, and controls.
  - Transferable pattern: event/progress data should become visible UI state.
  - Non-transferable for P1: installer ownership, desktop shell, and gateway write controls.

- `EKKOLearnAI/hermes-web-ui`
  - `packages/client/src/components/hermes/chat/TerminalPanel.vue` models WebSocket connection, reconnect, control-message, and terminal-output states.
  - `packages/server/src/services/hermes/chat-run-socket.ts` organizes chat run/session state and abort/completion handling.
  - `packages/client/src/api/hermes/jobs.ts` uses state fields such as `last_status`, `last_error`, `next_run_at`, and `last_run_at`.
  - GitNexus route map found a broad API surface for sessions, jobs, gateways, logs, kanban, and cron history.
  - Transferable pattern: run/session/job observability should be state-model driven.
  - Non-transferable for P1: broad job orchestration, terminal streaming, and gateway write operations.

### Issue Evidence

- `fathah/hermes-desktop` issue [#89](https://github.com/fathah/hermes-desktop/issues/89): Windows install stuck.
- `fathah/hermes-desktop` issue [#88](https://github.com/fathah/hermes-desktop/issues/88): installed Hermes not detected.
- `fathah/hermes-desktop` issue [#87](https://github.com/fathah/hermes-desktop/issues/87): Sessions infinite loading.
- `fathah/hermes-desktop` issue [#85](https://github.com/fathah/hermes-desktop/issues/85): Windows install detection hardcoded to Unix paths.
- `fathah/hermes-desktop` issue [#83](https://github.com/fathah/hermes-desktop/issues/83): remote mode cannot read remote config/models.
- `EKKOLearnAI/hermes-web-ui` issue [#607](https://github.com/EKKOLearnAI/hermes-web-ui/issues/607): gateway port auto-increment and config mutation.
- `EKKOLearnAI/hermes-web-ui` issue [#606](https://github.com/EKKOLearnAI/hermes-web-ui/issues/606): unauthenticated frontend requests causing 429 loops.
- `EKKOLearnAI/hermes-web-ui` issue [#598](https://github.com/EKKOLearnAI/hermes-web-ui/issues/598): Windows gateway management compatibility and `spawn hermes ENOENT`.
- `EKKOLearnAI/hermes-web-ui` issue [#587](https://github.com/EKKOLearnAI/hermes-web-ui/issues/587): tool-call UI overflow and readability problems.

## Product Decision

P1 ships a Run Inspector dashboard panel that reads the P0 snapshot through a local API and renders a bounded diagnostic view. It should be usable in a browser and also suitable for a future desktop wrapper.

P1 does not implement a separate desktop application. A true desktop wrapper can be evaluated after the read-only panel has stable data contracts, UI states, and privacy tests.

## Goals

1. Expose a local read-only Run Inspector API for the dashboard.
2. Add a Run Inspector panel that renders P0 snapshot fields safely.
3. Add a compact sidebar signal for current run health.
4. Add session/chat diagnostic entry points that route to the panel.
5. Prevent infinite loading, unbounded retry, auth loops, config mutation, and privacy leaks.
6. Produce tests that make the panel safe to extend into a desktop wrapper later.

## Non-Goals

- No full Electron app.
- No installer.
- No provider credential manager.
- No config editor.
- No gateway start/stop/restart.
- No automatic port reassignment.
- No terminal emulator or PTY streaming.
- No raw transcript, raw log, raw prompt, file-body, or full tool-argument viewer.
- No remote write operations.

## Target Users

Primary user: a HERMES operator or developer running long agent tasks locally who needs to know what the system is doing and what to do next.

Secondary user: a HERMES maintainer diagnosing session/tool/MCP failures and collecting privacy-safe reproduction context.

## User Stories

1. As an operator, I can open the dashboard and immediately see whether HERMES is running, waiting, failed, degraded, or unknown.
2. As an operator, I can see the active session/run context without exposing secrets or raw prompts.
3. As an operator, I can tell whether the active tool or MCP system is the likely blocker.
4. As an operator, I can refresh manually when the panel is stale.
5. As an operator, I can see a clear degraded/auth/offline state instead of an infinite spinner.
6. As a maintainer, I can verify the panel from tests without needing a full desktop shell.

## Requirements

### P1.1 Local Read-Only API

Add an additive local endpoint, recommended as `GET /api/run-inspector`, backed by the P0 Run Inspector snapshot contract.

Acceptance:

- The endpoint returns the same privacy-safe top-level concepts as `hermes status --run-inspector`.
- The endpoint does not start, stop, resume, retry, reconnect, refresh, register, deregister, dispatch tools, or write config.
- Missing collector data returns `status: unknown` and `degraded_reason` when possible.
- Tool/MCP/session/gateway collector failures degrade the payload instead of crashing the dashboard API.
- The endpoint has tests for success, unknown state, degraded collector failure, and redaction.

### P1.2 Run Inspector Panel

Add a dashboard panel for the snapshot.

Minimum displayed fields:

- Status, source, and reason.
- Session id and workspace when safe.
- Last activity time.
- Active tool name, call id when safe, duration, and summarized argument shape.
- MCP health summary.
- Tool health summary.
- Gateway/session availability.
- Recovery hint.
- Privacy flags.
- Degraded reason.
- Last refreshed time.
- Manual refresh action.

Acceptance:

- Loading state has a timeout and cannot spin forever.
- Empty, unknown, degraded, auth-failed, and offline states are explicit.
- Long tool names, call ids, and summaries fit without breaking layout.
- Raw prompts, raw logs, secrets, file bodies, environment values, and full tool arguments are never rendered.
- Display copy tells the user what is known and what is unavailable, without claiming certainty from missing data.

### P1.3 Sidebar Run Signal

Add a compact state signal near the existing sidebar status surface.

Acceptance:

- The signal maps to `running`, `waiting`, `failed`, `degraded`, `unknown`, or `unavailable`.
- Clicking or activating the signal routes to the full Run Inspector panel.
- Sidebar polling does not duplicate high-frequency panel polling.
- If the API is unavailable, the sidebar shows an unavailable/degraded state without blocking navigation.

### P1.4 Session And Chat Entry Points

Add diagnostic entry points from the session and chat surfaces.

Acceptance:

- Sessions page can link to the current/latest run diagnostic when a snapshot exists.
- Chat page can link to the current run diagnostic when embedded chat is enabled.
- No-snapshot state is treated as unavailable, not as an error.
- Entry points do not require run mutation or gateway control.

### P1.5 Resilience And Retry Rules

The panel must be safe under network, auth, and server failures.

Acceptance:

- Requests use bounded timeout.
- Polling uses backoff after repeated failure.
- Auth failure stops polling and surfaces an auth/degraded state.
- Manual refresh remains available where safe.
- No automatic gateway restart, config write, model refresh, or credential read happens from this panel.

### P1.6 Desktop Wrapper Readiness

Keep the panel compatible with a future desktop wrapper without committing to one in P1.

Acceptance:

- No hardcoded Unix-only paths or `bash` requirement are introduced.
- No desktop install detection is required for the panel to work.
- Local-only fields are clearly marked when unavailable remotely.
- Config write actions stay out of scope until a separate config-preserving design exists.

## Information Architecture

The panel should be organized around operator questions:

1. Current state: status, reason, source, last activity, last refresh.
2. Runtime context: workspace, session id, run id if available.
3. Active work: active tool and safe argument summary.
4. Dependencies: tool registry and MCP health.
5. Recovery: recovery hint and degraded reason.
6. Safety: privacy flags and copy-safe diagnostic boundary.

## API Contract Draft

The API should preserve the P0 snapshot shape where possible. If a web-specific envelope is needed, keep it additive:

```json
{
  "ok": true,
  "snapshot": {
    "version": 1,
    "status": "running",
    "source": "session",
    "reason": null,
    "workspace": "C:/path/to/workspace",
    "session_id": "safe-session-id",
    "last_activity_at": "2026-05-11T10:00:00Z",
    "active_tool": {
      "name": "mcp_tool",
      "call_id": "safe-call-id",
      "duration_ms": 1200,
      "args_summary": "dict: 3 keys"
    },
    "mcp_health": {
      "status": "degraded",
      "servers": []
    },
    "tool_health": {
      "status": "available"
    },
    "recovery_hint": "Check MCP server connection",
    "privacy_flags": ["safe", "redacted"],
    "degraded_reason": null
  },
  "refreshed_at": "2026-05-11T10:00:02Z"
}
```

If the snapshot cannot be built:

```json
{
  "ok": false,
  "snapshot": {
    "version": 1,
    "status": "unknown",
    "source": "web_api",
    "degraded_reason": "run_inspector_snapshot_failed",
    "privacy_flags": ["safe"]
  },
  "refreshed_at": "2026-05-11T10:00:02Z"
}
```

## Execution Contract

When this PRD enters implementation, `.hermes/task.yaml` must contain a P1 slice with:

- API task.
- Client data hook task.
- Full panel task.
- Sidebar signal task.
- Sessions/Chat entry task.
- Resilience/privacy test task.
- Desktop wrapper decision task.

Every task must define dependencies, acceptance criteria, verification commands, status, and risk. Risk flags must pause implementation for config mutation, credential access, destructive filesystem changes, public contract changes, platform-specific execution, infinite retry/loading, and privacy leakage.

## Evaluation Plan

### Backend

- Unit tests for `/api/run-inspector` success, unknown state, collector failure, and redaction.
- Regression test that endpoint access does not call start/stop/reconnect/refresh/config-write methods.
- Existing P0 run inspector tests must remain passing.

### Frontend

- Hook tests for success, timeout, auth failure, server failure, backoff, and manual refresh.
- Component tests for visible fields, empty state, degraded state, long tool names, long summaries, and secret-looking values.
- Sidebar tests for state mapping and route activation.
- Sessions/Chat tests for diagnostic link and no-snapshot state.

### Manual Verification

- Start dashboard and confirm panel loads from current local HERMES state.
- Verify no infinite spinner when API is unavailable.
- Verify long active tool content does not overflow.
- Verify a secret-looking value is not visible in UI.
- Verify Windows environment does not require `/bin/bash` for this feature.

## Rollout

1. Land additive API and tests.
2. Land client hook and state model.
3. Land full panel behind normal dashboard navigation.
4. Add sidebar signal.
5. Add Sessions/Chat links.
6. Run UI/manual checks and update `.hermes/task.yaml` progress.
7. Decide whether a desktop wrapper PRD is justified.

## Open Questions

1. Should the panel route be `/run-inspector`, `/status/run-inspector`, or nested under Sessions?
   - Recommendation: standalone route plus links from sidebar, Sessions, and Chat.

2. Should the UI include copy-safe diagnostic bundle in P1?
   - Recommendation: only if the payload is explicitly generated from the redacted snapshot. Otherwise defer.

3. Should the dashboard API envelope use `ok/snapshot/refreshed_at`?
   - Recommendation: yes for web resilience, while keeping the internal snapshot contract versioned.

4. Should polling be active when the panel is hidden?
   - Recommendation: no. Poll while visible; sidebar can use slower cached status.

5. How much remote mode should P1 support?
   - Recommendation: read-only snapshot if reachable; mark local-only fields unavailable.

## Definition Of Done

- PRD and task contract are present.
- `GET /api/run-inspector` is additive and read-only.
- Dashboard panel renders P0 snapshot state safely.
- Sidebar signal and Sessions/Chat entry points exist.
- Auth/offline/degraded/unknown states are explicit.
- Polling is bounded and cannot become an infinite retry loop.
- No config writes, gateway writes, installer behavior, or desktop path detection are introduced.
- Backend, frontend, and manual verification steps pass or have documented blockers in `.hermes/task.yaml`.
