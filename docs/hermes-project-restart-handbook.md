# HERMES Project Restart Handbook

Date: 2026-05-12
Owner: HERMES / product-manager workflow
Purpose: complete restart, handoff, and audit document for the current HERMES capability-improvement work.

This document is written for the case where the project is restarted in a new chat, new worktree, or new clone. It records what was researched, what was decided, which MCP and skill workflows were used, what was built, what is still risky, and how to continue without losing context.

## 1. Current State In One Page

### Main Product Decision

The current HERMES improvement path chose **Run Inspector / runtime observability first**.

Reason:

- HERMES users need to know what is running, stuck, waiting, failed, unsafe, or recoverable before deeper orchestration or skill-evaluation features can be trusted.
- External projects such as `graykode/abtop`, `openai/symphony`, `fathah/hermes-desktop`, and `EKKOLearnAI/hermes-web-ui` all pointed to the same product need: long-running agent work must have visible state, bounded recovery, and privacy-safe diagnostics.
- The product-manager SKILL benchmark showed that skill evaluation is valuable, but the higher-priority first investment for live HERMES operators is observability.

### Active Worktree To Use For Run Inspector UI / TUI / Desktop Work

Use this worktree for the current Run Inspector UI/TUI/desktop work:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui
```

Current branch:

```text
codex/hermes-run-inspector-ui-desktop
```

Backup remote:

```text
backup  https://github.com/lesadcoreydiabor-sketch/hermes-agent.git
```

Official upstream remote:

```text
origin  https://github.com/nousresearch/hermes-agent.git
```

Do not push to official `origin` unless explicitly deciding to open an upstream PR. The current workflow pushes only to `backup`.

### Worktree To Avoid For This Line

This older worktree contains parallel multi-agent / MCP / memory work and local dirty files:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest
```

It has unrelated modified files such as `hermes_cli/mcp_config.py`, `tools/mcp_tool.py`, `web/package.json`, docs, and many untracked `.hermes/dashboard-*.log` files. Do not use it for Run Inspector UI/TUI/desktop changes unless deliberately reconciling branches.

### Product-Manager SKILL Location

The product-manager skill is not inside this repo. It lives at:

```text
D:\product-manager
```

Important files:

```text
D:\product-manager\SKILL.md
D:\product-manager\references\source-grounded-product-work.md
D:\product-manager\references\hermes-product-work.md
D:\product-manager\evals\evals.json
D:\product-manager\evals\scoring-schema.json
D:\product-manager\evals\results\2026-05-10-smoke-score.md
D:\product-manager\artifacts\hermes-run-inspector-prd.md
D:\product-manager\artifacts\.hermes\task.yaml
```

### Most Important HERMES Artifacts

Current repo artifacts:

```text
docs/plans/hermes-run-inspector-prd.md
docs/plans/hermes-run-inspector-desktop-panel-requirements.md
docs/plans/hermes-run-inspector-desktop-panel-prd.md
docs/plans/hermes-run-inspector-event-integration-prd.md
docs/plans/hermes-run-inspector-desktop-shell-prd.md
docs/plans/hermes-desktop-runtime-decision.md
docs/plans/hermes-desktop-attention-notifications-prd.md
docs/plans/hermes-multi-agent-memory-prd.md
.hermes/task.yaml
```

`.hermes/task.yaml` is the execution contract. It contains task DAGs, risk flags, progress reporting, and failure review.

## 2. How The Project Evolved

### Phase 0: Original Strategic Discussion

The project began with the goal of improving HERMES by learning from high-quality GitHub projects. Early decisions:

- Do not blindly copy GitHub projects.
- Use open-source repositories as controlled evidence sources and task inspiration.
- Separate code evidence, user/problem evidence, product assumptions, and HERMES implementation decisions.
- For AGENTS validation, do not use full repo cloning as the only benchmark. Prefer real historical issue/PR-style tasks, hidden tests, reproducible environments, and incremental modifications.
- Use containerized or otherwise reproducible test environments with visible tests and hidden tests.
- Treat agent self-improvement as an external verified loop: execute, evaluate, attribute failure, update prompt/skill/workflow/memory, then revalidate.

This led to the idea that HERMES needs a stronger task-management and observability layer, not only a stronger model.

### Phase 1: Source Project Selection And GitNexus

GitNexus MCP was selected as the main way to inspect source projects through a code graph.

The project list grew to include:

- HERMES itself.
- GitNexus.
- `mattpocock/skills`.
- `tw93/Kami`.
- `graykode/abtop`.
- `addyosmani/agent-skills`.
- `openai/symphony`.
- `anthropics/skills`.
- `Lucasmantou/phoenix-immortal`.
- `fathah/hermes-desktop`.
- `EKKOLearnAI/hermes-web-ui`.

The key principle became:

> GitNexus/code graph explains how a system is built and where integration risk lives. GitHub Issues explain user pain. Neither replaces the other.

### Phase 2: product-manager SKILL Evolution

The user supplied a product-manager SKILL at `D:\product-manager`. It was tested and evolved so it could write HERMES-specific PRDs and execution contracts.

Important changes:

- `SKILL.md` now routes HERMES work to `references/hermes-product-work.md`.
- `SKILL.md` now requires GitHub Issues to be read by default when GitHub repos are used.
- `references/source-grounded-product-work.md` separates:
  - code evidence
  - issue evidence
  - transferable pattern
  - target implication
  - not-to-copy boundary
- `references/hermes-product-work.md` defines:
  - HERMES product surfaces
  - GitNexus + Issues reading standard
  - HERMES capability PRD sections
  - HERMES Execution Contract
  - `.hermes/task.yaml` template
  - failure review loop
  - agent-ready issue slicing
  - HERMES quality gate
- `evals/scoring-schema.json`, `evals/scoring-rubric.md`, and `evals/runbook.md` were added or strengthened.
- Evaluation prompts T1-T9 were created in `evals/evals.json`.

### Phase 3: product-manager SKILL Validation

The SKILL was benchmarked with baseline vs with-skill outputs.

Results from `D:\product-manager\evals\results\2026-05-10-smoke-score.md`:

| Task | Capability | Baseline | With Skill | Delta |
| --- | --- | ---: | ---: | ---: |
| T1 | route vague HERMES improvement ask | 22 / 27 | 23 / 27 | +1 |
| T2 | turn HERMES tools/MCP code facts into capability gap | 24 / 27 | 26 / 27 | +2 |
| T3 | design HERMES observability from abtop | 23 / 27 | 26 / 27 | +3 |
| T4 | design long-running orchestration from Symphony | 25 / 27 | 26 / 27 | +1 |
| T5 | design skill evaluation from Anthropic skills | 24 / 27 | 27 / 27 | +3 |
| T6 | convert HERMES PRD into agent-ready issues | 24 / 27 | 27 / 27 | +3 |
| T7 | document quality gates from Kami | 25 / 27 | 27 / 27 | +2 |
| T8 | prioritize next HERMES capability | 23 / 27 | 26 / 27 | +3 |

Aggregate:

```text
Baseline:   190 / 216, average 23.75 / 27
With Skill: 208 / 216, average 26 / 27
Net delta:  +18
```

Important regression found and fixed:

- T6 initially over-abstracted and invented a PRD-to-issue-generator meta-product when no concrete PRD was supplied.
- The SKILL was updated so that when asked to break down a PRD/plan, it must first find a concrete supplied or repo-local PRD/plan. If none exists, it must ask or produce a placeholder template instead of inventing a new product.

### Phase 4: First HERMES Capability PRD

The first capability PRD became:

```text
docs/plans/hermes-run-inspector-prd.md
```

Core decision:

Build a privacy-safe, read-only Run Inspector first.

It should answer:

- What is running?
- What is stuck?
- What tool or MCP server is involved?
- What data is safe to show?
- What should the operator do next?

Non-goals:

- no scheduler
- no automatic retry orchestrator
- no raw prompt/log/tool-argument display
- no full abtop clone
- no full Symphony daemon
- no required cloud tracing

### Phase 5: HERMES Execution Contract

The project adopted `.hermes/task.yaml` at repo root.

Purpose:

- split long work into dependency-aware tasks
- make work resumable
- record verification after each step
- pause on risky operations
- record failure reviews
- avoid silent drift during long agent sessions

Current `.hermes/task.yaml` status at time of this document:

```text
tasks: 104
completed: 104
task groups:
  HRI: 6
  HRIDP: 8
  HRIE: 6
  HRIG: 2
  HRIGF: 13
  HRIDS: 10
  HRIDR: 5
  HMAM: 12
  HMAMR: 12
  HMAMO: 30
```

Risk flags include:

- destructive file change
- database migration
- external API write
- credential or secret access
- public contract change
- config mutation
- platform-specific execution
- infinite loading or retry loop
- UI privacy leak
- unreviewed memory or skill mutation
- multi-agent ownership conflict
- ledger/checkpoint privacy leak

Important note:

`.hermes/task.yaml` currently includes both Run Inspector work and multi-agent memory/orchestration work. If restarting only the Run Inspector UI line, do not automatically resume HMAM tasks unless that is the chosen branch.

## 3. GitNexus / MCP Source Reading

### GitNexus Indexed Repositories

The following repositories were indexed by GitNexus MCP:

| GitNexus Repo | Path | Files / Flows | Use In This Project |
| --- | --- | ---: | --- |
| `hermes-agent` | `C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest` | 3095 files / 300 flows | HERMES architecture: agent loop, MCP, tools, status, dashboard, Run Inspector integration |
| `GitNexus` | `C:\Users\XQQ\Documents\New project 3\gitnexus-projects\GitNexus` | 984 files / 300 flows | Code graph MCP product pattern |
| `anthropics-skills` | `...\anthropics-skills` | 319 files / 89 flows | Skill packaging, progressive disclosure, eval patterns |
| `graykode-abtop` | `...\graykode-abtop` | 48 files / 93 flows | Runtime observability, agent/session status, local privacy |
| `tw93-Kami` | `...\tw93-Kami` | 65 files / 27 flows | document/report quality gates |
| `mattpocock-skills` | `...\mattpocock-skills` | 60 files / 0 flows | agent-ready issue briefs, source-aware delivery slicing |
| `addyosmani-agent-skills` | `...\addyosmani-agent-skills` | 54 files / 0 flows | agent skills taxonomy, spec-driven development, task breakdown |
| `openai-symphony` | `...\openai-symphony` | 73 files / 0 flows | unattended orchestration, workflow policy, workspace isolation |
| `Lucasmantou-phoenix-immortal` | `...\Lucasmantou-phoenix-immortal` | 2 files / 0 flows | failure review, healing loop, checkpoint/retry/report discipline |
| `fathah-hermes-desktop` | `...\fathah-hermes-desktop` | 164 files / 110 flows | desktop shell, IPC/event bridge, gateway panel patterns |
| `EKKOLearnAI-hermes-web-ui` | `...\EKKOLearnAI-hermes-web-ui` | 355 files / 300 flows | web dashboard, session/job/run monitoring, terminal/socket panel patterns |

### GitNexus Staleness Caveat

The indexed `hermes-agent` repo points to:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest
```

It is not the active Run Inspector UI worktree:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui
```

GitNexus reports the indexed `hermes-agent` as stale:

```text
Index is 122 commits behind HEAD
```

When working in `hermes-agent-run-inspector-ui`, GitNexus `detect_changes` returns:

```text
Repository not found
```

Therefore:

- Do not use old GitNexus impact results as proof for new UI-worktree changes.
- Either re-index the active worktree or clearly mark GitNexus impact as unavailable.
- For local-only UI slices, rely on focused tests, build, smoke, and code review until indexing is refreshed.

### GitNexus MCP Tools Used Or Considered

Important GitNexus tools and how they fit:

| Tool | Purpose | How It Was Used / Should Be Used |
| --- | --- | --- |
| `list_repos` | list indexed repositories and staleness | used to confirm all source repos and detect stale HERMES index |
| `query` | find code flows by concept | used/expected for architecture reading: agent loop, MCP, tools, dashboard, event flows |
| `context` | inspect a symbol in depth | used/expected after `query` for important symbols or handlers |
| `impact` | pre-change blast radius | used on earlier shared symbols/routes when available |
| `detect_changes` | analyze staged/unstaged change impact | worked in indexed old worktree; unavailable in new UI worktree |
| `route_map` | map API routes to handlers and consumers | useful for dashboard API changes |
| `api_impact` | pre-change report for API route handler | should be used before changing API route handlers |
| `shape_check` | API response shape vs consumer accesses | useful for dashboard endpoint changes |
| `tool_map` | MCP/RPC tool definitions | useful for tool/MCP system changes |

### Issue Reading Standard

The project explicitly changed the standard:

When using GitNexus to read a GitHub repository for HERMES product work, also read GitHub Issues unless the user excludes them or they are inaccessible.

Reason:

- Code explains implementation.
- Issues explain user pain.
- Both are needed to decide product scope, non-goals, risk flags, and acceptance criteria.

This was especially important for desktop/UI work.

Issue evidence read and applied:

| Repo | Issue Evidence | Product Effect |
| --- | --- | --- |
| `fathah/hermes-desktop` | install stuck on Windows, installed Hermes not detected, sessions infinite loading, Unix path assumptions, remote mode cannot read config/models | avoid installer-first desktop; avoid Unix-only assumptions; require explicit degraded states and no infinite loading |
| `EKKOLearnAI/hermes-web-ui` | gateway port auto-increment/config mutation, unauthenticated request loops, Windows gateway compatibility, tool-call UI overflow | keep Run Inspector read-only; avoid config mutation; add auth/offline/degraded states; test layout overflow |

## 4. External Project Pattern Decisions

### `graykode/abtop`

Useful:

- agent/session observability
- active process/tool state
- token/context/resource pressure
- local privacy boundaries
- operator-focused status surfaces

HERMES decision:

- Build Run Inspector as a structured runtime status surface.
- Do not copy abtop's Rust/TUI architecture or btop layout.

### `openai/symphony`

Useful:

- long-running unattended work
- workflow policy
- workpad/state
- workspace isolation
- retries and handoff

HERMES decision:

- Use Symphony as an orchestration design reference later.
- Do not build a full Symphony clone before HERMES has reliable runtime visibility.

### `GitNexus`

Useful:

- code graph
- symbol context
- route/API/tool maps
- impact analysis
- stale-index signals

HERMES decision:

- Use GitNexus for architecture evidence and blast-radius estimation.
- Do not treat code facts as product validation.
- Update the PM workflow so GitNexus reading is paired with issue reading.

### `anthropics/skills`

Useful:

- skill lifecycle
- trigger-rich descriptions
- progressive disclosure
- baseline vs with-skill evals
- regression loops

HERMES decision:

- Product-manager SKILL should be tested like a product.
- HERMES skill evaluation is valuable but should follow after Run Inspector.

### `mattpocock/skills`

Useful:

- agent-ready issues
- durable briefs
- AFK/HITL split
- vertical tracer-bullet slicing

HERMES decision:

- PRDs should convert into `.hermes/task.yaml` tasks and independently verifiable slices.
- Avoid fragile file-path-only instructions.

### `tw93/Kami`

Useful:

- document intent extraction
- source/material pass
- anti-pattern checks
- final artifact quality gate

HERMES decision:

- PM artifacts should include source ledgers, assumptions, anti-pattern checks, and parseable quality gates.
- Do not treat visual layout as the main quality signal.

### `addyosmani/agent-skills`

Useful:

- spec-driven development
- task breakdown
- Git workflow
- orchestration boundaries

HERMES decision:

- Use living specs, acceptance criteria, verification commands, and bounded task DAGs.

### `Lucasmantou/phoenix-immortal`

Useful:

- failure review
- action ledger
- working checkpoint
- long-term queue
- skills journal
- healing loop concept

HERMES decision:

- Adopt failure review and resumable task structure.
- Do not treat Phoenix's conceptual module names as HERMES code facts.
- Do not allow automatic self-modification or unreviewed skill mutation.

### `fathah/hermes-desktop`

Useful:

- desktop shell pattern
- IPC/event bridge
- gateway panel and runtime status ideas

HERMES decision:

- Build a thin desktop shell around existing dashboard first.
- Do not start with installer, native app stack, or config editor.

### `EKKOLearnAI/hermes-web-ui`

Useful:

- session/job/run dashboard patterns
- WebSocket terminal/status panel patterns
- route and API breadth

HERMES decision:

- Borrow state-model-driven dashboard ideas.
- Avoid gateway config mutation, unauthenticated retry loops, and broad write controls.

## 5. Product Documents Produced

### `docs/plans/hermes-run-inspector-prd.md`

Purpose:

- defines the P0 Run Inspector capability
- introduces versioned read-only run snapshot
- defines privacy/redaction boundaries
- defines tool/MCP health summary
- defines operator surface
- sets future P1/P2 directions

### `docs/plans/hermes-run-inspector-desktop-panel-requirements.md`

Purpose:

- captures desktop/web UI requirements from GitNexus and issue evidence
- records risk constraints from adjacent Hermes UI projects

### `docs/plans/hermes-run-inspector-desktop-panel-prd.md`

Purpose:

- defines the Run Inspector dashboard panel
- requires read-only local API
- requires explicit loading/degraded/auth/offline states
- requires sidebar signal and session/chat entry points
- sets desktop-wrapper readiness requirements

### `docs/plans/hermes-run-inspector-event-integration-prd.md`

Purpose:

- defines event contract and runtime event integration direction
- supports gateway run events, timeline, and future live observability

### `docs/plans/hermes-run-inspector-desktop-shell-prd.md`

Purpose:

- defines `hermes desktop`
- recommends browser-launcher lifecycle before Tauri/Electron
- defines process/port ownership, status, stop, and runtime record behavior

### `docs/plans/hermes-desktop-runtime-decision.md`

Purpose:

- records desktop runtime decision tradeoffs
- keeps Tauri/Electron/webview/package decisions separate from current dashboard lifecycle

### `docs/plans/hermes-desktop-attention-notifications-prd.md`

Purpose:

- defines attention notification product direction
- keeps notification opt-in, redacted, and local-safe

### `docs/plans/hermes-multi-agent-memory-prd.md`

Purpose:

- defines a parallel capability line for multi-agent memory and workbench
- should be continued in the multi-agent/memory worktree, not mixed casually into the Run Inspector UI worktree

## 6. What Was Built

### Run Inspector P0

Built:

- run snapshot schema
- session/gateway status reading
- tool and MCP health summary
- privacy flags and redaction
- failure review support
- CLI surface:

```text
hermes status --run-inspector
```

Important files:

```text
hermes_cli/run_inspector.py
hermes_cli/status.py
hermes_cli/main.py
tests/runtime/test_run_snapshot_schema.py
tests/runtime/test_run_snapshot_session.py
tests/runtime/test_run_snapshot_tools_mcp.py
tests/runtime/test_run_snapshot_redaction.py
tests/runtime/test_run_snapshot_failure_review.py
tests/hermes_cli/test_run_status.py
```

### Run Inspector Dashboard P1

Built:

- protected read-only dashboard API:

```text
GET /api/run-inspector
```

- React hook for Run Inspector status.
- Run Inspector page.
- sidebar signal.
- sessions/chat entry points.
- safe display and overflow guards.
- gateway run follow / recent runs / selected run detail.
- gateway launch/stop/approval controls through backend-safe routes.
- event timeline and attention preview.
- browser notification opt-in direction.

Important files include:

```text
hermes_cli/web_server.py
web/src/pages/RunInspectorPage.tsx
web/src/hooks/useRunInspectorStatus.ts
web/src/hooks/useRunInspectorEvents.ts
web/src/hooks/useRunInspectorAttention.ts
web/src/lib/api.ts
tests/hermes_cli/test_run_inspector_api.py
tests/hermes_cli/test_run_inspector_events_api.py
tests/hermes_cli/test_run_inspector_gateway_forwarder_api.py
tests/web/test_run_inspector_status_policy.py
```

### Desktop Shell

Built:

- `hermes desktop`
- default route `/run-inspector`
- local dashboard start/reuse
- loopback binding
- runtime record
- `--status`
- `--status --json`
- `--stop`
- stale record clearing
- status next action
- status attention level

Important files:

```text
hermes_cli/main.py
hermes_cli/desktop_shell_status.py
tests/hermes_cli/test_desktop_shell.py
tests/hermes_cli/test_desktop_shell_status_payload.py
```

### Desktop Shell In Run Inspector UI

Built in the active UI worktree:

- Desktop Shell card in Run Inspector.
- Desktop header badge.
- Health reason.
- Attention level.
- PID status and PID reason.
- URL display.
- Open URL action.
- Copy URL action.
- Next action row.
- Copy next command.
- Reuse command row and copy.
- Stop command row and copy.
- Narrow viewport overflow checks.

Recent commits in `codex/hermes-run-inspector-ui-desktop`:

```text
307db24c3 feat: open desktop shell url
e8bdc341e feat: copy desktop shell commands
5350b47d7 feat: show desktop pid reason
b9f8ea4c7 feat: copy desktop shell url
0200556d3 feat: print desktop attention level
6dcd24bf6 feat: show desktop health diagnostics
d0bb472bd feat: copy desktop next command
04102e246 feat: show desktop next action in Run Inspector
43434fc8f feat: print desktop status next action
```

Important files:

```text
web/src/pages/RunInspectorPage.tsx
web/src/pages/runInspectorDesktopStatus.ts
web/src/hooks/useRunInspectorDesktopStatus.ts
web/src/lib/api.ts
tests/web/test_run_inspector_desktop_status_policy.py
```

## 7. Verification History

### Product-Manager SKILL Verification

Product-manager skill benchmark:

```text
D:\product-manager\evals\results\2026-05-10-smoke-score.md
```

Result:

```text
Baseline:   190 / 216
With Skill: 208 / 216
Delta:      +18
```

### Run Inspector / Desktop Tests Frequently Used

Python test runner used from the old HERMES venv:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe
```

Common commands:

```powershell
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe -m pytest tests/web/test_run_inspector_desktop_status_policy.py -q -o addopts=

C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe -m pytest tests/hermes_cli/test_desktop_shell.py tests/hermes_cli/test_desktop_shell_status_payload.py -q -o addopts=

npm.cmd run build
```

Latest verified behaviors:

- Web desktop status policy tests passed.
- Desktop shell tests passed.
- Frontend build passed.
- Playwright smoke passed for desktop and narrow `/run-inspector` viewports.
- Open/Copy URL and Copy command buttons were visible.
- No horizontal overflow detected.

### Build Warning

Vite build still warns:

```text
Some chunks are larger than 500 kB after minification
```

This is a pre-existing bundle-size warning, not a blocker for the small Run Inspector UI slices. It should become a future frontend optimization task if dashboard size becomes a product concern.

## 8. Current Local Environment Notes

### Dependencies

The active UI worktree has web dependencies installed:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui\web\node_modules
```

Python venv is reused from:

```text
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv
```

Playwright is available through the old root `node_modules`. When running shell Playwright smoke tests, set:

```powershell
$env:NODE_PATH = 'C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\node_modules'
```

### Running A Temporary Dashboard For Smoke Tests

Use a temporary port and temporary `HERMES_HOME` when possible:

```powershell
$root = 'C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui'
$python = 'C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe'
$env:HERMES_WEB_DIST = Join-Path $root 'hermes_cli\web_dist'
```

For Desktop Shell UI states, a temporary `desktop_shell.json` may be written under a temporary `HERMES_HOME` to simulate shell-owned dashboard state.

Important PowerShell caveat:

- Do not assign to `$HOME`; it is a read-only PowerShell variable.
- Use names such as `$smokeHome`.

### Cleanup Rule

Before deleting a smoke directory, resolve and verify the path is inside the repo:

```powershell
$root = (Resolve-Path '.').Path
$smokePath = Join-Path $root '.hermes\smoke'
$resolvedSmokePath = (Resolve-Path -LiteralPath $smokePath).Path
if (-not $resolvedSmokePath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Unexpected smoke path: $resolvedSmokePath"
}
Remove-Item -LiteralPath $resolvedSmokePath -Recurse -Force
```

## 9. Known Problems And Decisions

### 9.1 Official Push Was Rejected

Earlier attempts to push to `nousresearch/hermes-agent` failed with 403 permission errors.

Decision:

- Do not push to official upstream.
- Use personal backup remote only.

### 9.2 GitHub Backup Push Sometimes Fails Temporarily

Observed error:

```text
fatal: unable to access 'https://github.com/lesadcoreydiabor-sketch/hermes-agent.git/': Empty reply from server
```

Resolution:

- Retry `git push backup <branch>`.
- The retry succeeded in multiple cases.

### 9.3 GitNexus Index Does Not Track The Active UI Worktree

Problem:

- GitNexus knows `hermes-agent-latest`, not `hermes-agent-run-inspector-ui`.
- `detect_changes` for the active UI worktree returns `Repository not found`.

Decision:

- Do not claim GitNexus staged impact for new UI-worktree changes.
- Re-index active worktree if GitNexus impact is required.

### 9.4 Old Worktree Is Dirty

The old worktree has unrelated dirty files and dashboard logs. Treat them as user/parallel-agent state.

Decision:

- Do not clean or revert old worktree unless explicitly requested.
- Keep Run Inspector UI/TUI/desktop work isolated in `hermes-agent-run-inspector-ui`.

### 9.5 Default Port 9119 May Already Be In Use

For smoke tests, `9119` may be occupied by an existing dashboard.

Decision:

- Do not kill unknown existing process.
- Use a temporary port such as `9156`, `9157`, etc.
- If a specific desktop-state path is needed, start your own dashboard with temporary `HERMES_HOME`.

### 9.6 Browser Tool / Node REPL Can Timeout

Observed:

- Browser/Node REPL interaction timed out once and reset.

Decision:

- Prefer Playwright through shell for deterministic frontend smoke when the browser plugin stalls.
- Use in-app browser only when useful for visible inspection.

### 9.7 UI/TUI Scope Boundary

Run Inspector UI work is allowed to add read-only display and safe local actions such as copy/open URL.

Do not add without explicit decision:

- stop/start mutation beyond existing controlled gateway/run controls
- config mutation
- credential reads
- raw logs/prompts/tool args
- automatic port mutation
- installer/native desktop runtime

## 10. MCP And Skill Process Record

### MCPs / Tools Used In This Project

#### GitNexus MCP

Role:

- source graph reading
- architecture exploration
- route/API analysis
- blast-radius thinking
- external project indexing

Key process:

1. Index or confirm repo in GitNexus.
2. Use `query` for concepts.
3. Use `context` for specific symbols.
4. Use `route_map` / `api_impact` before API route changes.
5. Use `detect_changes` when the current worktree is indexed.
6. Pair GitNexus code evidence with GitHub Issues for product decisions.
7. Record staleness or inaccessible issue evidence as a limitation.

#### Browser / GitHub / Issue Reading

Role:

- inspect GitHub pages and issues when product decisions need user pain evidence.
- create/verify personal backup repository workflows.

Important decision:

- Issue reading is now part of the default GitNexus source-bundle standard for GitHub repos.

#### Shell / Local Test Tools

Role:

- repo inspection with `rg`
- pytest
- npm build
- Playwright smoke
- git worktree/branch/remote management

Important commands:

```powershell
rg -n "pattern" path
git status --short --branch
git diff --check
git log --oneline -30
npm.cmd run build
```

#### Node / Playwright

Role:

- verify frontend at desktop and narrow viewports.
- check horizontal overflow.
- verify buttons and copy states.

Known setup:

```powershell
$env:NODE_PATH = 'C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\node_modules'
```

### Skills Used Or Created

#### product-manager SKILL

Location:

```text
D:\product-manager
```

Role:

- route product work
- write source-grounded PRDs
- convert PRDs into implementation-ready task contracts
- evaluate skill quality
- create HERMES-specific execution handoff

Important references:

```text
references/source-grounded-product-work.md
references/hermes-product-work.md
references/ai-product-prd.md
references/product-experience-gate.md
references/autonomous-execution-plan.md
references/pm-skill-lifecycle.md
references/skill-authoring-patterns.md
references/product-test-projects.md
references/quality-gates.md
```

Key rules added:

- For HERMES work, use `hermes-product-work.md`.
- For GitHub-source work, read Issues by default.
- Separate code evidence from issue evidence.
- Do not copy a repo's tech stack without target-product justification.
- If implementation is implied, produce `.hermes/task.yaml`.
- If asked to slice a PRD, first find a real PRD/plan. Do not invent a meta-product.
- Every task must be verifiable and resumable.

#### HERMES Execution Contract

Location:

```text
.hermes/task.yaml
```

Role:

- dependency-aware task list
- risk flags
- progress report
- failure review

This contract came directly from the product-manager SKILL evolution and the user-supplied insight that long tasks fail because they lack structure.

#### Failure Review Loop

Origin:

- Phoenix-style failure review discussion.
- Product-manager `hermes-product-work.md`.
- `.hermes/task.yaml`.

Rule:

A failure only matters if it changes a future requirement, eval, badcase, agent brief, task, or guardrail.

## 11. Product Roadmap From Here

### Continue Run Inspector UI/TUI/Desktop Line

Recommended next small slices:

1. Add a compact "Desktop Shell quick actions" grouping so URL/Open/Copy/Next/Reuse/Stop are easier to scan.
2. Add explicit button tooltips or titles if the design system supports them.
3. Add a visual distinction between safe actions (`Open`, `Copy`) and mutating actions elsewhere.
4. Add a Desktop Shell empty-state copy pass for no record / compatible dashboard / stale record.
5. Re-index active worktree in GitNexus and run impact analysis for the latest UI branch.
6. Decide whether to merge the UI worktree branch into the older P0 branch or keep it separate.

Do not jump to Tauri/Electron until:

- dashboard lifecycle is stable
- desktop shell status is reliable
- issue-driven risks are addressed
- UI overflow and auth loops are guarded

### Continue Multi-Agent / Memory Line

Use the other conversation/worktree for this.

Relevant PRD:

```text
docs/plans/hermes-multi-agent-memory-prd.md
```

Current concepts:

- action ledger
- working checkpoint
- long-term queue
- skills journal
- recovery gates
- handoff protocol
- learning review
- failure review export preview

Boundary:

- No automatic skill mutation.
- No raw transcripts.
- No raw memory provider payloads.
- Review before learning.

### Continue product-manager SKILL Line

Recommended next SKILL work:

1. Add or refresh T9 results for desktop panel using actual issue evidence.
2. Add a "restart handoff document" eval case similar to this document.
3. Add a scoring dimension for whether generated docs preserve worktree/branch/remote safety.
4. Add a source-bundle template that explicitly records GitNexus staleness and issue-access gaps.

## 12. Restart Procedure

### If Restarting In A New Chat

Start by telling the agent:

```text
Read docs/hermes-project-restart-handbook.md first.
Use C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui for Run Inspector UI/TUI/desktop work.
Do not touch C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest unless asked.
Push only to backup/codex/hermes-run-inspector-ui-desktop.
GitNexus does not index the active UI worktree yet; do not claim GitNexus impact unless it is re-indexed.
```

Then run:

```powershell
cd C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-run-inspector-ui
git status --short --branch
git log --oneline -10
```

### If Re-Cloning Or Re-Creating Worktree

Clone or restore HERMES, then add backup remote:

```powershell
git remote add backup https://github.com/lesadcoreydiabor-sketch/hermes-agent.git
git fetch backup
git checkout -b codex/hermes-run-inspector-ui-desktop backup/codex/hermes-run-inspector-ui-desktop
```

Install or verify dependencies:

```powershell
cd web
npm.cmd install
npm.cmd run build
```

Use Python venv if available:

```powershell
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe -m pytest tests/web/test_run_inspector_desktop_status_policy.py -q -o addopts=
```

### Minimum Health Check

```powershell
git status --short --branch
C:\Users\XQQ\Documents\Codex\2026-05-07\hermes-agent-latest\venv\Scripts\python.exe -m pytest tests/web/test_run_inspector_desktop_status_policy.py -q -o addopts=
cd web
npm.cmd run build
```

### When To Ask The User

Ask before:

- deleting files
- cleaning dirty old worktree
- pushing to official upstream
- opening an official PR
- mutating config
- reading credentials
- adding a native desktop runtime
- changing public API behavior
- merging Run Inspector UI branch with multi-agent branch

Do not ask for:

- focused read-only UI improvements
- tests
- local build
- backup remote push
- documentation updates

## 13. Open Questions

1. Should `codex/hermes-run-inspector-ui-desktop` eventually merge into `codex/hermes-run-inspector-p0`, or remain a separate backup branch?
2. Should GitNexus index the active UI worktree to restore accurate `detect_changes` and impact reports?
3. Should the old dirty worktree be cleaned, archived, or preserved for the multi-agent conversation?
4. Should product-manager SKILL be packaged into a reusable Codex skill location, or remain at `D:\product-manager`?
5. Should the next HERMES capability after Run Inspector be skill evaluation or multi-agent memory workbench? Current evidence says both matter; priority depends on whether the user is optimizing for live operation or skill-authoring quality.
6. Should desktop packaging choose browser launcher, Python webview, Tauri, or Electron after the shell lifecycle stabilizes?

## 14. Things Not To Forget

- The core failure mode this project is solving is not only model weakness; it is lack of structured task state, observability, recovery, and verification.
- GitHub projects are evidence sources, not blueprints.
- GitNexus gives code truth, not user truth.
- GitHub Issues give user pain, not implementation truth.
- `.hermes/task.yaml` is now part of the product architecture.
- Failure review is not optional for serious long-running agent work.
- Keep Run Inspector read-only by default.
- Keep UI safe to view and safe to share.
- Keep multi-agent/memory work separated from Run Inspector UI unless explicitly merging.
- Push to `backup`, not official `origin`.
