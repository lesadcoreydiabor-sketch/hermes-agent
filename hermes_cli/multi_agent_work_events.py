"""Privacy-safe multi-agent work event helpers.

This module defines pure normalization helpers for future multi-agent and
memory workbench slices. It does not write files, dispatch tools, mutate
memory providers, or record Run Inspector events by itself.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SUMMARY_LIMIT = 160
ID_LIMIT = 96
ROLE_LIMIT = 64

PRIVACY_CLASS = "redacted_summary"

_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password|credential)\s*[:=]\s*[^,\s;]+"
    r"|\b(?:sk|gh[pousr])[-_][A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s]+)|(?:/(?:Users|home|tmp|var|etc|mnt|workspace)/[^\s]+)",
    re.IGNORECASE,
)
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9_.:/ -]+")


_EVENT_ALIASES = {
    "parent.started": "agent.parent.started",
    "parent_started": "agent.parent.started",
    "agent.parent.started": "agent.parent.started",
    "child.spawned": "agent.child.spawned",
    "child_spawned": "agent.child.spawned",
    "spawned": "agent.child.spawned",
    "agent.child.spawned": "agent.child.spawned",
    "child.running": "agent.child.running",
    "child_running": "agent.child.running",
    "running": "agent.child.running",
    "agent.child.running": "agent.child.running",
    "child.completed": "agent.child.completed",
    "child_completed": "agent.child.completed",
    "completed": "agent.child.completed",
    "agent.child.completed": "agent.child.completed",
    "child.failed": "agent.child.failed",
    "child_failed": "agent.child.failed",
    "failed": "agent.child.failed",
    "agent.child.failed": "agent.child.failed",
    "child.interrupted": "agent.child.interrupted",
    "child_interrupted": "agent.child.interrupted",
    "interrupted": "agent.child.interrupted",
    "agent.child.interrupted": "agent.child.interrupted",
    "child.timeout": "agent.child.timeout",
    "child_timeout": "agent.child.timeout",
    "timeout": "agent.child.timeout",
    "agent.child.timeout": "agent.child.timeout",
}

_EVENT_STATUS = {
    "agent.parent.started": "running",
    "agent.child.spawned": "queued",
    "agent.child.running": "running",
    "agent.child.completed": "completed",
    "agent.child.failed": "failed",
    "agent.child.interrupted": "interrupted",
    "agent.child.timeout": "timeout",
}


def normalize_multi_agent_event_type(event_type: Any) -> str:
    """Normalize known parent/child lifecycle event names."""

    text = _string_or_none(event_type)
    if not text:
        return "agent.unknown"
    key = text.strip().lower().replace(" ", "_")
    return _EVENT_ALIASES.get(key, "agent.unknown")


def build_multi_agent_work_event(
    event_type: Any,
    *,
    work_id: Any = None,
    parent_work_id: Any = None,
    agent_id: Any = None,
    parent_agent_id: Any = None,
    role: Any = None,
    title: Any = None,
    message: Any = None,
    status: Any = None,
    depth: Any = None,
    timestamp: Optional[str] = None,
    source: Any = "multi_agent",
) -> Dict[str, Any]:
    """Return one normalized, redacted multi-agent work event."""

    normalized_type = normalize_multi_agent_event_type(event_type)
    normalized_status = _safe_status(status) or _EVENT_STATUS.get(normalized_type, "unknown")
    safe_title = _safe_text(title)
    safe_message = _safe_text(message)

    return {
        "type": normalized_type,
        "source": _safe_label(source, fallback="multi_agent", limit=ROLE_LIMIT),
        "timestamp": timestamp or _utc_now_iso(),
        "work_id": _safe_identifier(work_id),
        "parent_work_id": _safe_identifier(parent_work_id),
        "agent_id": _safe_identifier(agent_id),
        "parent_agent_id": _safe_identifier(parent_agent_id),
        "role": _safe_label(role, fallback=None, limit=ROLE_LIMIT),
        "title": safe_title,
        "message": safe_message,
        "status": normalized_status,
        "depth": _safe_depth(depth),
        "privacy_class": PRIVACY_CLASS,
    }


def multi_agent_event_to_run_inspector_kwargs(event: Dict[str, Any]) -> Dict[str, Any]:
    """Map a normalized work event into Run Inspector event-ledger kwargs."""

    message = event.get("message") or event.get("title")
    return {
        "event_type": _safe_label(event.get("type"), fallback="agent.unknown", limit=ROLE_LIMIT),
        "source": "multi_agent",
        "run_id": _safe_identifier(event.get("work_id")),
        "session_id": _safe_identifier(event.get("parent_work_id")),
        "tool": _safe_label(event.get("role"), fallback=None, limit=ROLE_LIMIT),
        "status": _safe_status(event.get("status")),
        "message": _safe_text(message),
        "timestamp": _string_or_none(event.get("timestamp")),
    }


def _safe_text(value: Any, *, fallback: Optional[str] = None) -> Optional[str]:
    text = _string_or_none(value)
    if not text:
        return fallback
    if _SECRET_RE.search(text) or _ABSOLUTE_PATH_RE.search(text):
        return "Redacted"
    if len(text) > SUMMARY_LIMIT:
        return text[: SUMMARY_LIMIT - 3] + "..."
    return text


def _safe_identifier(value: Any) -> Optional[str]:
    text = _safe_text(value)
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


def _safe_label(
    value: Any,
    *,
    fallback: Optional[str],
    limit: int,
) -> Optional[str]:
    text = _safe_text(value, fallback=fallback)
    if text is None or text == "Redacted":
        return text
    cleaned = _SAFE_LABEL_RE.sub("_", text).strip()
    if not cleaned:
        return fallback
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def _safe_status(value: Any) -> Optional[str]:
    text = _safe_label(value, fallback=None, limit=ROLE_LIMIT)
    return text.lower() if text else None


def _safe_depth(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return None
    if depth < 0:
        return None
    return min(depth, 10)


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
