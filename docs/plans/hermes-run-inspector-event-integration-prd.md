# HERMES Run Inspector Event Integration PRD

Date: 2026-05-11

## Summary

Run Inspector P2 adds a read-only event timeline to the existing dashboard panel. The goal is to turn the P0 snapshot from a point-in-time status view into a small live diagnostic surface that explains what changed recently.

The first P2 slice should reuse existing event sources:

- dashboard chat `/api/pub` and `/api/events` frames
- gateway API run lifecycle SSE events from `/v1/runs/{run_id}/events`
- existing Run Inspector snapshot fields for run/session identity

## Problem

P1 can answer "what is the current state?" but not "how did it get here?".

When a run stalls, fails, waits for approval, or has tool/MCP churn, the user needs a short timeline of recent events without opening raw logs or replaying the entire terminal.

## Goals

- Capture recent run/session/tool lifecycle events into a bounded in-memory ledger.
- Expose a local read-only recent-events API.
- Expose a local read-only live subscription for the dashboard.
- Render a compact event timeline inside the Run Inspector page.
- Preserve P1 privacy guarantees: no raw prompts, raw logs, secrets, file bodies, environment values, or full tool arguments.

## Non-Goals

- Do not start, stop, resume, retry, reconnect, or mutate a run.
- Do not replace existing `/api/events` chat sidebar behavior.
- Do not persist raw event payloads.
- Do not add remote event forwarding.
- Do not add a desktop wrapper in this slice.

## Event Contract

Each exposed event should include:

- `id`: local monotonic event id
- `type`: normalized lifecycle type
- `source`: `dashboard_chat`, `gateway_run`, `run_inspector`, or `unknown`
- `timestamp`: ISO timestamp
- `run_id`: optional redacted run id
- `session_id`: optional redacted session/channel id
- `tool`: optional safe tool name
- `status`: optional safe event status
- `message`: optional redacted short summary

The event contract must not expose:

- raw prompt text
- raw terminal output
- raw logs
- full tool arguments
- file contents or diffs
- secrets, tokens, API keys, or environment values

## P2 Slice

The first implementation slice is intentionally narrow:

1. Add an in-memory event ledger with bounded size and redaction.
2. Record dashboard chat tool/session events received through `/api/pub`.
3. Add `GET /api/run-inspector/events` for recent events.
4. Add `WS /api/run-inspector/events` for live subscription with initial replay.
5. Add a Run Inspector timeline card.

Gateway `/v1/runs/{run_id}/events` bridging can follow after this slice if it needs network/adapter configuration discovery.

## P3 Gateway Source Mirroring

The next safe slice is source-side mirroring inside `APIServerAdapter`.

When the gateway API server creates run lifecycle events for `/v1/runs/{run_id}/events`, it should also emit the same lifecycle facts into the Run Inspector event contract:

- `run.started`
- `run.running`
- `approval.request`
- `tool.started`
- `tool.completed`
- `run.completed`
- `run.failed`
- `run.cancelled`

This must be best-effort only. If Run Inspector event recording fails, the gateway API server must keep serving `/v1/runs`, `/v1/runs/{run_id}`, and `/v1/runs/{run_id}/events` exactly as before.

Important boundary: the in-memory ledger is process-local. If the dashboard and gateway API server run as separate processes, source mirroring alone does not make gateway events appear in the dashboard process. Cross-process forwarding should be a separate slice with explicit gateway URL/key configuration, reconnect policy, and secret handling.

## P4 Cross-Process Gateway Event Forwarder

The next implementation slice lets the dashboard process follow a specific gateway API run without exposing gateway credentials to the browser.

Add a protected dashboard endpoint:

- `POST /api/run-inspector/gateway-runs/{run_id}/follow`

When called, the dashboard backend resolves the gateway base URL from `HERMES_RUN_INSPECTOR_GATEWAY_URL`, `GATEWAY_HEALTH_URL`, or configured `API_SERVER_*` environment values. It resolves the gateway bearer token from `HERMES_RUN_INSPECTOR_GATEWAY_KEY` or `API_SERVER_KEY`, opens `GET /v1/runs/{run_id}/events`, normalizes the SSE frames, and records them into the existing Run Inspector event ledger.

This must remain additive and best-effort:

- Browser code never receives the gateway key.
- Missing gateway configuration returns a clear `409`, not a background failure loop.
- Invalid gateway URLs return `400`.
- Gateway SSE payloads are normalized through the existing privacy contract.
- `tool.started` preview text and `run.completed` output are not recorded into the event ledger.
- A failed follower records a short `gateway.forwarder.failed` event but does not break the dashboard event API.

This slice does not yet auto-discover run ids. The caller must provide a `run_id` created by `/v1/runs`; automatic discovery or UI input can follow after this bridge is stable.

## Acceptance

- Recent events API returns an envelope with `ok`, `events`, and `refreshed_at`.
- WebSocket subscriber receives a replay and then new redacted events.
- Missing event source returns an empty event list, not an error.
- Events are bounded and do not grow unbounded in memory.
- Auth failure stops live subscription attempts.
- UI shows empty, connected, disconnected, and event states.
- Long event values do not overflow.
- Sensitive-looking event values render as `Redacted`.

## Risks

- Event payloads may contain prompt fragments or secrets.
- Existing chat sidebar event frames are not a stable public contract.
- WebSocket tests can race if subscriber registration is not awaited.
- Dashboard-only events may not represent non-dashboard runs yet.

## Verification

- Unit tests for event normalization, redaction, ordering, and bounded ledger.
- API tests for auth, recent-events response, and WebSocket replay/new event delivery.
- Gateway run endpoint tests for source-side lifecycle mirroring.
- Runtime tests for gateway SSE parsing, configured URL/key resolution, and cross-process forwarding redaction.
- API tests for the protected gateway follow endpoint, missing config, and status lookup.
- Frontend tests for hook error classification, event formatting, and overflow/privacy guards.
- `npm.cmd run build`.
- Manual or Playwright smoke for `/run-inspector`.
