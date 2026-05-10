# HERMES Desktop Wrapper Decision

Date: 2026-05-11

## Decision

Do not add a separate desktop wrapper in Run Inspector P1.

Ship the Run Inspector as a read-only dashboard panel first. Revisit a desktop wrapper only after the panel has stable run/session event sources, documented packaging needs, and a separate PRD with its own `.hermes/task.yaml` execution contract.

## Why

The current HERMES codebase already has a Python dashboard backend and React dashboard shell. Adding a second desktop runtime now would duplicate routing, authentication, logging, release, and support surfaces before the diagnostic data contract is mature.

The adjacent projects still provide useful patterns:

- `fathah/hermes-desktop`: useful for IPC event bridging, tool-progress events, gateway status surfaces, and desktop affordances.
- `EKKOLearnAI/hermes-web-ui`: useful for run/session/job monitoring, WebSocket terminal panels, and dashboard information architecture.

Those patterns are already better applied inside HERMES as:

- `/api/run-inspector`
- `useRunInspectorStatus`
- `RunInspectorPage`
- sidebar and session/chat diagnostic entry points

## Scope Boundary

Run Inspector P1 stays read-only.

It does not include:

- installer or updater work
- gateway start/stop controls
- config editing
- credential or secret management
- terminal streaming
- remote service writes
- MCP reconnect, retry, refresh, or tool dispatch actions

## Desktop Wrapper Criteria

A wrapper may be justified later if at least one condition is true:

- users need a single-click local status tray for long-running HERMES sessions
- local browser access is unreliable in the target deployment
- packaging must bundle a known Python/node runtime and dashboard assets
- OS-level notifications become a product requirement
- multi-workspace run monitoring needs native window/session management

Before implementation, the wrapper PRD must cover:

- Windows/macOS/Linux support matrix
- install and update strategy
- local dashboard discovery and port conflict handling
- remote mode behavior
- authentication and session-token handling
- offline and gateway-stopped behavior
- support burden and rollback plan

## Recommended Later Shape

If approved later, the first wrapper should be a thin shell around the existing local dashboard:

- discover or start the local dashboard only after explicit user action
- open `/run-inspector` as the primary view
- expose read-only notifications for degraded, failed, waiting approval, and recovering states
- avoid config writes and gateway controls in the first wrapper release
- keep all run data coming from the same `/api/run-inspector` contract

## Next Step

Close the desktop wrapper question for P1. The next product slice should be Run Inspector P2 event integration:

- real run event stream
- session event stream
- tool-call lifecycle events
- MCP reconnect/retry visibility
- failure review timeline
