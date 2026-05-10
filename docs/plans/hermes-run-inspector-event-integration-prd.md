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
- Frontend tests for hook error classification, event formatting, and overflow/privacy guards.
- `npm.cmd run build`.
- Manual or Playwright smoke for `/run-inspector`.
