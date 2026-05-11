# HERMES Desktop Attention Notifications PRD

Date: 2026-05-11
Status: Proposed for HRIDS-06
Owner: Product Manager skill
Related:

- `docs/plans/hermes-run-inspector-prd.md`
- `docs/plans/hermes-run-inspector-desktop-panel-requirements.md`
- `docs/plans/hermes-run-inspector-desktop-shell-prd.md`
- `docs/plans/hermes-desktop-runtime-decision.md`
- `.hermes/task.yaml`

## Decision Summary

Build a desktop attention signal contract before adding any native tray or OS notification runtime.

The next safe capability is not "send notifications everywhere." It is:

1. Define which Run Inspector states are allowed to become user-facing attention signals.
2. Normalize those states into redacted, deduplicated, local-only summaries.
3. Preview them in the existing dashboard.
4. Add explicit opt-in browser notifications only after privacy, permission, and rate-limit gates pass.
5. Revisit native tray or packaged OS notifications only through a separate runtime PRD.

This preserves the HRIDS-04 decision: the current desktop path remains `hermes desktop` plus the existing loopback dashboard, not a Tauri, Electron, or Python webview application.

## Target User And Workflow

Target user: a HERMES operator running long-lived CLI, gateway, MCP-backed, or coding-agent sessions from a local machine.

Current workflow:

- User starts a long task or gateway run.
- HERMES may become waiting, failed, degraded, or in need of approval.
- User has to keep the Run Inspector page visible or manually check status.

Desired workflow:

- User can see a safe attention summary in Run Inspector.
- If explicitly opted in, the browser can notify on high-signal states.
- The notification never exposes prompts, logs, file paths, full tool args, credentials, command output, or approval payload details.
- The user can click back to `/run-inspector` to inspect and act.

## Evidence, Assumptions, Decisions, Open Questions

### Evidence

- HERMES already exposes `/api/run-inspector`, `/api/run-inspector/events`, gateway run follow, approval controls, and recent run state inside the dashboard.
- GitNexus read `gateway/platforms/api_server.py:_approval_notify`: approval requests are already normalized into `approval.request` events and set run status to `waiting_for_approval`.
- GitNexus read `tools/approval.py:register_gateway_notify`: raw approval callback data can contain command, description, and pattern keys, so desktop notifications must not consume this callback payload directly.
- `docs/plans/hermes-run-inspector-desktop-panel-requirements.md` records issue evidence from adjacent projects: install detection failure, infinite loading, Windows path failures, remote/local communication failure, retry loops, config mutation, and UI overflow.
- `docs/plans/hermes-desktop-runtime-decision.md` explicitly defers tray, notifications, installer, signing, and update work until the browser-launcher lifecycle is stable and a packaging PRD exists.

### Assumptions

- Browser notifications are enough for the next validation step if they are explicit opt-in and only run while the dashboard is open.
- Native OS notifications and tray state require a packaged runtime decision because `hermes desktop` currently launches a browser and does not own a native window or tray process.
- A safe attention signal can be derived from the existing Run Inspector snapshot and event stream without reading raw logs or raw approval payloads.

### Decisions

- P0 defines a redacted attention event contract and preview surface.
- P1 may add opt-in browser notifications from the existing dashboard.
- P2 may evaluate native tray and OS notifications only after a packaging/runtime PRD is accepted.
- The attention system consumes Run Inspector-safe data only; it does not subscribe to raw gateway notification callbacks.

### Open Questions

- Should browser notification permission be stored in browser local storage only, or mirrored in HERMES config later?
- Should attention severity include cost/rate-limit pressure in this phase, or stay limited to waiting, failed, degraded, and recovery states?
- Should multiple workspaces share one attention stream or stay scoped to the current dashboard instance?

## Source Evidence Map

| Source | Code Evidence Read | Issue Evidence Read | Product Pattern | HERMES Implication | Not To Copy |
| --- | --- | --- | --- | --- | --- |
| `hermes-agent` Run Inspector | `/api/run-inspector`, `/api/run-inspector/events`, gateway run follow and approval endpoints, `RunInspectorPage`, `runInspectorGatewayControls.ts` | Existing local issue evidence is in the requirements register. | Run state and event state are already available in a privacy-filtered dashboard path. | Add attention signals as a read-only layer over Run Inspector data. | Do not create a second event bus or raw-log notifier. |
| `gateway/platforms/api_server.py` via GitNexus | `_approval_notify` emits `approval.request` and marks `waiting_for_approval`. | N/A | Approval waiting is already a high-signal state. | Use normalized event/status state, not raw approval data, for notifications. | Do not notify raw command, approval description, or tool pattern data. |
| `tools/approval.py` via GitNexus | `register_gateway_notify` accepts raw `command`, `description`, and `pattern_keys`. | N/A | Raw callback data is useful for gateway delivery but unsafe for OS notification text. | Build a redaction boundary before any user-facing notification. | Do not bridge this callback directly to desktop notification APIs. |
| `fathah/hermes-desktop` | Electron main/preload event bridge and gateway status surfaces. | #89 install stuck, #88 installed Hermes not detected, #87 infinite spinner, #85 Windows path assumptions, #83 remote mode gaps, #91 macOS/API key/remote-local failures. | Desktop affordances are valuable but fragile when install/runtime ownership comes too early. | Keep notifications optional, safe, and dashboard-owned first. | Do not copy installer, config detection, or full Electron shell. |
| `EKKOLearnAI/hermes-web-ui` | WebSocket terminal/control handling, job/session/run status model. | #607 config-mutating gateway port behavior, #606 retry loop/429, #598 Windows `spawn hermes ENOENT`, #587 tool UI overflow. | Status and reconnect UX need bounded retry, explicit degraded states, and layout limits. | Add rate limits, dedupe, auth-stop behavior, and overflow-safe notification text. | Do not add config mutation, infinite retries, or raw terminal notifications. |

## Current HERMES Reality

Existing surfaces:

- `hermes desktop` opens the loopback dashboard at `/run-inspector`.
- The dashboard has a Run Inspector page, sidebar signal, event timeline, gateway run follow, approval controls, and recent run filtering.
- The backend has protected read-only Run Inspector APIs and event WebSocket.
- The event ledger already redacts and bounds event storage.
- Existing gateway approval flow has raw data that must remain behind the dashboard detail view, not OS notification text.

Constraints:

- `hermes desktop` is a browser launcher, not a native tray process.
- The dashboard token and session model must not leak into notification URLs or logs.
- Browser notification permissions are user-agent state, not HERMES config state.
- Native notification behavior differs by Windows, macOS, Linux desktop environments, and browser.

## Requirements

### P0.1 Attention Signal Contract

Define a normalized attention signal derived only from Run Inspector-safe snapshot and event data.

Allowed fields:

- `id`
- `kind`
- `severity`
- `title`
- `body`
- `route`
- `run_id`
- `session_id`
- `timestamp`
- `dedupe_key`
- `ttl_ms`
- `privacy_class`

Allowed kinds:

- `approval_waiting`
- `run_failed`
- `run_degraded`
- `mcp_degraded`
- `desktop_shell_degraded`
- `recovery_available`

Acceptance:

- Signal text is generated from redacted summaries, not raw prompt/log/tool/approval payloads.
- `route` is path-only, such as `/run-inspector`, not a token-bearing absolute URL.
- `run_id` and `session_id` may be present only as opaque identifiers.
- `privacy_class` is `safe_summary`, `redacted_summary`, or `local_only`.
- Missing state produces no signal or an explicit `desktop_shell_degraded` signal, not an exception.

### P0.2 Dedupe, Rate Limit, And Expiry

Prevent notification loops.

Acceptance:

- Each signal has a stable `dedupe_key`.
- Repeated equivalent signals within a configured window collapse into one visible signal.
- Expired signals are ignored by notification delivery.
- Auth failure or API offline state stops polling or delivery escalation rather than retrying indefinitely.

### P0.3 Dashboard Attention Preview

Show the latest attention signals inside Run Inspector before delivering OS/browser notifications.

Acceptance:

- Preview appears in the Run Inspector page or a compact attention card.
- Empty state is explicit.
- Long titles and bodies do not overflow on desktop or narrow viewports.
- User can inspect the signal source through existing Run Inspector details.
- Preview remains read-only and does not start, stop, approve, deny, reconnect, retry, or mutate gateway/config state.

### P1.1 Explicit Browser Notification Opt-In

After P0 is verified, allow browser notifications only when the dashboard is open and the user has explicitly granted permission.

Acceptance:

- No permission prompt appears on initial page load.
- User must click an explicit enable action.
- Notification body uses only the attention signal title/body.
- Clicking a notification routes to `/run-inspector`.
- Permission denied, unsupported, or blocked states are shown as degraded, not fatal.
- Delivery is local-browser only and does not write `.env`, `config.yaml`, provider profiles, gateway config, or external services.

### P2 Native Tray And OS Notification Gate

Native tray and packaged OS notifications require a separate runtime PRD.

Acceptance:

- The PRD covers OS matrix, packaging, signing, update model, session-token handling, local dashboard discovery, port conflicts, remote mode, rollback, support ownership, and CI build cost.
- Tauri, Electron, and Python webview are compared with measured requirements.
- No native runtime work starts from this PRD alone.

## Non-Goals

- No native tray implementation in HRIDS-06.
- No Tauri, Electron, or Python webview packaging.
- No installer, updater, code signing, or auto-start.
- No gateway config writes or port mutation.
- No notification delivery to Slack, Telegram, Teams, email, or other external services.
- No raw prompts, raw logs, file paths, command output, full tool args, credentials, diffs, stack traces, or raw approval payloads in notifications.

## Success Metrics

- Approval-waiting or failed-run state becomes visible in the dashboard attention preview within one polling/event cycle.
- Browser notification permission is never requested without a user click.
- Repeated equivalent events produce one visible notification per dedupe window.
- Redaction tests prove secret-looking text and raw approval fields cannot appear in signal title/body.
- No new infinite retry loop is introduced when event API auth fails or disconnects.

## Acceptance And Evaluation

Unit/integration tests:

- Attention normalizer maps waiting approval, run failed, degraded MCP, and shell degraded states to safe signals.
- Secret-looking values, command strings, file paths, raw logs, and approval descriptions are redacted or excluded.
- Dedupe and TTL behavior suppress repeat spam.
- Permission denied/unsupported browser notification states do not crash the page.

Frontend/build checks:

- Run Inspector attention preview renders empty, ready, degraded, and long-text states.
- Browser permission prompt is only reachable through explicit user action.
- Desktop and narrow viewport smoke checks show no horizontal overflow.

GitNexus/source checks:

- `detect_changes` stays low/medium risk for PRD-only and policy-only slices.
- Any later API or frontend change runs targeted Run Inspector and web policy tests.

## Delivery Slices

### HRIDS-06 Desktop Attention PRD And Execution Gate

Outcome: this PRD plus `.hermes/task.yaml` slices.

Verification:

- PRD separates evidence, assumptions, decisions, open questions, requirements, non-goals, and evaluation.
- `.hermes/task.yaml` records HRIDS-06 through HRIDS-10.
- `git diff --check` and YAML parse pass.

### HRIDS-07 Redacted Attention Signal Policy

Outcome: add a small pure policy/normalizer layer that converts Run Inspector snapshot/events into safe attention signals.

Verification:

- Unit tests cover allowed kinds, redaction, dedupe key, TTL, missing data, and raw approval payload exclusion.
- No API, config, gateway, or notification delivery behavior changes yet.

### HRIDS-08 Dashboard Attention Preview

Outcome: show attention signals inside `/run-inspector`.

Verification:

- Frontend tests cover empty, ready, degraded, and long-text states.
- Build passes.
- Browser smoke passes at desktop and narrow widths.

### HRIDS-09 Optional Browser Notification Opt-In

Outcome: add explicit opt-in browser notification delivery from attention signals.

Verification:

- Tests or smoke confirm no permission prompt on initial load.
- Permission denied/unsupported states degrade safely.
- Dedupe/rate-limit prevents repeated browser notifications.

### HRIDS-10 Native Tray And Runtime Re-Evaluation

Outcome: decide whether native tray/OS notifications justify Tauri, Electron, Python webview, or continued browser launcher.

Verification:

- Runtime PRD answers the packaging gate in `docs/plans/hermes-desktop-runtime-decision.md`.
- No implementation begins until the decision is accepted.

## HERMES Execution Contract Addendum

When HRIDS-07 starts implementation, `.hermes/task.yaml` must keep these risk flags active:

- `credential_or_secret_access`
- `external_api_write`
- `public_contract_change`
- `user_visible_behavior_change`

Any redaction failure is a blocker and must create:

- a failing regression test
- a failure review entry
- an updated notification exclusion rule

## Next Step

Implement HRIDS-07: redacted attention signal policy and tests, without browser notification delivery.
