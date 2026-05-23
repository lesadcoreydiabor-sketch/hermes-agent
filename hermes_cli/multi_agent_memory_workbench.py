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
    REVIEW_ACTION_EFFECTS,
    REVIEW_ACTION_TARGET_TYPES,
    build_failure_review_export_handoff,
    build_failure_review_export_preview,
    build_learning_review_request,
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
    action_source = _read_jsonl_source(
        workspace / ACTION_LEDGER_PATH,
        normalize_action_ledger_entry,
        missing_reason="action_ledger_missing",
        limit=safe_limit,
    )
    action_entries = action_source["entries"]
    action_degraded = action_source["degraded_reason"]
    queue_source = _read_jsonl_source(
        workspace / LONG_TERM_QUEUE_PATH,
        normalize_long_term_queue_entry,
        missing_reason="long_term_queue_missing",
        limit=safe_limit,
    )
    queue_entries = queue_source["entries"]
    queue_degraded = queue_source["degraded_reason"]
    journal_source = _read_jsonl_source(
        workspace / SKILLS_JOURNAL_PATH,
        normalize_skills_journal_entry,
        missing_reason="skills_journal_missing",
        limit=safe_limit,
    )
    journal_entries = journal_source["entries"]
    journal_degraded = journal_source["degraded_reason"]
    active_work = _active_work_from_events(recent_events, limit=safe_limit)
    recovery_entries = _dedupe_recovery_gate_entries(
        [
            *_delegate_recovery_entries_from_action_ledger(action_entries),
            *_delegate_recovery_entries_from_events(recent_events, limit=safe_limit),
        ],
        limit=safe_limit,
    )
    memory = _memory_summary(memory_diagnostics)
    runtime_persistence = _runtime_persistence_summary(workspace)
    vault_signals = _readonly_vault_signals(generated_at=generated_at)
    agent_assignments = _agent_assignment_summary(workspace, limit=safe_limit)
    source_quality = _source_quality_summary(
        checkpoint=checkpoint,
        action_source=action_source,
        action_entries=action_entries,
        queue_source=queue_source,
        queue_entries=queue_entries,
        journal_source=journal_source,
        journal_entries=journal_entries,
        memory=memory,
        limit=safe_limit,
    )
    learning_review = _learning_review_request_summary(
        queue_entries,
        degraded_reason=queue_degraded,
        limit=safe_limit,
    )
    failure_review_export = _failure_review_export_preview_summary(
        queue_entries,
        degraded_reason=queue_degraded,
        generated_at=generated_at,
        limit=safe_limit,
    )
    failure_review_export_handoff = _failure_review_export_handoff_summary(
        failure_review_export,
        degraded_reason=queue_degraded,
        generated_at=generated_at,
    )
    failure_review_export_application_gate = (
        _failure_review_export_application_gate_summary(
            failure_review_export_handoff,
            degraded_reason=queue_degraded,
            generated_at=generated_at,
        )
    )

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
        "source_quality": source_quality,
        "runtime_persistence": runtime_persistence,
        "vault_signals": vault_signals,
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
        "learning_review": learning_review,
        "failure_review_export": failure_review_export,
        "failure_review_export_handoff": failure_review_export_handoff,
        "failure_review_export_application_gate": (
            failure_review_export_application_gate
        ),
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
    failure_review_export = _failure_review_export_preview_summary(
        [],
        degraded_reason=reason,
        generated_at=generated_at,
        limit=ENTRY_LIMIT,
    )
    failure_review_export_handoff = _failure_review_export_handoff_summary(
        failure_review_export,
        degraded_reason=reason,
        generated_at=generated_at,
    )
    failure_review_export_application_gate = (
        _failure_review_export_application_gate_summary(
            failure_review_export_handoff,
            degraded_reason=reason,
            generated_at=generated_at,
        )
    )
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
        "source_quality": _unavailable_source_quality(reason),
        "vault_signals": _unavailable_vault_signals(
            reason,
            generated_at=generated_at,
        ),
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
        "learning_review": _learning_review_request_summary(
            [],
            degraded_reason=reason,
            limit=ENTRY_LIMIT,
        ),
        "failure_review_export": failure_review_export,
        "failure_review_export_handoff": failure_review_export_handoff,
        "failure_review_export_application_gate": (
            failure_review_export_application_gate
        ),
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
    source = _read_jsonl_source(
        path,
        normalizer,
        missing_reason=missing_reason,
        limit=limit,
    )
    return source["entries"], source["degraded_reason"]


def _read_jsonl_source(
    path: Path,
    normalizer: Callable[[Dict[str, Any]], Dict[str, Any]],
    *,
    missing_reason: str,
    limit: int,
) -> Dict[str, Any]:
    if not path.exists():
        return {
            "entries": [],
            "entry_count": 0,
            "error_count": 0,
            "bounded": False,
            "missing": True,
            "degraded_reason": missing_reason,
        }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "entries": [],
            "entry_count": 0,
            "error_count": 1,
            "bounded": False,
            "missing": False,
            "degraded_reason": f"{path.stem}_read_error",
        }

    entries = []
    reasons = []
    error_count = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            reasons.append(f"{path.stem}_parse_error")
            error_count += 1
            continue
        if not isinstance(payload, dict):
            reasons.append(f"{path.stem}_entry_invalid")
            error_count += 1
            continue
        try:
            entries.append(normalizer(payload))
        except (TypeError, ValueError):
            reasons.append(f"{path.stem}_entry_invalid")
            error_count += 1

    safe_limit = _safe_limit(limit)
    return {
        "entries": entries[-safe_limit:],
        "entry_count": _safe_count(len(entries)),
        "error_count": _safe_count(error_count),
        "bounded": len(entries) > safe_limit,
        "missing": False,
        "degraded_reason": _join_reasons(reasons),
    }


def _source_quality_summary(
    *,
    checkpoint: Dict[str, Any],
    action_source: Dict[str, Any],
    action_entries: list[Dict[str, Any]],
    queue_source: Dict[str, Any],
    queue_entries: list[Dict[str, Any]],
    journal_source: Dict[str, Any],
    journal_entries: list[Dict[str, Any]],
    memory: Dict[str, Any],
    limit: int,
) -> Dict[str, Any]:
    action_reasons = _dedupe(
        [
            *_ledger_degraded_reasons(checkpoint.get("degraded_reason")),
            *_split_degraded_reasons(action_source.get("degraded_reason")),
        ]
    )
    if action_source.get("missing"):
        action_reasons = _dedupe(["ledger_missing", "action_ledger_missing", *action_reasons])

    sources = [
        {
            "source_id": "hermes.action_ledger",
            "family": "action_ledger",
            "status": _jsonl_source_status(action_source),
            "freshness": _source_freshness(_jsonl_source_status(action_source)),
            "affected_consumers": [
                "checkpoint_dependency",
                "action_ledger_surface",
            ],
            "degraded_reasons": action_reasons,
            "source_refs": [".hermes/action_ledger.jsonl"],
            "counts": _action_ledger_source_counts(
                action_source,
                action_entries,
                limit=limit,
            ),
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
            "safe_note": (
                "Relative source metadata only; entry bodies are not exposed."
            ),
        },
        {
            "source_id": "hermes.long_term_queue",
            "family": "long_term_queue",
            "status": _jsonl_source_status(queue_source),
            "freshness": _source_freshness(_jsonl_source_status(queue_source)),
            "affected_consumers": [
                "memory_review",
                "failure_review_export",
            ],
            "degraded_reasons": _split_degraded_reasons(
                queue_source.get("degraded_reason")
            ),
            "source_refs": [".hermes/long_term_queue.jsonl"],
            "counts": _long_term_queue_source_counts(queue_source, queue_entries),
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
            "safe_note": (
                "Relative source metadata only; entry bodies are not exposed."
            ),
        },
        {
            "source_id": "hermes.skills_journal",
            "family": "skills_journal",
            "status": _jsonl_source_status(journal_source),
            "freshness": _source_freshness(_jsonl_source_status(journal_source)),
            "affected_consumers": [
                "skills_journal_surface",
                "accepted_learnings",
            ],
            "degraded_reasons": _split_degraded_reasons(
                journal_source.get("degraded_reason")
            ),
            "source_refs": [".hermes/skills_journal.jsonl"],
            "counts": _skills_journal_source_counts(journal_source, journal_entries),
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
            "safe_note": (
                "Relative source metadata only; entry bodies are not exposed."
            ),
        },
        _memory_diagnostics_source_quality(memory),
    ]
    return {
        "contract_version": 1,
        "live_sources": ["/api/run-inspector/memory-workbench"],
        "fixture_sources": [],
        "degraded_reasons": _dedupe(
            reason
            for source in sources
            for reason in source.get("degraded_reasons", [])
        ),
        "sources": sources,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _unavailable_source_quality(reason: Any) -> Dict[str, Any]:
    safe_reasons = _split_degraded_reasons(reason)
    sources = [
        _unavailable_source_quality_source(
            "hermes.action_ledger",
            "action_ledger",
            ["checkpoint_dependency", "action_ledger_surface"],
            [".hermes/action_ledger.jsonl"],
            {
                "entry_count": 0,
                "recovery_gate_count": 0,
                "blocked_count": 0,
                "error_count": 1 if safe_reasons else 0,
            },
            safe_reasons,
        ),
        _unavailable_source_quality_source(
            "hermes.long_term_queue",
            "long_term_queue",
            ["memory_review", "failure_review_export"],
            [".hermes/long_term_queue.jsonl"],
            {
                "entry_count": 0,
                "unresolved_count": 0,
                "candidate_count": 0,
                "accepted_count": 0,
                "error_count": 1 if safe_reasons else 0,
            },
            safe_reasons,
        ),
        _unavailable_source_quality_source(
            "hermes.skills_journal",
            "skills_journal",
            ["skills_journal_surface", "accepted_learnings"],
            [".hermes/skills_journal.jsonl"],
            {
                "entry_count": 0,
                "accepted_count": 0,
                "stale_count": 0,
                "blocked_count": 0,
                "error_count": 1 if safe_reasons else 0,
            },
            safe_reasons,
        ),
        _unavailable_source_quality_source(
            "hermes.memory_diagnostics",
            "memory_diagnostics",
            ["memory_diagnostics_surface"],
            ["runtime.memory_diagnostics"],
            {
                "provider_count": 0,
                "registered_tool_count": 0,
                "available_provider_count": 0,
                "unavailable_provider_count": 0,
            },
            safe_reasons,
        ),
    ]
    return {
        "contract_version": 1,
        "live_sources": ["/api/run-inspector/memory-workbench"],
        "fixture_sources": [],
        "degraded_reasons": safe_reasons,
        "sources": sources,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _unavailable_source_quality_source(
    source_id: str,
    family: str,
    affected_consumers: list[str],
    source_refs: list[str],
    counts: Dict[str, int],
    degraded_reasons: list[str],
) -> Dict[str, Any]:
    return {
        "source_id": source_id,
        "family": family,
        "status": "unavailable",
        "freshness": "unknown",
        "affected_consumers": affected_consumers,
        "degraded_reasons": degraded_reasons,
        "source_refs": source_refs,
        "counts": counts,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
        "safe_note": "Relative source metadata only; entry bodies are not exposed.",
    }


def _jsonl_source_status(source: Dict[str, Any]) -> str:
    if source.get("missing"):
        return "missing"
    if source.get("degraded_reason"):
        return "degraded"
    if source.get("bounded"):
        return "bounded"
    return "available"


def _source_freshness(status: str) -> str:
    if status == "missing":
        return "missing"
    if status == "unavailable":
        return "unknown"
    return status


def _action_ledger_source_counts(
    source: Dict[str, Any],
    entries: list[Dict[str, Any]],
    *,
    limit: int,
) -> Dict[str, int]:
    gate_summary = _delegate_recovery_gate_summary(
        _delegate_recovery_entries_from_action_ledger(entries),
        limit=limit,
    )
    recovery_gate_count = (
        _safe_count(gate_summary.get("completed_count"))
        + _safe_count(gate_summary.get("blocked_count"))
        + _safe_count(gate_summary.get("monitoring_count"))
    )
    return {
        "entry_count": _safe_count(source.get("entry_count")),
        "recovery_gate_count": recovery_gate_count,
        "blocked_count": _safe_count(gate_summary.get("blocked_count")),
        "error_count": _safe_count(source.get("error_count")),
    }


def _long_term_queue_source_counts(
    source: Dict[str, Any],
    entries: list[Dict[str, Any]],
) -> Dict[str, int]:
    return {
        "entry_count": _safe_count(source.get("entry_count")),
        "unresolved_count": _unresolved_queue_count(entries),
        "candidate_count": _count_entries_by_status(entries, "state", {"candidate"}),
        "accepted_count": _count_entries_by_status(entries, "state", {"accepted"}),
        "error_count": _safe_count(source.get("error_count")),
    }


def _skills_journal_source_counts(
    source: Dict[str, Any],
    entries: list[Dict[str, Any]],
) -> Dict[str, int]:
    return {
        "entry_count": _safe_count(source.get("entry_count")),
        "accepted_count": _safe_count(len(entries)),
        "stale_count": 0,
        "blocked_count": 0,
        "error_count": _safe_count(source.get("error_count")),
    }


def _memory_diagnostics_source_quality(memory: Dict[str, Any]) -> Dict[str, Any]:
    status = _safe_status(memory.get("status")) or "unavailable"
    if status not in {"available", "degraded", "unavailable"}:
        status = "unavailable"
    providers = memory.get("providers") if isinstance(memory.get("providers"), list) else []
    registered_tools = (
        memory.get("registered_tools")
        if isinstance(memory.get("registered_tools"), list)
        else []
    )
    degraded_reasons = _split_degraded_reasons(memory.get("degraded_reason"))
    return {
        "source_id": "hermes.memory_diagnostics",
        "family": "memory_diagnostics",
        "status": status,
        "freshness": _source_freshness(status),
        "affected_consumers": ["memory_diagnostics_surface"],
        "degraded_reasons": degraded_reasons,
        "source_refs": ["runtime.memory_diagnostics"],
        "counts": {
            "provider_count": _safe_count(memory.get("provider_count")),
            "registered_tool_count": _safe_count(len(registered_tools)),
            "available_provider_count": _count_providers_by_availability(
                providers,
                "available",
            ),
            "unavailable_provider_count": _count_providers_by_availability(
                providers,
                "unavailable",
            ),
        },
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
        "safe_note": "Runtime memory diagnostics metadata only; provider secrets are not exposed.",
    }


def _count_entries_by_status(
    entries: Iterable[Dict[str, Any]],
    key: str,
    statuses: set[str],
) -> int:
    return sum(
        1
        for entry in entries
        if _safe_status(entry.get(key)) in statuses
    )


def _count_providers_by_availability(
    providers: Iterable[Any],
    availability: str,
) -> int:
    return sum(
        1
        for provider in providers
        if isinstance(provider, dict)
        and _safe_status(provider.get("availability")) == availability
    )


def _ledger_degraded_reasons(reason: Any) -> list[str]:
    return [
        item
        for item in _split_degraded_reasons(reason)
        if item in {"ledger_missing", "ledger_read_error", "ledger_parse_error", "ledger_entry_invalid"}
    ]


def _split_degraded_reasons(reason: Any) -> list[str]:
    if reason is None:
        return []
    values = reason if isinstance(reason, list) else str(reason).split(";")
    safe_values = []
    for value in values:
        safe = _safe_label(value, fallback=None, limit=LABEL_LIMIT)
        if safe and safe not in safe_values:
            safe_values.append(safe)
    return safe_values


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


def _readonly_vault_signals(*, generated_at: Optional[str]) -> Dict[str, Any]:
    observed_at = generated_at or _utc_now_iso()
    provider_id = _read_active_provider_id()

    if provider_id:
        provider_name = _provider_display_name(provider_id)
        vault = _vault_signal(
            alias=f"model-provider:{provider_id}",
            provider=provider_name,
            status="available",
            availability="available",
            access_status="allowed",
            reason_category="none",
            freshness="fresh",
            source_quality_status="available",
            degraded_reasons=[],
            safe_note="Active model provider metadata is available; secret material is omitted.",
            observed_at=observed_at,
        )
        event = _vault_metadata_event(
            event_id="vault-metadata-active-provider",
            event_type="vault.metadata.available",
            status="completed",
            summary="Active model provider metadata is available; secret material is omitted.",
            observed_at=observed_at,
            evidence_quality=vault["source_quality"],
        )
        return _vault_signals_payload([vault], [event], observed_at=observed_at)

    vault = _vault_signal(
        alias="model-provider:active",
        provider="model-provider",
        status="not_configured",
        availability="not_configured",
        access_status="not_requested",
        reason_category="not_configured",
        freshness="missing",
        source_quality_status="missing",
        degraded_reasons=["vault_metadata_not_configured"],
        safe_note="No active model provider metadata is configured.",
        observed_at=observed_at,
    )
    event = _vault_metadata_event(
        event_id="vault-metadata-not-configured",
        event_type="vault.metadata.not_configured",
        status="blocked",
        summary="No active model provider metadata is configured.",
        observed_at=observed_at,
        evidence_quality=vault["source_quality"],
        blockers=["vault_metadata_not_configured"],
        next_step="Configure a model provider before expecting live vault metadata.",
    )
    return _vault_signals_payload([vault], [event], observed_at=observed_at)


def _unavailable_vault_signals(
    reason: Any,
    *,
    generated_at: Optional[str],
) -> Dict[str, Any]:
    observed_at = generated_at or _utc_now_iso()
    safe_reason = _safe_label(
        reason,
        fallback="vault_metadata_provider_unavailable",
        limit=LABEL_LIMIT,
    )
    vault = _vault_signal(
        alias="model-provider:active",
        provider="model-provider",
        status="unavailable",
        availability="unavailable",
        access_status="unavailable",
        reason_category="provider_unavailable",
        freshness="unknown",
        source_quality_status="unavailable",
        degraded_reasons=[safe_reason],
        safe_note="Vault metadata source is unavailable; secret material is omitted.",
        observed_at=observed_at,
    )
    event = _vault_metadata_event(
        event_id="vault-metadata-unavailable",
        event_type="vault.metadata.unavailable",
        status="blocked",
        summary="Vault metadata source is unavailable; secret material is omitted.",
        observed_at=observed_at,
        evidence_quality=vault["source_quality"],
        blockers=[safe_reason],
    )
    return _vault_signals_payload([vault], [event], observed_at=observed_at)


def _read_active_provider_id() -> Optional[str]:
    try:
        from hermes_cli.auth import get_active_provider

        provider_id = get_active_provider()
    except Exception:
        provider_id = None
    if not provider_id:
        provider_id = _read_configured_model_provider()
    return _safe_label(provider_id, fallback=None, limit=LABEL_LIMIT)


def _read_configured_model_provider() -> Optional[str]:
    try:
        from hermes_cli.config import read_raw_config

        config = read_raw_config()
    except Exception:
        return None
    model_config = config.get("model") if isinstance(config, dict) else None
    if not isinstance(model_config, dict):
        return None
    return _safe_label(model_config.get("provider"), fallback=None, limit=LABEL_LIMIT)


def _provider_display_name(provider_id: str) -> str:
    try:
        from hermes_cli.auth import get_auth_provider_display_name

        display_name = get_auth_provider_display_name(provider_id)
    except Exception:
        display_name = provider_id
    return _safe_label(display_name, fallback=provider_id, limit=LABEL_LIMIT) or provider_id


def _vault_signal(
    *,
    alias: str,
    provider: str,
    status: str,
    availability: str,
    access_status: str,
    reason_category: str,
    freshness: str,
    source_quality_status: str,
    degraded_reasons: Iterable[Any],
    safe_note: str,
    observed_at: str,
) -> Dict[str, Any]:
    safe_degraded_reasons = _safe_list(degraded_reasons)
    return {
        "alias": _safe_label(alias, fallback="model-provider:active", limit=LABEL_LIMIT),
        "provider": _safe_label(provider, fallback="model-provider", limit=LABEL_LIMIT),
        "scope": {
            "category": "model_provider",
            "permissions": ["metadata:read"],
        },
        "status": _safe_status(status) or "unknown",
        "availability": _safe_status(availability) or "unknown",
        "access_status": _safe_status(access_status) or "unknown",
        "reason_category": _safe_status(reason_category) or "unknown",
        "freshness": _safe_status(freshness) or "unknown",
        "sessions": [],
        "last_access_at": None,
        "last_observed_at": observed_at,
        "related_candidate_ids": [],
        "safe_note": _safe_summary(safe_note, fallback=None),
        "source_quality": {
            "status": _safe_status(source_quality_status) or "unknown",
            "freshness": _safe_status(freshness) or "unknown",
            "bounded": False,
            "limit": None,
            "observed_at": observed_at,
            "source_refs": ["auth.active_provider", "config.model.provider"],
            "degraded_reasons": safe_degraded_reasons,
            "safe_note": _safe_summary(safe_note, fallback=None),
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
        },
        "secret_material_present": False,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _vault_metadata_event(
    *,
    event_id: str,
    event_type: str,
    status: str,
    summary: str,
    observed_at: str,
    evidence_quality: Dict[str, Any],
    blockers: Optional[Iterable[Any]] = None,
    next_step: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "event_id": _safe_identifier(event_id) or "vault-metadata-event",
        "sequence": 1,
        "type": _safe_label(event_type, fallback="vault.metadata.unknown", limit=LABEL_LIMIT),
        "source": "adapter",
        "timestamp": observed_at,
        "run_id": "run-inspector-vault-metadata",
        "session_id": None,
        "task_id": None,
        "agent_id": None,
        "parent_agent_id": None,
        "tool": "model_provider",
        "status": _safe_status(status) or "unknown",
        "summary": _safe_summary(summary, fallback="Vault metadata event") or "Vault metadata event",
        "verification": "Metadata-only signal; secret material omitted.",
        "evidence_quality": evidence_quality,
        "blockers": _safe_list(blockers or []),
        "next_step": _safe_summary(next_step, fallback=None),
        "side_effect_class": "read_only",
        "redaction": {
            "state": "redacted",
            "reason": "secret material never enters Run Inspector vault signals",
        },
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _vault_signals_payload(
    vaults: list[Dict[str, Any]],
    access_events: list[Dict[str, Any]],
    *,
    observed_at: str,
) -> Dict[str, Any]:
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "generated_at": observed_at,
        "summary": _vault_signals_summary(vaults),
        "vaults": vaults,
        "access_events": access_events,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _vault_signals_summary(vaults: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "requested_count": 0,
        "granted_count": 0,
        "denied_count": 0,
        "redacted_count": 0,
        "available_count": 0,
        "unavailable_count": 0,
        "not_configured_count": 0,
        "stale_count": 0,
    }
    for vault in vaults:
        status = _safe_status(vault.get("status")) or "unknown"
        availability = _safe_status(vault.get("availability")) or status
        if status in {"requested", "granted", "denied"}:
            counts[f"{status}_count"] += 1
        if availability in {"available", "unavailable", "not_configured", "stale"}:
            counts[f"{availability}_count"] += 1
        if status == "redacted" or availability == "redacted":
            counts["redacted_count"] += 1
    return counts


def _learning_review_request_summary(
    queue_entries: Iterable[Dict[str, Any]],
    *,
    degraded_reason: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    requests: list[Dict[str, Any]] = []
    ready_count = 0
    blocked_count = 0

    for entry in queue_entries:
        if not isinstance(entry, dict):
            continue
        review_request = _learning_review_request_from_queue_entry(entry)
        if not review_request:
            continue
        if review_request.get("state") == "pending_review":
            ready_count += 1
        else:
            blocked_count += 1
        requests.append(review_request)
        if len(requests) >= limit:
            break

    status = "empty"
    if blocked_count:
        status = "blocked"
    elif ready_count:
        status = "ready"
    elif degraded_reason:
        status = "unavailable"

    return {
        "status": status,
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "requests": requests,
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _failure_review_export_preview_summary(
    queue_entries: Iterable[Dict[str, Any]],
    *,
    degraded_reason: Optional[str],
    generated_at: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    preview = build_failure_review_export_preview(
        queue_entries,
        preview_id="failure-review-export-preview",
        timestamp=generated_at,
        limit=limit,
        privacy_class=WORKBENCH_PRIVACY_CLASS,
    )
    entry_count = preview.get("entry_count")
    if degraded_reason and entry_count == 0:
        status = "unavailable"
    elif entry_count:
        status = "ready"
    else:
        status = "empty"
    return {
        **preview,
        "status": status,
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _failure_review_export_handoff_summary(
    preview: Dict[str, Any],
    *,
    degraded_reason: Optional[str],
    generated_at: Optional[str],
) -> Dict[str, Any]:
    handoff = build_failure_review_export_handoff(
        preview,
        handoff_id="failure-review-export-handoff",
        timestamp=generated_at,
        privacy_class=WORKBENCH_PRIVACY_CLASS,
    )
    entry_count = handoff.get("entry_count")
    if degraded_reason and entry_count == 0:
        status = "unavailable"
    elif entry_count:
        status = "ready"
    else:
        status = "empty"
    return {
        **handoff,
        "status": status,
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _failure_review_export_application_gate_summary(
    handoff: Dict[str, Any],
    *,
    degraded_reason: Optional[str],
    generated_at: Optional[str],
) -> Dict[str, Any]:
    entry_count = _safe_count(handoff.get("entry_count"))
    if degraded_reason and entry_count == 0:
        status = "unavailable"
        state = "unavailable"
    elif entry_count:
        status = "waiting_review"
        state = "waiting_review"
    else:
        status = "empty"
        state = "empty"
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "gate_id": "failure-review-export-application-gate",
        "timestamp": generated_at or _utc_now_iso(),
        "action": "apply_reviewed_failure_review_export",
        "state": state,
        "status": status,
        "review_required": entry_count > 0,
        "export_allowed": False,
        "decision": None,
        "handoff_id": _safe_identifier(handoff.get("handoff_id")),
        "preview_id": _safe_identifier(handoff.get("preview_id")),
        "output_kind": _safe_label(
            handoff.get("output_kind"),
            fallback="failure_review_summary",
            limit=LABEL_LIMIT,
        ),
        "target_ref": _safe_summary(handoff.get("target_ref"), fallback=None),
        "entry_count": entry_count,
        "required_decision_fields": _safe_list(
            handoff.get("required_decision_fields")
            if isinstance(handoff.get("required_decision_fields"), list)
            else []
        ),
        "allowed_decisions": _safe_list(
            handoff.get("allowed_decisions")
            if isinstance(handoff.get("allowed_decisions"), list)
            else []
        ),
        "requested_effect": "reviewed_export_plan_required",
        "blocked_effects": _safe_list(
            handoff.get("blocked_effects")
            if isinstance(handoff.get("blocked_effects"), list)
            else []
        ),
        "degraded_reason": degraded_reason,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _learning_review_request_from_queue_entry(
    entry: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    state = _safe_status(entry.get("state")) or "candidate"
    if state in {"accepted", "applied", "rejected", "superseded"}:
        return None

    action = _learning_review_action_for_queue_entry(entry)
    if not action:
        return None

    source_queue_id = _safe_identifier(entry.get("entry_id"))
    source_candidate_id = _safe_identifier(entry.get("source_event_id"))
    target_type = REVIEW_ACTION_TARGET_TYPES[action]
    target_ref = _safe_summary(entry.get("target_ref"), fallback=None)
    evidence = entry.get("evidence") if isinstance(entry.get("evidence"), list) else []
    proposed_change = _safe_summary(entry.get("proposed_change"), fallback=None)
    verification = _review_verification_from_queue_entry(entry)
    rollback_note = _review_rollback_note_from_queue_entry(entry)
    missing = _learning_review_missing_requirements(
        action,
        source_queue_id=source_queue_id,
        source_candidate_id=source_candidate_id,
        target_ref=target_ref,
        evidence=evidence,
        proposed_change=proposed_change,
        verification=verification,
        rollback_note=rollback_note,
    )

    if missing:
        return {
            "schema_version": WORKBENCH_SCHEMA_VERSION,
            "request_id": _learning_review_request_id(
                source_queue_id,
                source_candidate_id,
            ),
            "action": action,
            "state": "needs_review_evidence",
            "requires_review": True,
            "source_queue_id": source_queue_id,
            "source_candidate_id": source_candidate_id,
            "target_type": target_type,
            "target_ref": target_ref,
            "title": _safe_summary(
                entry.get("title"),
                fallback="Untitled learning candidate",
            ),
            "missing_requirements": missing,
            "requested_effect": REVIEW_ACTION_EFFECTS[action],
            "blocked_effects": [
                "edit_skill_files",
                "write_memory_provider_data",
                "mutate_config",
                "mutate_task_yaml",
                "dispatch_tools_without_review",
            ],
            "privacy_class": WORKBENCH_PRIVACY_CLASS,
        }

    try:
        return build_learning_review_request(
            action,
            request_id=_learning_review_request_id(
                source_queue_id,
                source_candidate_id,
            ),
            timestamp=entry.get("timestamp"),
            source_queue_id=source_queue_id,
            source_candidate_id=source_candidate_id,
            target_type=target_type,
            target_ref=target_ref,
            proposed_change=proposed_change,
            evidence=evidence,
            verification=verification,
            rollback_note=rollback_note,
        )
    except ValueError:
        return None


def _learning_review_action_for_queue_entry(entry: Dict[str, Any]) -> Optional[str]:
    target_type = _safe_status(entry.get("target_type"))
    category = _safe_status(entry.get("category"))
    if target_type == "skill_update" or category == "skill_improvement":
        return "promote_queue_to_skills_journal"
    if target_type == "regression_test" or category == "missing_test":
        return "mark_badcase_covered"
    if target_type == "documentation_update" or category in {
        "recurring_failure",
        "recovery_pattern",
        "documentation_gap",
    }:
        return "export_failure_review_summary"
    return None


def _learning_review_missing_requirements(
    action: str,
    *,
    source_queue_id: Optional[str],
    source_candidate_id: Optional[str],
    target_ref: Optional[str],
    evidence: Iterable[Any],
    proposed_change: Optional[str],
    verification: Optional[str],
    rollback_note: Optional[str],
) -> list[str]:
    missing: list[str] = []
    if not source_queue_id and not source_candidate_id:
        missing.append("source_queue_id_or_candidate_id")
    if not target_ref:
        missing.append("target_ref")
    if not list(evidence):
        missing.append("evidence")
    if action in {
        "promote_queue_to_skills_journal",
        "export_failure_review_summary",
    } and not proposed_change:
        missing.append("proposed_change")
    if action in {
        "promote_queue_to_skills_journal",
        "mark_badcase_covered",
    } and not verification:
        missing.append("verification")
    if action == "promote_queue_to_skills_journal" and not rollback_note:
        missing.append("rollback_note")
    return missing


def _review_verification_from_queue_entry(entry: Dict[str, Any]) -> Optional[str]:
    for item in entry.get("acceptance_criteria") or []:
        safe = _safe_summary(item, fallback=None)
        if not safe:
            continue
        prefix = "Verification command covered: "
        if safe.startswith(prefix):
            return safe[len(prefix) :]
    return _safe_summary(entry.get("verification"), fallback=None)


def _review_rollback_note_from_queue_entry(entry: Dict[str, Any]) -> Optional[str]:
    for item in entry.get("acceptance_criteria") or []:
        safe = _safe_summary(item, fallback=None)
        if not safe:
            continue
        prefix = "Rollback note: "
        if safe.startswith(prefix):
            return safe[len(prefix) :]
    return _safe_summary(entry.get("rollback_note"), fallback=None)


def _learning_review_request_id(
    source_queue_id: Optional[str],
    source_candidate_id: Optional[str],
) -> str:
    return f"review-{source_queue_id or source_candidate_id or 'unknown'}"


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
    source_counts: dict[str, int] = {}
    event_type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    latest_event_type: Optional[str] = None
    latest_status: Optional[str] = None
    latest_timestamp: Optional[str] = None
    latest_source: Optional[str] = None

    for entry in _latest_delegate_recovery_entries(entries):
        if not isinstance(entry, dict):
            continue
        event_type = _safe_label(entry.get("event_type"), fallback="", limit=LABEL_LIMIT)
        if not event_type.startswith("agent.child."):
            continue
        source = _safe_label(
            entry.get("source"),
            fallback="unknown",
            limit=LABEL_LIMIT,
        ) or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1

        status = _safe_status(entry.get("status")) or "unknown"
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        timestamp = _safe_summary(entry.get("timestamp"), fallback=None)
        if _is_latest_recovery_marker(timestamp, latest_timestamp):
            latest_event_type = event_type
            latest_status = status
            latest_timestamp = timestamp
            latest_source = source
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
        "source_counts": source_counts,
        "event_type_counts": event_type_counts,
        "status_counts": status_counts,
        "latest_event_type": latest_event_type,
        "latest_status": latest_status,
        "latest_timestamp": latest_timestamp,
        "latest_source": latest_source,
        "degraded_reason": None,
        "privacy_class": WORKBENCH_PRIVACY_CLASS,
    }


def _latest_delegate_recovery_entries(
    entries: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    latest_by_work: dict[str, Dict[str, Any]] = {}
    order: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            _safe_identifier(entry.get("agent_id"))
            or _safe_identifier(entry.get("run_id"))
            or _safe_identifier(entry.get("work_id"))
            or _safe_identifier(entry.get("task_id"))
            or _safe_identifier(entry.get("event_id"))
        )
        if not key:
            continue
        if key not in latest_by_work:
            order.append(key)
        latest_by_work[key] = entry
    return [latest_by_work[key] for key in order]


def _is_latest_recovery_marker(
    timestamp: Optional[str],
    current_latest: Optional[str],
) -> bool:
    if not current_latest:
        return True
    if not timestamp:
        return False
    return timestamp >= current_latest


def _delegate_recovery_entries_from_action_ledger(
    entries: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    return [
        {**entry, "source": "action_ledger"}
        for entry in entries
        if isinstance(entry, dict)
    ]


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
                "source": "event_stream",
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


def _safe_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, 10_000))


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
