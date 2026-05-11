# HERMES Multi-Agent Memory PRD

Date: 2026-05-11
Status: Draft for implementation planning
Owner: Product Manager skill
Related:

- `.hermes/task.yaml`
- `docs/plans/hermes-run-inspector-prd.md`
- `docs/plans/hermes-run-inspector-event-integration-prd.md`
- `docs/plans/hermes-run-inspector-desktop-shell-prd.md`

## Summary

HERMES already has several pieces required for reliable multi-agent work:

- `delegate_task` can spawn bounded child agents.
- `AIAgent` tracks active children, delegate depth, interrupts, tool activity, and session ids.
- `MemoryManager` centralizes memory providers, system prompt context, turn sync, session end, session switch, and memory tool routing.
- `CheckpointManager` already protects risky file and terminal operations.
- Run Inspector now exposes a privacy-safe snapshot, event ledger, gateway run controls, attention preview, and desktop shell status.
- GitNexus can read HERMES code structure, symbols, call chains, route impact, and staged-change impact.

The next capability line should not start by adding a new autonomous orchestrator. It should first make multi-agent and memory behavior observable, structured, and recoverable.

The first milestone is a local, privacy-safe Multi-Agent Memory Workbench layered on top of existing delegation, memory, checkpoint, and Run Inspector systems.

## Problem

Long HERMES tasks can still fail for product reasons rather than model reasons:

- Parent and child agents have task ownership, but the user cannot easily inspect who owns what after a long run.
- Memory providers can recall, sync, and write data, but the operator cannot see safe lifecycle status without reading logs or provider internals.
- Failure review exists in `.hermes/task.yaml`, but runtime failures are not yet converted into a structured work ledger.
- Working checkpoints exist at filesystem/tool level, but there is no product-level checkpoint that says what was attempted, what remains, and what should be resumed.
- Useful lessons from failures are not yet routed into a reviewable long-term queue or skill journal.

This makes multi-agent work hard to trust. Adding more agents before adding a task/memory control layer increases hidden state and recovery cost.

## Source Evidence

### HERMES Code Evidence

| Area | Evidence | Implication |
| --- | --- | --- |
| Agent main loop | GitNexus and local reads show `run_agent.py:AIAgent` tracks `_delegate_depth`, `_active_children`, `_current_tool`, `_last_activity_desc`, interrupts, session ids, and per-turn memory hooks. | Multi-agent status can be derived without inventing a new runtime first. |
| Delegation | `tools/delegate_tool.py` has bounded child spawning, depth limits, active subagent registry, pause flag, interrupt support, and role handling. | The first multi-agent slice should observe and structure existing delegation rather than replace it. |
| Delegation safety | `DELEGATE_BLOCKED_TOOLS`, `subagent_auto_approve`, `orchestrator_enabled`, `max_spawn_depth`, and `max_concurrent_children` already bound child authority. | New orchestration policy should reuse these controls and surface their effective values. |
| Memory manager | `agent/memory_manager.py:MemoryManager` exposes provider registration, tool routing, prompt context, prefetch, sync, session hooks, pre-compress hook, delegation hook, memory-write hook, and shutdown. | Memory diagnostics can be provider-level and event-level without exposing memory contents. |
| Run Inspector events | `hermes_cli/run_inspector_events.py` stores bounded, redacted lifecycle events with replayable subscribers. | Multi-agent and memory events should reuse this ledger before adding new UI channels. |
| Kanban coordination | `hermes_cli/kanban_db.py` already models shared tasks, dependencies, workers, runs, heartbeats, retries, events, parent handoff results, and board stats. | Multi-agent task ownership should align with Kanban instead of creating a parallel scheduler. |
| Filesystem checkpoints | `tools/checkpoint_manager.py` and `hermes_cli/checkpoints.py` already manage rollback-oriented filesystem checkpoints. | Working checkpoints must be product-level summaries, not a replacement for filesystem rollback. |
| Existing execution contract | `.hermes/task.yaml` tracks task dependencies, risk flags, progress, and failure review. | Product-level task recovery should extend this contract rather than create another task file format. |
| Tests | `tests/tools/test_delegate.py`, `tests/run_agent/test_memory_sync_interrupted.py`, `tests/agent/test_memory_provider.py`, and Run Inspector tests already cover delegation, memory lifecycle, and safe dashboard behavior. | New slices can be validated with focused unit tests before touching broad agent paths. |

### External Project Patterns

| Source | Useful Pattern | HERMES Adaptation |
| --- | --- | --- |
| `abhigyanpatwari/GitNexus` | Code graph, context, impact, route/API surface analysis, stale-index signals. | Make external project reading a source bundle: code graph + docs + Issues + PRs + Discussions when available. |
| `Lucasmantou/phoenix-immortal` | Failure review, healing loop, action ledger, working checkpoint, long-term queue, skills journal. | Add local reviewable records, not automatic self-modification. |
| `graykode/abtop` | Agent/session observability and tool state monitoring. | Show multi-agent ownership and activity in Run Inspector. |
| `anthropics/skills` | Skills as packaged, evaluated capabilities. | Skills journal should create review candidates, not silently mutate skills. |
| `addyosmani/agent-skills` | Lifecycle commands, small task breakdown, verification gates, anti-rationalization checklists. | Task slices need acceptance, verification, and stop-the-line privacy gates. |
| `mattpocock/skills` | Shared language, PRD-to-issues, small composable engineering skills, feedback loops. | Multi-agent work needs stable domain terms and issue-ready slices before implementation. |
| `openai/symphony` | Orchestration state, bounded concurrency, workspace isolation, retry, reconciliation, workflow contracts. | Treat orchestration as a state machine with explicit claims, retries, and handoff states. |
| `EKKOLearnAI/hermes-web-ui` | Sessions/jobs/runs dashboard, WebSocket terminal, group chat, gateway management, auth and settings surfaces. | Borrow operator visibility patterns but avoid auto gateway restart/config mutation in this slice. |
| `fathah/hermes-desktop` | Desktop shell, local/remote backend setup, IPC/event bridge, sessions, memory, skills, and logs UI. | Keep HERMES core dashboard as the source UI; defer installer/config editor/native runtime work. |
| `tw93/Kami` | High-quality structured output. | Product outputs should become PRDs, task contracts, and review artifacts. |

### GitNexus Reading Standard

For external repositories, the product-manager workflow should move from "read code" to "read the project system":

1. Code structure and call graph: GitNexus `query`, `context`, `impact`, `route_map`, `api_impact`, and `detect_changes` where indexed.
2. Documentation: README, architecture docs, specs, runbooks, security docs, and skill docs.
3. Issues: open bugs, recurring feature requests, maintainer labels, and support pain.
4. Pull requests: recent merged work, rejected approaches, review comments, and release cadence.
5. Discussions or changelogs when present.

The output should name which source classes were actually read. If Issues/PR/Discussions are unavailable because credentials, network, or rate limits block access, the PRD must record that gap instead of implying they were reviewed.

## Goals

- Make active and recent child agents visible as a safe Run Inspector surface.
- Add a normalized event contract for delegation and memory lifecycle facts.
- Add a privacy-safe work ledger that records task attempts, verification, blockers, and next steps.
- Add a product-level working checkpoint that supports resume without exposing prompts, logs, or raw tool output.
- Add a reviewable long-term queue for learnings, badcases, and skill improvement candidates.
- Add a skills journal that records accepted learnings only after verification.
- Keep all first milestones additive, local, and reversible.
- Define a repeatable research source bundle so future PM skills can combine GitNexus code evidence with GitHub Issues, PRs, and docs.

## Non-Goals

- No free-running self-modifying agent.
- No automatic skill rewrite without review.
- No raw memory content, prompts, tool arguments, terminal output, diffs, secrets, or provider payloads in UI or ledgers.
- No replacement of `delegate_task` in the first milestone.
- No persistent database migration in the first milestone.
- No automatic training, SFT, DPO, or model update pipeline.
- No network writes to GitHub, Slack, or remote services.
- No desktop installer, gateway config editor, native tray, or packaged runtime in this milestone.

## Design Principles

1. Observe before orchestrating: first normalize what HERMES already does.
2. Append before mutate: action and learning records are append-only until reviewed.
3. Summarize before store: ledgers keep safe facts, not transcripts.
4. Review before learning: long-term memory and skills changes require explicit acceptance.
5. Reuse existing controls: delegate limits, Kanban ownership, Run Inspector privacy, and checkpoint rollback remain the guardrails.
6. Degrade safely: missing memory providers, stale GitNexus indexes, or unavailable GitHub APIs produce degraded evidence, not guessed conclusions.

## Product Model

### Work Unit

A work unit is one user-intent task or subtask that can be owned by a parent agent or child agent.

Safe fields:

- `work_id`
- `parent_work_id`
- `agent_id`
- `role`
- `title`
- `status`
- `started_at`
- `updated_at`
- `dependencies`
- `verification`
- `blockers`
- `next_step`
- `privacy_class`

Unsafe fields:

- raw prompt text
- raw transcript
- raw tool args
- raw terminal output
- file contents or diffs
- credentials, tokens, environment values

### Task Ownership Graph

The task ownership graph links:

- parent run
- child agent
- Kanban task
- `.hermes/task.yaml` slice
- gateway run id when present
- verification result

This graph should explain who owns each task, what it depends on, which worker touched it, and what must happen next. It must not expose child transcripts.

### Action Ledger

The action ledger is an append-only local record of safe work events:

- task started
- child spawned
- tool started
- tool completed
- verification run
- blocker recorded
- failure reviewed
- checkpoint updated
- long-term queue candidate created

The ledger should be bounded or rotated. It must be useful for debugging but not become a transcript database.

Minimum fields:

```yaml
schema_version: 1
event_id: string
event_type: string
timestamp: string
run_id: string | null
session_id: string | null
task_id: string | null
agent_id: string | null
parent_agent_id: string | null
status: string | null
summary: string
verification: string | null
blockers: []
next_step: string | null
privacy_class: safe | redacted_summary | local_only | omitted
```

### Working Checkpoint

The working checkpoint is the current resumable state:

- active work unit
- completed subtasks
- pending subtasks
- known blockers
- last verification result
- next recommended action

It should be generated from current task contracts and safe runtime events. It should not require reading raw logs.

Minimum fields:

```yaml
schema_version: 1
generated_at: string
source: generated | user_reviewed
active_capability: string
current_task_id: string | null
completed_tasks: []
pending_tasks: []
blocked_tasks: []
last_verification: string | null
open_decisions: []
next_step: string
degraded_reason: string | null
```

### Long-Term Queue

The long-term queue stores candidates for later improvement:

- recurring failures
- missing tests
- repeated recovery actions
- skill improvement ideas
- documentation gaps

Nothing in the queue is automatically applied. Queue entries need review, deduping, and acceptance criteria.

Queue states:

- `candidate`
- `needs_evidence`
- `accepted`
- `rejected`
- `applied`
- `superseded`

Accepted entries must name the target: memory fact, regression test, documentation update, skill update, product requirement, or code issue.

### Skills Journal

The skills journal stores accepted improvements after verification:

- source failure or task
- rule or workflow update
- affected skill
- evidence
- eval added or changed
- rollback note

This is the boundary between runtime learning and durable skill evolution.

### Failure Review Automation

`failure_review.entries` in `.hermes/task.yaml` remains the authoritative product review log for this repository. The new memory system may propose entries from failed verification or repeated runtime errors, but it should not silently mark them accepted. A failure-review candidate becomes durable only after it includes:

- what happened
- why it failed
- what changed or should change
- how it was verified
- added eval, badcase, or follow-up issue
- blocker state

## Architecture Direction

### Phase 1: Observe Existing Multi-Agent Behavior

Reuse current `delegate_task` and Run Inspector event ledger.

Add safe events for:

- `agent.parent.started`
- `agent.child.spawned`
- `agent.child.running`
- `agent.child.completed`
- `agent.child.failed`
- `agent.child.interrupted`
- `agent.child.timeout`

The first version should be best-effort. If recording fails, delegation continues.

### Phase 2: Memory Lifecycle Diagnostics

Expose provider-level memory diagnostics:

- provider names
- registered tool names
- initialized or unavailable state
- last sync status
- last prefetch status
- last session-end status

Do not expose memory content or provider raw responses.

### Phase 3: Work Ledger And Checkpoint

Add local safe files under `.hermes/`:

- `.hermes/action_ledger.jsonl`
- `.hermes/working_checkpoint.json`
- `.hermes/long_term_queue.jsonl`
- `.hermes/skills_journal.jsonl`

The first implementation should provide pure schema helpers and tests before runtime writes.

Runtime writes should be opt-in or explicitly wired by a later slice. Pure helpers come first so redaction and truncation can be tested independently.

Current delegate runtime opt-ins:

| Flag | Default | Writes | Behavior |
| --- | --- | --- | --- |
| `HERMES_DELEGATE_ACTION_LEDGER` | off | `.hermes/action_ledger.jsonl` | Mirrors redacted delegate child lifecycle events into the local action ledger. |
| `HERMES_DELEGATE_WORKING_CHECKPOINT` | off | `.hermes/working_checkpoint.json` | Refreshes the generated working checkpoint from safe task and ledger summaries. |
| `HERMES_DELEGATE_FAILURE_QUEUE` | off | `.hermes/long_term_queue.jsonl` | Captures failed or timed-out delegate children as reviewable recurring-failure candidates. |

These flags are intentionally separate. Enabling the action ledger alone must not create a checkpoint or queue candidate. Enabling checkpoint or failure queue writes must remain best-effort: write failures are logged at debug level and must not change delegate return values, child interruption behavior, depth limits, concurrency limits, or cost rollup.

### Phase 4: Run Inspector Workbench

Add a Run Inspector section for:

- active parent and child agents
- current work checkpoint
- recent safe action ledger entries
- delegate recovery gates with source counts
- memory provider diagnostics
- unresolved long-term queue items

This should be read-only first.

Recovery gates summarize the latest known lifecycle state for each delegate
child or work item. They combine two safe sources:

- `action_ledger`: persisted local entries written only when
  `HERMES_DELEGATE_ACTION_LEDGER` is explicitly enabled.
- `event_stream`: current in-process Run Inspector `agent.child.*` events.

The workbench must keep these sources distinguishable with bounded
`source_counts`. `event_stream` entries are live diagnostics, not durable
memory; they must not imply that `.hermes/action_ledger.jsonl` exists or that a
checkpoint can be reconstructed after process restart.

Recovery diagnostics also expose bounded lifecycle classification fields:

- `latest_event_type`, `latest_status`, `latest_timestamp`, and `latest_source`
  identify the newest visible delegate recovery state after the per-child or
  per-work latest-state collapse.
- `event_type_counts` groups the visible latest states by safe lifecycle event
  labels such as completed, failed, interrupted, timeout, or running.
- `status_counts` groups the same visible latest states by operator-facing
  status buckets such as completed, blocked, or monitoring.

These fields are diagnosis aids only. They must never expose raw delegate
goals, summaries, prompts, logs, tool arguments, diffs, file contents, absolute
paths, provider memory payloads, or secret-looking values. Empty workbench
payloads should return empty count maps and null latest markers so dashboard and
TUI renderers can distinguish quiet state from missing data without guessing.

### Phase 5: Review Gates

Add explicit commands or UI actions for:

- promote queue item to skill journal
- mark badcase as covered by a test
- export safe failure review summary

No automatic mutation of skills or configuration.

The first implementation step is a review request preview. It normalizes a
manual operator intent into a redacted `pending_review` payload with source
queue or candidate id, target type, target reference, evidence, verification,
rollback note, requested effect, and blocked effects. Building this payload must
not append the skills journal, mark a badcase covered, export a file, edit
skills, write provider memory, mutate config, or mutate `.hermes/task.yaml`.
The Run Inspector memory workbench can surface these requests as read-only
diagnostics with ready and blocked counts; blocked requests must list missing
requirements instead of guessing or silently filling review evidence.
Operator views should render this as status and evidence readiness only. They
must not add approve, promote, export, mark-covered, retry, spawn, or config
mutation controls until a separate reviewed mutation contract exists.
The export path starts with a preview helper that turns reviewable queue entries
into a bounded, redacted failure review summary payload. The preview may contain
counts, safe entry summaries, and blocked effects, but it must not write an
export file, mark queue entries applied, or mutate any durable learning state.

### Phase 6: Agent-Ready Work Distribution

Use `.hermes/task.yaml` plus Kanban task context to define:

- role: planner, orchestrator, worker, reviewer, observer
- write ownership
- dependency ids
- allowed tools or toolsets
- verification command
- handoff payload
- conflict policy

The initial policy can be documentation and schema only. Runtime scheduling changes should wait until the ledger and checkpoint are observable.

Minimum agent-ready task assignment template:

```yaml
schema_version: 1
task_id: string
title: string
role: planner | orchestrator | worker | reviewer | observer
owner:
  agent_id: string | null
  parent_agent_id: string | null
  human_owner: string | null
status: planned | queued | running | blocked | review | completed | failed
dependencies:
  task_ids: []
  required_artifacts: []
write_scope:
  files: []
  directories: []
  forbidden_paths: []
  shared_contracts: []
allowed_tools:
  toolsets: []
  commands: []
  disallowed: []
delegate_limits:
  max_depth: number | null
  max_parallel_workers: number | null
  interrupt_policy: cooperative | parent_owned | manual_review
verification:
  command: string
  expected_signal: string
  required_before_handoff: true
handoff_payload:
  summary: string
  changed_files: []
  verification_result: string | null
  blockers: []
  next_step: string
  privacy_class: redacted_summary
conflict_policy:
  write_scope_must_be_disjoint: true
  shared_contract_requires_reviewer: true
  conflict_resolution: pause_and_handoff | reviewer_decides | human_decides
```

Role policy:

- Planner creates PRD slices, task ids, acceptance criteria, risk flags, and safe handoff payloads.
- Orchestrator assigns disjoint write scopes, watches dependencies, and records action ledger or checkpoint summaries.
- Worker owns implementation only inside the assigned write scope and reports changed files, verification, blockers, and next step.
- Reviewer checks contracts, privacy, tests, and conflict policy before a shared schema or public API change is accepted.
- Observer reads status, events, diagnostics, and ledgers without mutating code, config, memory, or remote systems.

Conflict and handoff rules:

- Parallel workers must have disjoint write scopes. Shared files such as `.hermes/task.yaml`, API contracts, generated schemas, or common UI types require orchestrator sequencing and reviewer handoff.
- Existing `delegate_task` depth, concurrency, cost, heartbeat, and interrupt behavior remains the runtime guardrail. This policy does not bypass those limits.
- Kanban task ownership remains the human-visible ownership layer; this template is the agent handoff payload that can be attached to Kanban or `.hermes/task.yaml`.
- Handoffs must not include raw child transcripts, raw prompts, raw logs, tool arguments, diffs, secrets, or private file bodies.
- A blocked worker returns a blocker summary and proposed next step instead of widening its own write scope.

### Phase 7: External Source Bundle

Add a standard PM research artifact that records:

- repository
- code evidence source
- docs read
- Issues read
- PRs read
- Discussions/changelog read
- missing source classes
- transferable pattern
- explicit non-transferable risk

This can become the input format for future product-manager skill evals.

Minimum source-bundle template:

```yaml
schema_version: 1
repository:
  name: string
  url: string
  default_branch: string | null
  commit: string | null
  researched_at: string
gitnexus:
  indexed_repo: string | null
  indexed_at: string | null
  indexed_commit: string | null
  freshness: fresh | stale | unknown
  evidence:
    - symbol_or_process: string
      file: string | null
      summary: string
source_classes:
  code:
    status: read | partial | missing | unavailable
    evidence:
      - source: gitnexus | local_search | docs
        summary: string
        reference: string | null
  docs:
    status: read | partial | missing | unavailable
    evidence:
      - title: string
        url_or_path: string | null
        summary: string
  issues:
    status: read | partial | missing | unavailable
    evidence:
      - id: string
        title: string
        state: open | closed | unknown
        summary: string
  prs:
    status: read | partial | missing | unavailable
    evidence:
      - id: string
        title: string
        state: open | merged | closed | unknown
        summary: string
  discussions_or_changelog:
    status: read | partial | missing | unavailable
    evidence:
      - title: string
        url_or_path: string | null
        summary: string
evidence_gaps:
  - type: stale_gitnexus_index | missing_credentials | network_failure | rate_limit | missing_source_class | unknown
    source_class: code | docs | issues | prs | discussions_or_changelog | unknown
    detail: string
transferable_patterns:
  - pattern: string
    evidence_refs: []
    hermes_fit: direct | adapted | rejected
non_transferable_risks:
  - risk: string
    reason: string
pm_outputs:
  prd_implication: string
  agent_ready_issue_hint: string
privacy_class: redacted_summary
```

Source-bundle rules:

- Read code structure through GitNexus when indexed; if the index is stale, record the stale commit or timestamp and cross-check with local search.
- Read docs, Issues, PRs, and Discussions/changelog as separate source classes; do not imply coverage when one class is missing.
- Record GitHub credential failures, network failures, and rate limits as evidence gaps instead of silently dropping those sources.
- Keep GitHub access read-only for this artifact. The template does not create issues, comment on PRs, mutate labels, or write remote state.
- Summaries must stay privacy-safe: no raw prompts, secrets, full logs, diffs, private file bodies, or tokenized URLs.

## Privacy And Safety Rules

- Default all new records to `privacy_class: redacted_summary`.
- Redact secret-like identifiers in run ids, session ids, tool names, messages, and paths.
- Truncate long strings.
- Store only summaries and stable ids.
- Treat write operations under `.hermes/` as local-only.
- Never record approval payloads, raw prompts, raw outputs, diffs, or environment values.
- If redaction confidence is low, omit the field.

## Rollout And Review Gates

Local record ownership:

| Record | Owner | Purpose | Write Rule | Review Gate |
| --- | --- | --- | --- | --- |
| `.hermes/action_ledger.jsonl` | Orchestrator or explicit runtime integration | Append safe work events for debugging and resume. | Explicit local append only; no raw transcript storage. | Review redaction regressions before adding new event fields. |
| `.hermes/working_checkpoint.json` | Generated checkpoint helper or orchestrator | Current resumable summary of active, pending, blocked, verified, and next work. | Generated from safe task and ledger summaries; no raw logs. | Human or reviewer can inspect before using as resume source. |
| `.hermes/long_term_queue.jsonl` | Reviewer or failure candidate helper | Reviewable improvement candidates for recurring failures, missing tests, recovery patterns, docs gaps, and skill ideas. | Candidate or needs-evidence states only unless explicitly reviewed. | Accepted, applied, or superseded states require reviewer evidence. |
| `.hermes/skills_journal.jsonl` | Reviewer | Accepted skill learnings after evidence and eval coverage exist. | Append accepted summaries only; never edit `SKILL.md` automatically. | Requires source evidence, accepted change, eval coverage, verification, and rollback note. |
| `.hermes/task.yaml` `failure_review.entries` | Product/reviewer | Authoritative product review log for failed verification and redaction blockers. | Manual or explicit helper-assisted update only. | Redaction failures stay blockers until a regression exists. |

Review gates:

- Long-term memory changes are never silently applied. Queue entries can propose memory facts, but promotion to a provider requires a later explicit provider integration and review.
- Skill changes are never silently applied. A skills journal entry is evidence, not a patch to a skill package.
- Failure-review candidates are not accepted by default. They must include what happened, likely cause, verification command or evidence, proposed badcase, and blocker state.
- Failure-review export previews are build-only diagnostics. They may summarize eligible long-term queue items, but they must not create files, mark queue entries applied, edit skills, write memory, mutate config, mutate tasks, dispatch tools, or spawn agents.
- Redaction failures are blocker-class candidates. They must not expose the leaked value and must add or reference a regression before promotion.
- Rollback notes are required for skills journal entries so an accepted learning can be removed or revised without rewriting history.

Run Inspector display policy:

- Missing action ledger, checkpoint, queue, journal, or memory diagnostics surfaces as degraded or unavailable state, not as a dashboard crash.
- Empty local files surface as empty state.
- Active child-agent events surface as active work; failed, interrupted, timeout, or blocked items surface as attention state.
- Recovery gates show the latest per-child state and source counts only; stale spawned or running states are hidden after the same child completes, fails, times out, or is interrupted.
- `event_stream` recovery gates can remain visible while the action ledger is missing, but the missing ledger stays degraded metadata.
- Memory provider diagnostics show provider name, availability, initialized state, tool names, and lifecycle status only. They do not show memory contents, provider raw responses, prompts, or tool arguments.
- Failure-review export previews can surface as read-only workbench payloads with summary lines, counts, blocked effects, and degraded state only; the UI must not render export, approve, write-file, or mark-applied controls from that preview.
- The Multi-Agent Memory workbench is read-only. It does not approve, deny, stop, spawn, write memory, edit skills, mutate config, or write remote systems.

Migration limits:

- The first implementation is local and process-aware, not a cross-process database. Gateway, dashboard, CLI, and delegated child processes may have separate in-memory event ledgers.
- Cross-process ledger merging needs an explicit bridge or persistent store design before it can be treated as complete.
- JSONL helpers are append-by-explicit-call only. Automatic runtime writes should stay behind dedicated slices with redaction tests and failure-review coverage.
- Delegate runtime persistence is opt-in per file class. Operators must enable the ledger, checkpoint, and failure queue flags independently so observation does not silently become long-term learning.
- Source bundles are read-only research artifacts. GitHub Issues, PRs, and Discussions evidence can be missing because of credentials, network, or rate limits; those gaps must be recorded instead of inferred.

## Evaluation

Minimum evals for the first implementation slices:

- Multi-agent event helpers normalize child lifecycle events.
- Delegation continues when event recording fails.
- Interrupted child agents record safe interrupted status.
- Memory diagnostics list provider names and tool names without memory contents.
- Action ledger rejects or redacts secret-looking fields.
- Working checkpoint can be regenerated from safe task and event summaries.
- Run Inspector UI shows empty, active, failed, and degraded states without overflow.
- Long-term queue state transitions reject auto-apply without review.
- Skills journal entries require source evidence, verification, and rollback notes.
- Source bundle records missing Issues/PR evidence instead of implying coverage.

## Open Questions

- Should `.hermes/action_ledger.jsonl` be enabled by default or behind a config flag?
- Should the working checkpoint be purely generated or also user-editable?
- Should memory provider diagnostics live in Run Inspector P0 snapshot or a separate endpoint?
- Should delegated child events be emitted from `delegate_tool.py` only, or also from `AIAgent` lifecycle hooks?
- How should multi-process gateway and CLI runs merge work ledgers without a database migration?
- Should GitHub Issues/PR reading use `gh`, GitHub REST, GitHub GraphQL, or a GitNexus extension?
- Should accepted long-term queue entries mirror into external memory providers, or stay local until a provider explicitly opts in?

## Implementation Slices

The first safe path is:

1. Define this PRD and `.hermes/task.yaml` execution contract.
2. Add pure schemas and redaction helpers for multi-agent work events.
3. Mirror existing `delegate_task` child lifecycle into the Run Inspector event ledger.
4. Add read-only memory diagnostics helper and tests.
5. Add local action ledger schema and append helper with redaction.
6. Add working checkpoint generation from safe task and ledger data.
7. Add long-term queue and skills journal schema helpers.
8. Add Run Inspector workbench UI.
9. Add failure-review candidate generation from failed verification and repeated runtime errors.
10. Add a GitNexus source-bundle template for code + Issues + PR + docs research.
11. Add agent-ready task ownership and handoff templates.
12. Add rollout docs that explain local-only storage, redaction, review gates, and migration limits.

Each slice should be independently testable and reversible.
