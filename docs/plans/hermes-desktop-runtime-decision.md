# HERMES Desktop Runtime Decision

Date: 2026-05-11
Status: Re-accepted for HRIDS-10 after browser notification validation
Owner: Product Manager skill
Related:

- `docs/plans/hermes-run-inspector-desktop-shell-prd.md`
- `docs/plans/hermes-desktop-wrapper-decision.md`
- `docs/plans/hermes-desktop-attention-notifications-prd.md`
- `.hermes/task.yaml`

## Decision

Continue with the browser-launcher desktop shell for the next HERMES Run Inspector desktop slice.

Do not add Tauri, Electron, or Python webview packaging yet. The current runtime layer should remain:

- `hermes desktop`
- loopback-only dashboard binding
- `/run-inspector` as the primary surface
- shell-owned runtime record for status and stop
- existing React dashboard and FastAPI backend as the only UI/runtime implementation

This keeps the desktop work focused on lifecycle reliability before adding installer, tray, update, signing, and bundled-runtime responsibilities.

## HRIDS-10 Re-Evaluation

HRIDS-09 validated the next desktop-adjacent capability without adding a native runtime:

- The Run Inspector dashboard can render safe attention signals.
- Browser notifications require an explicit user click before `requestPermission`.
- Denied or unsupported browser notification permission degrades inside the dashboard.
- Delivered notifications use the safe attention signal title/body only.
- Notification click routing uses `/run-inspector` and does not carry a session token.
- Dedupe and TTL are enforced before notification delivery.

This means the first attention workflow no longer requires a tray, packaged window, installer, or native notification bridge. The product still needs better lifecycle reliability and operator observability before native packaging would pay for itself.

Decision: keep the browser-launcher runtime for the next phase. Revisit a packaged runtime only after HERMES has evidence that browser-open notification delivery is insufficient for real operators.

## Current State

HRIDS-02 and HRIDS-03 have already created the minimum viable desktop shell:

- `hermes desktop` starts or reuses a local dashboard.
- It opens `http://127.0.0.1:<port>/run-inspector`.
- It records shell-owned runtime metadata in `~/.hermes/desktop_shell.json`.
- `--status` reports PID, URL, route, started time, and health.
- `--stop` only targets the verified shell-owned PID.
- Busy non-HERMES ports degrade without mutating gateway or user config.

This is enough to validate whether operators actually need a packaged desktop app.

## Evidence

### HERMES

Local code and GitNexus reads show that HERMES already has the required runtime primitives:

- `hermes_cli/main.py` owns CLI lifecycle and now owns `hermes desktop`.
- `hermes_cli/web_server.py:start_server` already binds and serves the local dashboard.
- The Run Inspector dashboard is already the source UI.
- Existing dashboard lifecycle tests cover stop/status precedence and stale dashboard cleanup.

Adding a second runtime now would duplicate behavior that already works through the dashboard.

### fathah/hermes-desktop

Useful patterns:

- Electron main/preload can bridge runtime and tool progress events into renderer state.
- Gateway and install surfaces can be presented as desktop affordances.
- Desktop packaging can eventually provide tray or update flows.

Risks:

- Installed-HERMES detection can block users before they reach the product.
- Installer/update flows create extra failure modes.
- Windows path and session-loading assumptions become product blockers.

### EKKOLearnAI/hermes-web-ui

Useful patterns:

- Run/session/job monitoring benefits from explicit state models.
- WebSocket and terminal panels are valuable when scoped.
- Gateway status and job state need clear degraded states.

Risks:

- Gateway port mutation creates operator confusion.
- Update/install flows add Node path and global package assumptions.
- Unauthenticated or failed connection loops can create noisy failures.

## Runtime Comparison

| Option | Install footprint | Windows compatibility | CI complexity | Tray support | Update model | Security | Maintenance cost | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Browser launcher | None beyond existing HERMES install | Best current path because it reuses Python and browser | Low | None | Existing HERMES update path | Reuses loopback and dashboard token model | Low | Continue |
| Python webview | Adds a native webview dependency | Uncertain across WebView2, GTK, Cocoa variants | Medium | Limited | Still custom | Must audit embedded webview/session behavior | Medium | Defer |
| Tauri | Small packaged shell | Good if WebView2 is present; Rust toolchain needed | High | Good | Requires signing/update decisions | Strong isolation if configured correctly | Medium-high | Evaluate later |
| Electron | Mature desktop runtime | Good but heavier | High | Good | Requires app updater/signing path | Larger attack surface, Node integration constraints | High | Defer unless Tauri/webview fail |

## Post-Notification Runtime Gate

| Gate | Current Browser Launcher | Python Webview | Tauri | Electron | HRIDS-10 Decision |
| --- | --- | --- | --- | --- | --- |
| OS matrix | Works anywhere supported HERMES and a browser run | Requires WebView2/GTK/Cocoa validation | Requires Rust build plus system WebView validation | Requires Electron package validation | Keep browser launcher until platform-specific need is proven |
| Packaging | No new packaging | New Python dependency and native webview packaging | New app packaging pipeline | New app packaging pipeline | Defer packaged runtime |
| Signing | Existing HERMES distribution only | New signing path if distributed as app | New signing path | New signing path | Defer |
| Update model | Existing HERMES update path | Custom app/runtime update story | Tauri updater or custom update story | Electron updater or custom update story | Defer |
| Session token handling | Existing FastAPI injection model | Must audit embedded window storage and navigation | Must audit window isolation and deep links | Must audit Node integration and deep links | Keep existing token model |
| Local dashboard discovery | Already implemented through `hermes desktop --status` and shell-owned runtime file | Still needs same discovery | Still needs same discovery | Still needs same discovery | Improve current discovery first |
| Port conflicts | Current shell reports/degrades without mutating gateway config | Same problem remains | Same problem remains | Same problem remains | Improve diagnostics before packaging |
| Remote mode | Browser can already open a remote dashboard URL if separately supported | Needs explicit remote navigation and auth story | Needs explicit remote navigation and auth story | Needs explicit remote navigation and auth story | Keep remote mode out of runtime packaging |
| Tray | Not available | Limited/non-standard | Good | Good | Not justified yet |
| OS notifications | Browser notifications while dashboard is open | Native bridge possible | Native bridge possible | Native bridge possible | Browser opt-in is enough for validation |
| Rollback | Revert CLI/dashboard changes | App rollback needed | App rollback needed | App rollback needed | Avoid extra rollback surface |
| Support ownership | Existing CLI/dashboard owner | Adds native runtime support | Adds Rust/native app support | Adds Electron/security support | Avoid until usage evidence requires it |
| CI cost | Existing web/Python checks | Adds webview matrix | Adds Rust/app build matrix | Adds Electron build matrix | Avoid until packaging is accepted |

## Accepted Path

For the next implementation phase:

1. Keep `hermes desktop` as a browser-launcher lifecycle shell.
2. Improve lifecycle quality before packaging:
   - clearer startup failure classes
   - optional port selection that never mutates config
   - status output for shell-owned and compatible dashboard cases
   - smoke coverage for Windows native paths
3. Keep all UI work in the React dashboard.
4. Keep all run data behind the existing `/api/run-inspector` contract.
5. Do not start installer, auto-update, code signing, tray, or notification implementation in this branch.

## Revisit Criteria

Reconsider Tauri, Electron, or Python webview only if at least two of these become true:

- Operators need tray state for long-running runs.
- Browser-launcher usage creates measurable support burden.
- OS notifications become a required product surface.
- Users need a single-window app for multi-workspace monitoring.
- Packaging must bundle known dashboard assets for offline installs.
- The dashboard lifecycle layer has stable telemetry showing startup, stop, status, and recovery success rates.

## Packaging Gate

No packaged runtime work should begin until a new PRD answers:

- supported OS matrix
- install/update/signing approach
- bundled Python/Node/runtime strategy
- dashboard asset build and cache strategy
- session-token handling inside a native shell
- remote dashboard mode, if any
- port conflict behavior
- tray and notification privacy rules
- rollback and support plan
- CI build cost and release ownership

The current answer is no: HRIDS-10 does not approve packaged runtime work. A later PRD may reopen the gate only with measured evidence from Run Inspector usage, notification opt-in behavior, and dashboard lifecycle telemetry.

## Product Boundary

The desktop runtime must not become:

- a second Run Inspector UI
- a config editor
- a gateway port manager
- a credential manager
- a terminal emulator
- an installer/updater in this slice
- a source of raw prompts, logs, command output, tool args, credentials, diffs, stack traces, or file bodies

## Next Step

HRIDS-10 closes the runtime choice for this phase after browser notification validation.

Next product slice should improve browser-launcher reliability rather than package a new runtime:

- startup failure classification
- compatible dashboard discovery
- optional explicit free-port suggestion
- Windows smoke coverage
- documentation for `hermes desktop`, `--status`, and `--stop`
