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

### Phase 4: Run Inspector Workbench

Add a Run Inspector section for:

- active parent and child agents
- current work checkpoint
- recent safe action ledger entries
- memory provider diagnostics
- unresolved long-term queue items

This should be read-only first.

### Phase 5: Review Gates

Add explicit commands or UI actions for:

- promote queue item to skill journal
- mark badcase as covered by a test
- export safe failure review summary

No automatic mutation of skills or configuration.

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
