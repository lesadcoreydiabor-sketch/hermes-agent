"""Privacy-safe working checkpoint helpers for HERMES multi-agent work.

This module builds resumable work summaries from safe task contracts and
action ledger entries. It does not write checkpoint files, read raw logs,
dispatch tools, mutate memory providers, or inspect provider content.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

from hermes_cli.action_ledger import normalize_action_ledger_entry
from utils import atomic_replace


WORKING_CHECKPOINT_SCHEMA_VERSION = 1
WORKING_CHECKPOINT_PRIVACY_CLASS = "redacted_summary"
WORKING_CHECKPOINT_PATH = Path(".hermes") / "working_checkpoint.json"

TASK_LIMIT = 40
DECISION_LIMIT = 20
SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96

COMPLETED_STATUSES = frozenset({"completed", "done", "passed", "success", "succeeded"})
PENDING_STATUSES = frozenset(
    {"pending", "todo", "queued", "running", "started", "in_progress", "in-progress"}
)
BLOCKED_STATUSES = frozenset(
    {"blocked", "failed", "interrupted", "timeout", "cancelled", "canceled", "error"}
)
ACTIVE_STATUSES = frozenset({"running", "started", "in_progress", "in-progress"})

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


def default_working_checkpoint_path(root: str | Path = ".") -> Path:
    """Return the default workspace-local working checkpoint path."""

    return Path(root) / WORKING_CHECKPOINT_PATH


def build_working_checkpoint(
    task_contract: Optional[Dict[str, Any]] = None,
    ledger_entries: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    active_capability: Any = None,
    current_task_id: Any = None,
    source: Any = "generated",
    generated_at: Optional[str] = None,
    degraded_reason: Any = None,
) -> Dict[str, Any]:
    """Build one bounded, redacted working checkpoint object."""

    contract = task_contract if isinstance(task_contract, dict) else {}
    normalized_entries, entry_reasons = _normalize_ledger_entries(ledger_entries or [])
    reasons = _degraded_reasons(degraded_reason)
    reasons.extend(entry_reasons)

    contract_tasks = _extract_task_summaries(contract.get("tasks"))
    completed_tasks = _bounded(
        [task for task in contract_tasks if _status_bucket(task.get("status")) == "completed"]
    )
    pending_tasks = _bounded(
        [task for task in contract_tasks if _status_bucket(task.get("status")) == "pending"]
    )
    blocked_tasks = _bounded(
        [task for task in contract_tasks if _status_bucket(task.get("status")) == "blocked"]
    )

    known_task_ids = {
        task["task_id"]
        for task in completed_tasks + pending_tasks + blocked_tasks
        if task.get("task_id")
    }
    for entry in normalized_entries:
        task_id = entry.get("task_id")
        if not task_id or task_id in known_task_ids:
            continue
        ledger_task = _task_summary_from_ledger(entry)
        bucket = _status_bucket(entry.get("status"))
        if bucket == "completed":
            completed_tasks.append(ledger_task)
        elif bucket == "blocked" or entry.get("blockers"):
            blocked_tasks.append(ledger_task)
        elif bucket == "pending":
            pending_tasks.append(ledger_task)
        known_task_ids.add(task_id)

    completed_tasks = _bounded(_dedupe_tasks(completed_tasks))
    pending_tasks = _bounded(_dedupe_tasks(pending_tasks))
    blocked_tasks = _bounded(_dedupe_tasks(blocked_tasks))

    return {
        "schema_version": WORKING_CHECKPOINT_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "source": _safe_source(source),
        "active_capability": _safe_label(
            active_capability or contract.get("capability"),
            fallback="unknown",
            limit=LABEL_LIMIT,
        ),
        "current_task_id": _resolve_current_task_id(
            current_task_id,
            contract_tasks,
            normalized_entries,
            pending_tasks,
        ),
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "blocked_tasks": blocked_tasks,
        "last_verification": _last_verification(contract, normalized_entries),
        "open_decisions": _bounded(
            _extract_open_decisions(contract),
            limit=DECISION_LIMIT,
        ),
        "next_step": _next_step(contract, normalized_entries, pending_tasks),
        "degraded_reason": _join_degraded_reasons(reasons),
        "privacy_class": WORKING_CHECKPOINT_PRIVACY_CLASS,
    }


def build_working_checkpoint_from_files(
    task_yaml_path: str | Path = Path(".hermes") / "task.yaml",
    ledger_path: str | Path = Path(".hermes") / "action_ledger.jsonl",
    *,
    source: Any = "generated",
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a degraded-safe checkpoint from local task and ledger files."""

    reasons: list[str] = []
    task_contract = _read_task_contract(Path(task_yaml_path), reasons)
    ledger_entries = _read_ledger_entries(Path(ledger_path), reasons)
    return build_working_checkpoint(
        task_contract,
        ledger_entries,
        source=source,
        generated_at=generated_at,
        degraded_reason=reasons,
    )


def write_working_checkpoint_from_files(
    task_yaml_path: str | Path = Path(".hermes") / "task.yaml",
    ledger_path: str | Path = Path(".hermes") / "action_ledger.jsonl",
    checkpoint_path: str | Path = WORKING_CHECKPOINT_PATH,
    *,
    source: Any = "generated",
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Explicitly write a safe working checkpoint generated from local files."""

    checkpoint = build_working_checkpoint_from_files(
        task_yaml_path=task_yaml_path,
        ledger_path=ledger_path,
        source=source,
        generated_at=generated_at,
    )
    _atomic_write_json(Path(checkpoint_path), checkpoint)
    return checkpoint


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        atomic_replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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


def _read_ledger_entries(path: Path, reasons: list[str]) -> list[Dict[str, Any]]:
    if not path.exists():
        reasons.append("ledger_missing")
        return []

    entries: list[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        reasons.append("ledger_read_error")
        return []

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            reasons.append("ledger_parse_error")
            continue
        if not isinstance(entry, dict):
            reasons.append("ledger_entry_invalid")
            continue
        entries.append(entry)
    return entries


def _normalize_ledger_entries(
    entries: Iterable[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], list[str]]:
    normalized = []
    reasons: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            reasons.append("ledger_entry_invalid")
            continue
        try:
            normalized.append(normalize_action_ledger_entry(entry))
        except (TypeError, ValueError):
            reasons.append("ledger_entry_invalid")
    return normalized, reasons


def _extract_task_summaries(tasks: Any) -> list[Dict[str, Optional[str]]]:
    if not isinstance(tasks, list):
        return []
    summaries: list[Dict[str, Optional[str]]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _safe_identifier(task.get("id") or task.get("task_id"))
        if not task_id:
            continue
        summaries.append(
            {
                "task_id": task_id,
                "title": _safe_summary(task.get("title"), fallback="Untitled task"),
                "status": _safe_status(task.get("status")) or "unknown",
            }
        )
        if len(summaries) >= TASK_LIMIT:
            break
    return summaries


def _task_summary_from_ledger(entry: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "task_id": entry.get("task_id"),
        "title": _safe_summary(entry.get("summary"), fallback="Ledger task"),
        "status": _safe_status(entry.get("status")) or "unknown",
    }


def _extract_open_decisions(contract: Dict[str, Any]) -> list[str]:
    values = contract.get("open_decisions") or contract.get("decisions") or []
    if not isinstance(values, list):
        return []
    decisions = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in decisions:
            decisions.append(safe)
    return decisions


def _resolve_current_task_id(
    requested: Any,
    contract_tasks: list[Dict[str, Optional[str]]],
    ledger_entries: list[Dict[str, Any]],
    pending_tasks: list[Dict[str, Optional[str]]],
) -> Optional[str]:
    requested_id = _safe_identifier(requested)
    if requested_id:
        return requested_id

    for task in contract_tasks:
        if _safe_status(task.get("status")) in ACTIVE_STATUSES and task.get("task_id"):
            return task["task_id"]

    for entry in reversed(ledger_entries):
        if _safe_status(entry.get("status")) in ACTIVE_STATUSES and entry.get("task_id"):
            return entry["task_id"]

    for task in pending_tasks:
        if task.get("task_id"):
            return task["task_id"]
    return None


def _last_verification(
    contract: Dict[str, Any],
    ledger_entries: list[Dict[str, Any]],
) -> Optional[str]:
    for entry in reversed(ledger_entries):
        verification = _safe_summary(entry.get("verification"), fallback=None)
        if verification:
            return verification

    progress_report = contract.get("progress_report")
    if isinstance(progress_report, list):
        for report in reversed(progress_report):
            if not isinstance(report, dict):
                continue
            verification = _safe_summary(report.get("verification_result"), fallback=None)
            if verification:
                return verification
    return None


def _next_step(
    contract: Dict[str, Any],
    ledger_entries: list[Dict[str, Any]],
    pending_tasks: list[Dict[str, Optional[str]]],
) -> str:
    progress_report = contract.get("progress_report")
    if isinstance(progress_report, list):
        for report in reversed(progress_report):
            if not isinstance(report, dict):
                continue
            next_step = _safe_summary(report.get("next_step"), fallback=None)
            if next_step:
                return next_step

    for entry in reversed(ledger_entries):
        next_step = _safe_summary(entry.get("next_step"), fallback=None)
        if next_step:
            return next_step

    if pending_tasks:
        task_id = pending_tasks[0].get("task_id") or "the next pending task"
        return f"Continue {task_id}."
    return "No next step recorded."


def _status_bucket(status: Any) -> str:
    safe = _safe_status(status)
    if safe in COMPLETED_STATUSES:
        return "completed"
    if safe in BLOCKED_STATUSES:
        return "blocked"
    if safe in PENDING_STATUSES:
        return "pending"
    return "unknown"


def _dedupe_tasks(tasks: Iterable[Dict[str, Optional[str]]]) -> list[Dict[str, Optional[str]]]:
    seen = set()
    deduped = []
    for task in tasks:
        task_id = task.get("task_id")
        if not task_id or task_id in seen:
            continue
        deduped.append(task)
        seen.add(task_id)
    return deduped


def _bounded(values: Iterable[Any], *, limit: int = TASK_LIMIT) -> list[Any]:
    return list(values)[:limit]


def _degraded_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            safe
            for safe in (_safe_label(item, fallback=None, limit=LABEL_LIMIT) for item in value)
            if safe
        ]
    safe = _safe_label(value, fallback=None, limit=LABEL_LIMIT)
    return [safe] if safe else []


def _join_degraded_reasons(reasons: list[str]) -> Optional[str]:
    unique = []
    for reason in reasons:
        safe = _safe_label(reason, fallback=None, limit=LABEL_LIMIT)
        if safe and safe not in unique:
            unique.append(safe)
    if not unique:
        return None
    return ";".join(unique[:8])


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


def _safe_source(value: Any) -> str:
    source = _safe_status(value)
    if source in {"generated", "user_reviewed"}:
        return source
    return "generated"


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
