"""Read-only Multi-Agent Memory Workbench summary helpers."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import yaml

from hermes_cli.action_ledger import (
    ACTION_LEDGER_PATH,
    normalize_action_ledger_entry,
)
from hermes_cli.agent_task_assignment import (
    build_agent_task_assignments_from_task_contract,
    plan_agent_assignment_batches,
    summarize_agent_handoff_protocol,
    summarize_agent_task_assignments,
)
from hermes_cli.learning_journal import (
    LONG_TERM_QUEUE_PATH,
    SKILLS_JOURNAL_PATH,
    normalize_long_term_queue_entry,
    normalize_skills_journal_entry,
)
from hermes_cli.working_checkpoint import build_working_checkpoint_from_files
from utils import is_truthy_value


WORKBENCH_SCHEMA_VERSION = 1
WORKBENCH_PRIVACY_CLASS = "redacted_summary"

SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96
ENTRY_LIMIT = 12

RUNTIME_PERSISTENCE_FLAGS = (
    {
        "name": "action_ledger",
        "env_var": "HERMES_DELEGATE_ACTION_LEDGER",
        "path": ".hermes/action_ledger.jsonl",
    },
    {
        "name": "working_checkpoint",
        "env_var": "HERMES_DELEGATE_WORKING_CHECKPOINT",
        "path": ".hermes/working_checkpoint.json",
    },
    {
        "name": "failure_queue",
        "env_var": "HERMES_DELEGATE_FAILURE_QUEUE",
        "path": ".hermes/long_term_queue.jsonl",
    },
)

ACTIVE_STATUSES = frozenset({"queued", "running", "started", "in_progress", "waiting"})
FAILED_STATUSES = frozenset(
    {"failed", "error", "timeout", "interrupted", "cancelled", "canceled"}
)
TERMINAL_STATUSES = frozenset({"completed", "done", "success", "succeeded"})

_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password|credential)\s*[:=]\s*[^,\s;]+"
    r"|\b(?:sk|gh[pousr])[-_][A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s]+)|(?:/(?:Users|home|tmp|var|etc|mnt|workspace)/[^\s]+)",
    re.IGNORECASE,
)
_DIFF_RE = re.compile(r"(^|\n)(diff --git|@@\s|[+-]{3}\s)", re.IGNORECASE)
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9_.:/ -]+")


def build_multi_agent_memory_workbench(
    root: str | Path = ".",
    *,
    events: Optional[Iterable[Dict[str, Any]]] = None,
    memory_diagnostics: Optional[Dict[str, Any]] = None,
    generated_at: Optional[str] = None,
    limit: int = ENTRY_LIMIT,
) -> Dict[str, Any]:
    """Build a bounded, redacted Run Inspector workbench payload."""

    workspace = Path(root)
    safe_limit = _safe_limit(limit)
    recent_events = list(events or [])
    checkpoint = build_working_checkpoint_from_files(
        workspace / ".hermes" / "task.yaml",
        workspace / ACTION_LEDGER_PATH,
        generated_at=generated_at,
    )
    action_entries, action_degraded = _read_jsonl_entries(
        workspace / ACTION_LEDGER_PATH,
        normalize_action_ledger_entry,
        missing_reason="action_ledger_missing",
        limit=safe_limit,
    )
    queue_entries, queue_degraded = _read_jsonl_entries(
        workspace / LONG_TERM_QUEUE_PATH,
        normalize_long_term_queue_entry,
        missing_reason="long_term_queue_missing",
        limit=safe_limit,
    )
    journal_entries, journal_degraded = _read_jsonl_entries(
        workspace / SKILLS_JOURNAL_PATH,
        normalize_skills_journal_entry,
        missing_reason="skills_journal_missing",
        limit=safe_limit,
    )
    active_work = _active_work_from_events(recent_events, limit=safe_limit)
    recovery_entries = _dedupe_recovery_gate_entries(
        [
            *action_entries,
            *_delegate_recovery_entries_from_events(recent_events, limit=safe_limit),
        ],
        limit=safe_limit,
    )
    memory = _memory_summary(memory_diagnostics)
    runtime_persistence = _runtime_persistence_summary(workspace)
    agent_assignments = _agent_assignment_summary(workspace, limit=safe_limit)

    degraded_reasons = [
        checkpoint.get("degraded_reason"),
        action_degraded,
        queue_degraded,
        journal_degraded,
        memory.get("degraded_reason"),
        agent_assignments.get("degraded_reason"),
    ]
    status = _workbench_status(
        active_work=active_work,
        checkpoint=checkpoint,
        action_entries=action_entries,
        queue_entries=queue_entries,
        journal_entries=journal_entries,
        memory=memory,
        degraded_reason=_join_reasons(degraded_reasons),
    )

    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "status": status,
        "status_reason": _status_reason(status, active_work, checkpoint),
        "active_work": active_work,
        "memory": memory,
        "runtime_persistence": runtime_persistence,
        "agent_assignments": agent_assignments,
        "checkpoint": checkpoint,
        "action_ledger": {
            "entries": action_entries,
            "recovery_gates": _delegate_recovery_gate_summary(
                recovery_entries,
                limit=safe_limit,
            ),
            "degraded_reason": action_degraded,
        },
        "long_term_queue": {
            "entries": queue_entries,
            "unresolved_count": _unresolved_queue_count(queue_entries),
            "degraded_reason": queue_degraded,
        },
        "skills_journal": {
            "entries": journal_entries,
            "degraded_reason": journal_degraded,
        },
        "degraded_reason": _join_reasons(degraded_reasons),
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def empty_multi_agent_memory_workbench(
    *,
    generated_at: Optional[str] = None,
    degraded_reason: Any = None,
) -> Dict[str, Any]:
    """Return a safe unavailable workbench payload."""

    reason = _safe_summary(degraded_reason, fallback="workbench_unavailable")
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "status": "unavailable",
        "status_reason": "Workbench unavailable",
        "active_work": [],
        "memory": {
            "status": "unavailable",
            "provider_count": 0,
            "providers": [],
            "registered_tools": [],
            "degraded_reason": reason,
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
        },
        "runtime_persistence": _runtime_persistence_summary(Path(".")),
        "agent_assignments": _empty_agent_assignment_summary(reason),
        "checkpoint": {
            "schema_version": 1,
            "generated_at": generated_at or _utc_now_iso(),
            "source": "generated",
            "active_capability": "unknown",
            "current_task_id": None,
            "completed_tasks": [],
            "pending_tasks": [],
            "blocked_tasks": [],
            "last_verification": None,
            "open_decisions": [],
            "next_step": "No next step recorded.",
            "degraded_reason": reason,
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
        },
        "action_ledger": {
            "entries": [],
            "recovery_gates": _delegate_recovery_gate_summary([], limit=ENTRY_LIMIT),
            "degraded_reason": reason,
        },
        "long_term_queue": {
            "entries": [],
            "unresolved_count": 0,
            "degraded_reason": reason,
        },
        "skills_journal": {"entries": [], "degraded_reason": reason},
        "degraded_reason": reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _read_jsonl_entries(
    path: Path,
    normalizer: Callable[[Dict[str, Any]], Dict[str, Any]],
    *,
    missing_reason: str,
    limit: int,
) -> tuple[list[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return [], missing_reason
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], f"{path.stem}_read_error"

    entries = []
    reasons = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            reasons.append(f"{path.stem}_parse_error")
            continue
        if not isinstance(payload, dict):
            reasons.append(f"{path.stem}_entry_invalid")
            continue
        try:
            entries.append(normalizer(payload))
        except (TypeError, ValueError):
            reasons.append(f"{path.stem}_entry_invalid")

    return entries[-limit:], _join_reasons(reasons)


def _agent_assignment_summary(workspace: Path, *, limit: int) -> Dict[str, Any]:
    reasons: list[str] = []
    contract = _read_task_contract(workspace / ".hermes" / "task.yaml", reasons)
    assignments = build_agent_task_assignments_from_task_contract(contract)
    summary = summarize_agent_task_assignments(assignments)
    degraded_reason = _join_reasons([*reasons, summary.get("degraded_reason")])
    parallel_plan = plan_agent_assignment_batches(assignments)
    handoff_protocol = summarize_agent_handoff_protocol(assignments)
    if degraded_reason:
        parallel_plan = {
            **parallel_plan,
            "degraded_reason": _join_reasons(
                [parallel_plan.get("degraded_reason"), degraded_reason]
            ),
        }
        handoff_protocol = {
            **handoff_protocol,
            "degraded_reason": _join_reasons(
                [handoff_protocol.get("degraded_reason"), degraded_reason]
            ),
        }
    return {
        "summary": summary,
        "parallel_plan": parallel_plan,
        "handoff_protocol": handoff_protocol,
        "assignments": assignments[:limit],
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _empty_agent_assignment_summary(reason: Any) -> Dict[str, Any]:
    summary = summarize_agent_task_assignments([])
    degraded_reason = _safe_label(reason, fallback=None, limit=LABEL_LIMIT)
    parallel_plan = {
        **plan_agent_assignment_batches([]),
        "degraded_reason": degraded_reason,
    }
    handoff_protocol = {
        **summarize_agent_handoff_protocol([]),
        "degraded_reason": degraded_reason,
    }
    return {
        "summary": summary,
        "parallel_plan": parallel_plan,
        "handoff_protocol": handoff_protocol,
        "assignments": [],
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _read_task_contract(path: Path, reasons: list[str]) -> Dict[str, Any]:
    if not path.exists():
        reasons.append("task_contract_missing")
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        reasons.append("task_contract_parse_error")
        return {}
    if not isinstance(loaded, dict):
        reasons.append("task_contract_invalid")
        return {}
    return loaded


def _runtime_persistence_summary(workspace: Path) -> Dict[str, Any]:
    flags = []
    enabled_count = 0
    for spec in RUNTIME_PERSISTENCE_FLAGS:
        enabled = is_truthy_value(os.environ.get(spec["env_var"], False))
        if enabled:
            enabled_count += 1
        flags.append(
            {
                "name": spec["name"],
                "env_var": spec["env_var"],
                "enabled": enabled,
                "path": spec["path"],
                "exists": (workspace / spec["path"]).exists(),
                "privacy_class": WORKBENCH_PRIVACY_CLASS,
            }
        )

    return {
        "status": "enabled" if enabled_count else "disabled",
        "enabled_count": enabled_count,
        "flags": flags,
        "degraded_reason": None,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _delegate_recovery_gate_summary(
    entries: Iterable[Dict[str, Any]],
    *,
    limit: int,
) -> Dict[str, Any]:
    completed_count = 0
    blocked_count = 0
    monitoring_count = 0
    verification_task_ids: list[str] = []
    blocked_task_ids: list[str] = []
    monitoring_task_ids: list[str] = []
    next_steps: list[str] = []
    blockers: list[str] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event_type = _safe_label(entry.get("event_type"), fallback="", limit=LABEL_LIMIT)
        if not event_type.startswith("agent.child."):
            continue

        status = _safe_status(entry.get("status")) or "unknown"
        task_id = (
            _safe_identifier(entry.get("task_id"))
            or _safe_identifier(entry.get("work_id"))
            or _safe_identifier(entry.get("run_id"))
        )
        if status in TERMINAL_STATUSES or event_type == "agent.child.completed":
            completed_count += 1
            if entry.get("verification") and task_id:
                _append_unique(verification_task_ids, task_id, limit=limit)
        elif status in FAILED_STATUSES or event_type in {
            "agent.child.failed",
            "agent.child.timeout",
            "agent.child.interrupted",
        }:
            blocked_count += 1
            if task_id:
                _append_unique(blocked_task_ids, task_id, limit=limit)
        elif status in ACTIVE_STATUSES or event_type in {
            "agent.child.spawned",
            "agent.child.running",
        }:
            monitoring_count += 1
            if task_id:
                _append_unique(monitoring_task_ids, task_id, limit=limit)

        next_step = _safe_summary(entry.get("next_step"), fallback=None)
        if next_step:
            _append_unique(next_steps, next_step, limit=limit)
        for blocker in entry.get("blockers") or []:
            safe = _safe_summary(blocker, fallback=None)
            if safe:
                _append_unique(blockers, safe, limit=limit)

    status = "empty"
    if blocked_count:
        status = "blocked"
    elif monitoring_count:
        status = "monitoring"
    elif completed_count:
        status = "ready"

    return {
        "status": status,
        "completed_count": completed_count,
        "blocked_count": blocked_count,
        "monitoring_count": monitoring_count,
        "verification_task_ids": verification_task_ids,
        "blocked_task_ids": blocked_task_ids,
        "monitoring_task_ids": monitoring_task_ids,
        "next_steps": next_steps,
        "blockers": blockers,
        "degraded_reason": None,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _delegate_recovery_entries_from_events(
    events: Iterable[Dict[str, Any]],
    *,
    limit: int,
) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = _safe_label(
            event.get("type") or event.get("event_type"),
            fallback="",
            limit=LABEL_LIMIT,
        )
        if not event_type.startswith("agent.child."):
            continue
        status = _safe_status(event.get("status")) or _status_from_delegate_event_type(
            event_type
        )
        message = event.get("message") or event.get("summary") or event.get("title")
        entries.append(
            {
                "event_id": _safe_identifier(event.get("event_id") or event.get("id")),
                "event_type": event_type,
                "timestamp": _safe_summary(event.get("timestamp"), fallback=None),
                "run_id": _safe_identifier(event.get("run_id") or event.get("work_id")),
                "session_id": _safe_identifier(
                    event.get("session_id") or event.get("parent_work_id")
                ),
                "task_id": _safe_identifier(
                    event.get("task_id")
                    or event.get("session_id")
                    or event.get("parent_work_id")
                ),
                "work_id": _safe_identifier(event.get("work_id") or event.get("run_id")),
                "status": status,
                "summary": _safe_summary(message, fallback=""),
                "verification": _delegate_recovery_verification(event_type, status),
                "blockers": _delegate_recovery_blockers(event_type, status, message),
                "next_step": _delegate_recovery_next_step(event_type, status),
                "privacy_class": WORKBENCH_PRIVACY_CLASS,
            }
        )
        if len(entries) >= limit:
            break
    return entries


def _dedupe_recovery_gate_entries(
    entries: Iterable[Dict[str, Any]],
    *,
    limit: int,
) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[tuple[Optional[str], ...]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            _safe_identifier(entry.get("event_id")),
            _safe_label(entry.get("event_type"), fallback=None, limit=LABEL_LIMIT),
            _safe_identifier(entry.get("run_id") or entry.get("work_id")),
            _safe_identifier(entry.get("task_id") or entry.get("session_id")),
            _safe_status(entry.get("status")),
            _safe_summary(entry.get("timestamp"), fallback=None),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
        if len(deduped) >= limit:
            break
    return deduped


def _status_from_delegate_event_type(event_type: str) -> str:
    if event_type == "agent.child.completed":
        return "completed"
    if event_type == "agent.child.failed":
        return "failed"
    if event_type == "agent.child.timeout":
        return "timeout"
    if event_type == "agent.child.interrupted":
        return "interrupted"
    if event_type == "agent.child.spawned":
        return "queued"
    if event_type == "agent.child.running":
        return "running"
    return "unknown"


def _delegate_recovery_verification(
    event_type: str,
    status: Optional[str],
) -> Optional[str]:
    if status == "completed" or event_type == "agent.child.completed":
        return "delegate child completed"
    return None


def _delegate_recovery_blockers(
    event_type: str,
    status: Optional[str],
    message: Any,
) -> list[str]:
    if status in FAILED_STATUSES or event_type in {
        "agent.child.failed",
        "agent.child.timeout",
        "agent.child.interrupted",
    }:
        blocker = _safe_summary(message, fallback=event_type)
        return [blocker] if blocker else []
    return []


def _delegate_recovery_next_step(
    event_type: str,
    status: Optional[str],
) -> Optional[str]:
    if status == "completed" or event_type == "agent.child.completed":
        return "Review delegate child handoff summary."
    if status in {"failed", "error", "timeout"} or event_type in {
        "agent.child.failed",
        "agent.child.timeout",
    }:
        return "Review delegate failure and decide retry, reassignment, or handoff."
    if status == "interrupted" or event_type == "agent.child.interrupted":
        return "Resume or reassign interrupted delegate work."
    if status in ACTIVE_STATUSES or event_type in {
        "agent.child.spawned",
        "agent.child.running",
    }:
        return "Monitor delegate child lifecycle."
    return None


def _active_work_from_events(
    events: Iterable[Dict[str, Any]],
    *,
    limit: int,
) -> list[Dict[str, Any]]:
    latest_by_work: dict[str, Dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = _safe_label(event.get("type"), fallback="", limit=LABEL_LIMIT)
        source = _safe_label(event.get("source"), fallback="", limit=LABEL_LIMIT)
        if not event_type.startswith("agent.") and source != "multi_agent":
            continue
        work_id = _safe_identifier(event.get("run_id")) or _safe_identifier(event.get("id"))
        if not work_id:
            continue
        status = _safe_status(event.get("status")) or "unknown"
        latest_by_work[work_id] = {
            "work_id": work_id,
            "parent_work_id": _safe_identifier(event.get("session_id")),
            "event_type": event_type,
            "role": _safe_label(event.get("tool"), fallback=None, limit=LABEL_LIMIT),
            "status": status,
            "summary": _safe_summary(event.get("message"), fallback="No details"),
            "timestamp": _safe_summary(event.get("timestamp"), fallback=None),
        }

    active_or_failed = [
        item
        for item in latest_by_work.values()
        if _safe_status(item.get("status")) not in TERMINAL_STATUSES
    ]
    return sorted(
        active_or_failed,
        key=lambda item: item.get("timestamp") or "",
        reverse=True,
    )[:limit]


def _memory_summary(memory_diagnostics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(memory_diagnostics, dict):
        return {
            "status": "unavailable",
            "provider_count": 0,
            "providers": [],
            "registered_tools": [],
            "degraded_reason": "memory_diagnostics_unavailable",
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
        }

    providers = []
    registered_tools = []
    for provider in memory_diagnostics.get("providers") or []:
        if not isinstance(provider, dict):
            continue
        tool_names = _safe_list(provider.get("tool_names") or [])
        providers.append(
            {
                "name": _safe_identifier(provider.get("name")),
                "kind": _safe_label(provider.get("kind"), fallback="unknown", limit=LABEL_LIMIT),
                "availability": _safe_status(provider.get("availability")) or "unknown",
                "initialized": provider.get("initialized")
                if isinstance(provider.get("initialized"), bool)
                else None,
                "tool_names": tool_names,
                "last_lifecycle": _safe_last_lifecycle(provider.get("last_lifecycle")),
                "privacy_class": WORKBENCH_PRIVACY_CLASS,
            }
        )
        registered_tools.extend(tool_names)

    degraded_reason = _safe_summary(memory_diagnostics.get("degraded_reason"), fallback=None)
    status = "available"
    if degraded_reason:
        status = "degraded"
    elif any(provider["availability"] == "unavailable" for provider in providers):
        status = "degraded"
    elif not providers:
        status = "unavailable"

    return {
        "status": status,
        "provider_count": len(providers),
        "providers": providers,
        "registered_tools": _dedupe(registered_tools)[:ENTRY_LIMIT],
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _safe_last_lifecycle(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    return {
        "event": _safe_label(value.get("event"), fallback="unknown", limit=LABEL_LIMIT),
        "status": _safe_status(value.get("status")) or "unknown",
        "timestamp": _safe_summary(value.get("timestamp"), fallback=None),
        "error_type": _safe_label(value.get("error_type"), fallback=None, limit=LABEL_LIMIT),
    }


def _workbench_status(
    *,
    active_work: list[Dict[str, Any]],
    checkpoint: Dict[str, Any],
    action_entries: list[Dict[str, Any]],
    queue_entries: list[Dict[str, Any]],
    journal_entries: list[Dict[str, Any]],
    memory: Dict[str, Any],
    degraded_reason: Optional[str],
) -> str:
    if any(_safe_status(item.get("status")) in FAILED_STATUSES for item in active_work):
        return "failed"
    if checkpoint.get("blocked_tasks"):
        return "failed"
    if active_work or checkpoint.get("current_task_id"):
        return "active"
    if degraded_reason:
        return "degraded"
    if (
        action_entries
        or queue_entries
        or journal_entries
        or checkpoint.get("completed_tasks")
        or checkpoint.get("pending_tasks")
        or memory.get("status") == "available"
    ):
        return "active"
    return "empty"


def _status_reason(
    status: str,
    active_work: list[Dict[str, Any]],
    checkpoint: Dict[str, Any],
) -> str:
    if status == "failed":
        return "Blocked or failed multi-agent work needs review"
    if status == "active":
        current = checkpoint.get("current_task_id")
        if current:
            return f"Current task {current}"
        if active_work:
            return f"{len(active_work)} active work items"
        return "Workbench has current safe work summaries"
    if status == "degraded":
        return "Some local workbench sources are missing or unreadable"
    if status == "unavailable":
        return "Workbench unavailable"
    return "No multi-agent memory work recorded"


def _unresolved_queue_count(entries: list[Dict[str, Any]]) -> int:
    return sum(
        1
        for entry in entries
        if _safe_status(entry.get("state")) in {"candidate", "needs_evidence", "accepted"}
    )


def _safe_list(values: Iterable[Any]) -> list[str]:
    safe_values = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in safe_values:
            safe_values.append(safe)
        if len(safe_values) >= ENTRY_LIMIT:
            break
    return safe_values


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _append_unique(values: list[str], value: str, *, limit: int) -> None:
    if value in values or len(values) >= limit:
        return
    values.append(value)


def _join_reasons(reasons: Iterable[Any]) -> Optional[str]:
    safe_reasons = []
    for reason in reasons:
        safe = _safe_label(reason, fallback=None, limit=LABEL_LIMIT)
        if safe and safe not in safe_reasons:
            safe_reasons.append(safe)
    if not safe_reasons:
        return None
    return ";".join(safe_reasons[:8])


def _safe_limit(limit: Any) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return ENTRY_LIMIT
    return max(1, min(value, 50))


def _safe_summary(value: Any, *, fallback: Optional[str]) -> Optional[str]:
    text = _string_or_none(value)
    if not text:
        return fallback
    if _SECRET_RE.search(text) or _ABSOLUTE_PATH_RE.search(text) or _DIFF_RE.search(text):
        return "Redacted"
    if len(text) > SUMMARY_LIMIT:
        return text[: SUMMARY_LIMIT - 3] + "..."
    return text


def _safe_identifier(value: Any) -> Optional[str]:
    text = _safe_summary(value, fallback=None)
    if text is None:
        return None
    if text == "Redacted":
        return text
    cleaned = _SAFE_LABEL_RE.sub("_", text).strip()
    if not cleaned:
        return None
    if len(cleaned) > ID_LIMIT:
        return cleaned[: ID_LIMIT - 3] + "..."
    return cleaned


def _safe_label(value: Any, *, fallback: Optional[str], limit: int) -> Optional[str]:
    text = _safe_summary(value, fallback=fallback)
    if text is None or text == "Redacted":
        return text
    cleaned = _SAFE_LABEL_RE.sub("_", text).strip()
    if not cleaned:
        return fallback
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def _safe_status(value: Any) -> Optional[str]:
    text = _safe_label(value, fallback=None, limit=LABEL_LIMIT)
    return text.lower() if text else None


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
