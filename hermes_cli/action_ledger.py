"""Local, privacy-safe action ledger helpers for HERMES multi-agent work.

This module only builds and explicitly appends ledger entries. It does not
wire runtime event emitters, dispatch tools, mutate memory providers, or edit
task contracts automatically.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from utils import atomic_replace


ACTION_LEDGER_SCHEMA_VERSION = 1
ACTION_LEDGER_PRIVACY_CLASS = "redacted_summary"
ACTION_LEDGER_PATH = Path(".hermes") / "action_ledger.jsonl"

SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96
BLOCKER_LIMIT = 12

ALLOWED_PRIVACY_CLASSES = frozenset(
    {"safe", "redacted_summary", "local_only", "omitted"}
)

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


def default_action_ledger_path(root: str | Path = ".") -> Path:
    """Return the default workspace-local action ledger path."""

    return Path(root) / ACTION_LEDGER_PATH


def build_action_ledger_entry(
    event_type: Any,
    *,
    event_id: Any = None,
    timestamp: Optional[str] = None,
    run_id: Any = None,
    session_id: Any = None,
    task_id: Any = None,
    work_id: Any = None,
    agent_id: Any = None,
    parent_agent_id: Any = None,
    status: Any = None,
    summary: Any = None,
    verification: Any = None,
    blockers: Optional[Iterable[Any]] = None,
    next_step: Any = None,
    privacy_class: Any = ACTION_LEDGER_PRIVACY_CLASS,
) -> Dict[str, Any]:
    """Build one normalized, redacted action ledger entry."""

    safe_event_type = _safe_label(event_type, fallback=None, limit=LABEL_LIMIT)
    if not safe_event_type:
        raise ValueError("event_type is required")

    return {
        "schema_version": ACTION_LEDGER_SCHEMA_VERSION,
        "event_id": _safe_identifier(event_id) or _new_event_id(),
        "event_type": safe_event_type,
        "timestamp": timestamp or _utc_now_iso(),
        "run_id": _safe_identifier(run_id),
        "session_id": _safe_identifier(session_id),
        "task_id": _safe_identifier(task_id),
        "work_id": _safe_identifier(work_id),
        "agent_id": _safe_identifier(agent_id),
        "parent_agent_id": _safe_identifier(parent_agent_id),
        "status": _safe_status(status),
        "summary": _safe_summary(summary, fallback=""),
        "verification": _safe_summary(verification, fallback=None),
        "blockers": _safe_blockers(blockers or []),
        "next_step": _safe_summary(next_step, fallback=None),
        "privacy_class": _safe_privacy_class(privacy_class),
    }


def normalize_action_ledger_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an existing dict into the action ledger schema."""

    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")
    return build_action_ledger_entry(
        entry.get("event_type"),
        event_id=entry.get("event_id"),
        timestamp=_safe_timestamp(entry.get("timestamp")),
        run_id=entry.get("run_id"),
        session_id=entry.get("session_id"),
        task_id=entry.get("task_id"),
        work_id=entry.get("work_id"),
        agent_id=entry.get("agent_id"),
        parent_agent_id=entry.get("parent_agent_id"),
        status=entry.get("status"),
        summary=entry.get("summary"),
        verification=entry.get("verification"),
        blockers=entry.get("blockers") if isinstance(entry.get("blockers"), list) else [],
        next_step=entry.get("next_step"),
        privacy_class=entry.get("privacy_class"),
    )


def append_action_ledger_entry(
    entry: Dict[str, Any],
    *,
    ledger_path: str | Path = ACTION_LEDGER_PATH,
) -> Dict[str, Any]:
    """Explicitly append one entry to a JSONL action ledger atomically."""

    normalized = normalize_action_ledger_entry(entry)
    _atomic_append_jsonl(Path(ledger_path), normalized)
    return normalized


def _atomic_append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing and not existing.endswith("\n"):
        existing += "\n"

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(existing)
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
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


def _safe_blockers(values: Iterable[Any]) -> list[str]:
    blockers = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in blockers:
            blockers.append(safe)
        if len(blockers) >= BLOCKER_LIMIT:
            break
    return blockers


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


def _safe_privacy_class(value: Any) -> str:
    text = _safe_status(value)
    if text in ALLOWED_PRIVACY_CLASSES:
        return text
    return ACTION_LEDGER_PRIVACY_CLASS


def _safe_timestamp(value: Any) -> Optional[str]:
    text = _string_or_none(value)
    if not text:
        return None
    if _SECRET_RE.search(text) or _ABSOLUTE_PATH_RE.search(text):
        return None
    return text


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _new_event_id() -> str:
    return f"ledger-{uuid.uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
