# HERMES Run Inspector Desktop Shell PRD

Date: 2026-05-11
Status: Draft for desktop-shell decision
Owner: Product Manager skill
Related:

- `docs/plans/hermes-run-inspector-prd.md`
- `docs/plans/hermes-run-inspector-desktop-panel-requirements.md`
- `docs/plans/hermes-run-inspector-desktop-panel-prd.md`
- `docs/plans/hermes-run-inspector-event-integration-prd.md`
- `.hermes/task.yaml`

## Summary

Build the first HERMES desktop experience as a thin local shell around the existing React dashboard and Run Inspector panel. The shell should manage local dashboard lifecycle, open a desktop-facing window or browser surface, and expose clear status for the running dashboard process.

The first desktop shell must not become an installer, config editor, gateway control center, terminal emulator, or second implementation of the dashboard. The product value is reliable local visibility, not a new UI stack.

## Product Decision

Recommended path: start with a lightweight local dashboard shell contract before choosing a full packaged runtime.

The next implementation should add a desktop-shell layer that:

- reuses the existing dashboard command and `start_server` path
- binds to `127.0.0.1`
- chooses or records a safe local port without mutating gateway config
- opens `/run-inspector` by default
- reports dashboard process, URL, port, and health
- keeps all gateway write actions explicit inside the existing Run Inspector controls

Tauri or Electron packaging should remain a later decision after the lifecycle layer is tested. This avoids repeating the install, path detection, and config mutation failures seen in adjacent Hermes desktop/web UI projects.

## Source Evidence

### HERMES Current Architecture

GitNexus and local reads show the existing dashboard path is already suitable for a shell wrapper:

- `hermes_cli/main.py:cmd_dashboard` handles dashboard `--status`, `--stop`, stale process checks, optional web build, and then calls `start_server`.
- `hermes_cli/web_server.py:start_server` binds host/port, records `app.state.bound_host` and `app.state.bound_port`, and serves the FastAPI app through uvicorn.
- `hermes_cli/web_server.py:mount_spa` serves the built React app and injects the session token into `index.html`.
- The current dashboard command already supports `--host`, `--port`, `--no-open`, `--status`, `--stop`, and `--tui`.
- Run Inspector now has a dashboard route, event timeline, gateway follow/launch/control surfaces, selected run details, approval auto-selection, and recent-run filters.

### External Project Lessons

From `fathah/hermes-desktop`:

- Useful pattern: desktop main/preload process can bridge runtime events into renderer state.
- Risk: installer and installed-Hermes detection can block users before they reach the actual product.
- Risk: Windows path assumptions and session loading failures cause high-friction desktop failure modes.

From `EKKOLearnAI/hermes-web-ui`:

- Useful pattern: run/session/job UI works best when state is explicit and resilient.
- Risk: gateway port auto-increment and config mutation can corrupt operator expectations.
- Risk: unauthenticated request loops can create noisy failures.
- Risk: tool-call UI needs strict overflow and readability constraints.

## Goals

1. Define a minimal desktop shell that reuses the existing dashboard and Run Inspector work.
2. Make the shell lifecycle explicit: start, open, status, stop, and degraded state.
3. Keep local binding and session-token protection intact.
4. Avoid installer, gateway config, provider auth, and terminal responsibilities in the first slice.
5. Prepare an implementation plan that can later choose Tauri, Electron, or a lighter launcher with evidence.

## Non-Goals

- No new installer.
- No provider credential setup.
- No direct config editor.
- No gateway port mutation.
- No gateway restart/start/stop automation from the shell.
- No terminal emulator or PTY surface beyond the existing dashboard option.
- No duplicate Run Inspector UI outside the existing React dashboard.
- No public network bind by default.
- No raw prompt, log, command output, tool args, file body, diff, stack trace, or credential display.

## Target User

Primary user: a local HERMES operator who wants a desktop-like control surface for monitoring long-running agent work and quickly finding runs that need attention.

Secondary user: a HERMES maintainer testing dashboard lifecycle and Run Inspector behavior on Windows/macOS/Linux without committing to a full packaged app.

## User Stories

1. As an operator, I can launch a desktop entry point and land directly on Run Inspector.
2. As an operator, I can see whether the local dashboard process is running and which URL it uses.
3. As an operator, I can reopen the shell without starting duplicate dashboard processes.
4. As an operator, I can stop the shell-managed dashboard process without killing unrelated user processes.
5. As an operator, I get a clear degraded state when the dashboard cannot start or the port is unavailable.
6. As a maintainer, I can test the lifecycle layer without packaging a full desktop runtime.

## Requirements

### DS.1 Desktop Shell Command Contract

Add a new command or documented mode, recommended as `hermes desktop`, that wraps the existing dashboard lifecycle rather than bypassing it.

Acceptance:

- `hermes desktop` starts or reuses a local dashboard bound to `127.0.0.1`.
- It defaults to `/run-inspector`.
- It can run with `--port`, `--no-open`, and `--status` equivalents.
- It does not require gateway configuration.
- It does not write `.env`, `config.yaml`, provider profiles, or gateway config.
- It does not require Bash or Unix-style venv paths.

### DS.2 Process And Port Ownership

The shell must avoid duplicate process and port confusion.

Acceptance:

- The shell records only the process it starts, or explicitly detects an existing compatible dashboard.
- It reports the active URL and PID.
- If the requested port is busy, it reports a clear degraded state and recommended next action.
- It does not silently mutate gateway ports or HERMES config.
- Stop only targets shell-owned or clearly dashboard-owned processes, never broad Python processes.

### DS.3 Desktop Surface Strategy

The first implementation should separate lifecycle from packaging.

Acceptance:

- Phase 1 can open the default browser or a minimal local webview after starting the dashboard.
- Phase 2 may evaluate Tauri or Electron using the same lifecycle contract.
- Runtime choice must be documented with size, dependency, Windows compatibility, auto-update, tray, and build complexity tradeoffs.
- The React dashboard remains the source UI.

### DS.4 Tray And Notification Scope

Tray and notifications are useful but not first-slice blockers.

Acceptance:

- First slice may define tray states, but implementation can defer.
- Notifications, if later added, must only use redacted summary states such as waiting, failed, or needs action.
- No raw approval messages, prompts, tool args, command output, or file paths should appear in OS notifications.

### DS.5 Security And Privacy

Desktop shell must preserve current dashboard protections.

Acceptance:

- Default bind remains loopback only.
- Session token injection remains server-side and is not logged.
- Any shell logs redact URLs if they ever include token-bearing query strings.
- Public bind requires the existing explicit insecure path, not a desktop default.
- The shell never reads or prints provider credentials.

### DS.6 Observability And Recovery

The shell should make startup failures actionable.

Acceptance:

- Start failure includes reason class: port busy, frontend missing, FastAPI import failure, browser/webview open failure, or unknown.
- `status` reports PID, URL, route, started-at if known, and health check result.
- Recovery copy gives commands such as `hermes dashboard --status`, `hermes dashboard --stop`, or `hermes desktop --port <port>` where applicable.

## Architecture

Recommended shape:

1. Desktop shell command parses user intent.
2. It checks whether an existing local dashboard is compatible.
3. It starts the existing dashboard lifecycle with `--host 127.0.0.1 --no-open`.
4. It opens `http://127.0.0.1:<port>/run-inspector`.
5. It records shell-owned process metadata in a small local runtime file.
6. It reports status and stop behavior from that metadata plus existing dashboard process discovery.

The shell should not import or call Run Inspector internals directly. It should treat the dashboard route as the product surface.

## Runtime Options

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| Browser launcher only | Lowest risk, no new runtime, reuses dashboard immediately | Not a true desktop app, no tray/window ownership | Good first verification step |
| Python local webview | Potentially light, Python-owned lifecycle | Adds dependency and platform webview variance | Evaluate after lifecycle tests |
| Tauri | Small bundle, system WebView, good desktop shell model | Adds Rust/toolchain/build complexity | Candidate after DS lifecycle stabilizes |
| Electron | Mature JS desktop ecosystem, matches external Hermes desktop patterns | Heavy bundle, Node/Electron security/update burden | Candidate only if Tauri/webview cannot satisfy shell needs |

Recommendation: implement browser-launcher lifecycle first, then evaluate Tauri vs Electron from measured requirements instead of guessing.

## Execution Contract

When this PRD enters implementation, `.hermes/task.yaml` must add a desktop-shell slice with:

- lifecycle command task
- process/port ownership task
- `/run-inspector` route open task
- status/stop reporting task
- platform compatibility tests
- privacy/logging tests
- runtime packaging decision task

Every implementation task must include dependencies, acceptance criteria, verification commands, status, risk, and progress entries.

## Proposed Slices

### HRIDS-01 Desktop Shell PRD And Decision Contract

Outcome: this PRD plus `.hermes/task.yaml` execution contract.

Verification:

- PRD exists and links code evidence, issue lessons, goals, non-goals, requirements, risks, and proposed slices.
- `.hermes/task.yaml` includes desktop-shell task structure.
- `git diff --check` passes for PRD and task file.

### HRIDS-02 Local Dashboard Shell Command

Outcome: add a shell command that starts/reuses local dashboard and opens `/run-inspector`.

Verification:

- CLI tests for default args, `--port`, `--no-open`, existing dashboard reuse, port-busy behavior, and no config writes.
- Windows-safe subprocess/path tests.

### HRIDS-03 Shell Status And Stop

Outcome: status/stop for shell-owned dashboard lifecycle.

Verification:

- Tests that status reports URL/PID/route/health.
- Tests that stop does not target unrelated Python processes.
- Existing dashboard lifecycle tests continue passing.

### HRIDS-04 Desktop Runtime Decision Memo

Outcome: decide whether to proceed with browser launcher, Python webview, Tauri, or Electron packaging.

Verification:

- Decision compares install footprint, Windows compatibility, CI complexity, tray support, update model, security, and maintenance cost.
- No packaging implementation starts before the memo is accepted.

## Risks And Guardrails

| Risk | Guardrail |
| --- | --- |
| Duplicate dashboard processes | Reuse existing dashboard or record shell-owned PID; do not blindly spawn. |
| Port mutation | Report busy port; do not rewrite gateway or dashboard config silently. |
| Windows path failures | Avoid Bash and Unix venv assumptions; test native Windows command paths. |
| Credential exposure | Do not log session tokens, provider keys, prompts, or raw gateway payloads. |
| Installer scope creep | Keep installer and auto-update out of the first desktop shell slice. |
| Desktop runtime lock-in | Separate lifecycle contract from Tauri/Electron choice. |
| Broad process kill | Stop only shell-owned or verified dashboard processes. |

## Evaluation Plan

Backend/CLI:

- Command parser tests.
- Process ownership tests.
- Port-busy tests.
- No-config-write regression tests.
- Existing dashboard lifecycle tests.

Frontend/smoke:

- `/run-inspector` opens from shell-managed URL.
- Run Inspector panel loads with existing P13 behavior.
- No horizontal overflow on desktop and narrow viewports.

Platform:

- Windows native path smoke.
- macOS/Linux command smoke when available.
- No hardcoded `/bin/bash`, `venv/bin`, or POSIX-only process assumptions.

Security:

- Session token is not printed in shell output.
- Logs do not contain provider credentials.
- Public bind is not enabled by default.

## Definition Of Done

- Desktop shell PRD is committed.
- `.hermes/task.yaml` contains HRIDS task contract and progress entry.
- Next implementation slice is clear and testable.
- No desktop runtime or installer has been prematurely introduced.
- HERMES dashboard and Run Inspector remain the single UI source of truth.
