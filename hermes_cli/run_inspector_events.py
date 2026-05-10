"""Read-only event ledger for the Run Inspector dashboard.

The ledger stores a bounded, redacted view of recent lifecycle events. It is
intentionally lossy: raw event frames may contain prompts, logs, diffs, or
secrets, so only a small normalized contract is exposed to the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections import deque
from datetime import datetime, timezone
from itertools import count
from typing import Any, Deque, Dict, List, Optional, Tuple


RUN_INSPECTOR_EVENT_LIMIT = 200
_SUMMARY_LIMIT = 160
_SUBSCRIBER_QUEUE_LIMIT = 100
_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s;]+"
    r"|\b(?:sk|gh[pousr])-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)

_events: Deque[Dict[str, Any]] = deque(maxlen=RUN_INSPECTOR_EVENT_LIMIT)
_next_id = count(1)
_lock = threading.RLock()
_subscribers: set[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()


def record_run_inspector_event(
    event_type: str,
    *,
    source: str = "unknown",
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tool: Optional[str] = None,
    status: Optional[str] = None,
    message: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Record one normalized, redacted event and publish it to subscribers."""

    event = {
        "id": next(_next_id),
        "type": _safe_text(event_type, fallback="unknown"),
        "source": _safe_text(source, fallback="unknown"),
        "timestamp": timestamp or _utc_now_iso(),
        "run_id": _safe_optional(run_id),
        "session_id": _safe_optional(session_id),
        "tool": _safe_optional(tool),
        "status": _safe_optional(status),
        "message": _safe_optional(message),
    }

    with _lock:
        _events.append(event)
        subscribers = list(_subscribers)

    for loop, queue in subscribers:
        try:
            loop.call_soon_threadsafe(_offer_event, queue, event)
        except RuntimeError:
            unregister_run_inspector_event_subscriber(queue)

    return dict(event)


def record_run_inspector_event_frame(
    frame_text: str,
    *,
    source: str = "dashboard_chat",
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Normalize and record a dashboard/gateway event frame.

    Malformed frames are ignored so event recording can never break the
    existing chat event broadcast path.
    """

    normalized = normalize_run_inspector_event_frame(
        frame_text,
        source=source,
        session_id=session_id,
    )
    if normalized is None:
        return None
    return record_run_inspector_event(**normalized)


def normalize_run_inspector_event_frame(
    frame_text: str,
    *,
    source: str = "dashboard_chat",
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        frame = json.loads(frame_text)
    except Exception:
        return None
    if not isinstance(frame, dict):
        return None

    payload: Dict[str, Any] = {}
    raw_type: Optional[str] = None
    if frame.get("method") == "event" and isinstance(frame.get("params"), dict):
        params = frame["params"]
        raw_type = _string_or_none(params.get("type"))
        raw_payload = params.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else {}
    else:
        raw_type = _string_or_none(frame.get("type") or frame.get("event"))
        raw_payload = frame.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else frame

    if not raw_type:
        return None

    normalized_type = _normalize_event_type(raw_type)
    tool_name = _first_text(
        payload,
        "name",
        "tool",
        "tool_name",
        "tool_id",
    )
    error_message = _first_text(payload, "error", "last_error", "exception")
    message = _first_text(payload, "message", "preview", "summary", "status", "state")
    status = _status_for_event(normalized_type, payload, error_message)

    if error_message:
        message = error_message

    return {
        "event_type": normalized_type,
        "source": source,
        "run_id": _first_text(payload, "run_id") or _string_or_none(frame.get("run_id")),
        "session_id": _first_text(payload, "session_id") or session_id,
        "tool": tool_name,
        "status": status,
        "message": message,
    }


def get_recent_run_inspector_events(limit: int = 50) -> List[Dict[str, Any]]:
    safe_limit = max(0, min(int(limit), RUN_INSPECTOR_EVENT_LIMIT))
    with _lock:
        if safe_limit == 0:
            return []
        return [dict(event) for event in list(_events)[-safe_limit:]]


def subscribe_run_inspector_events(
    replay: int = 20,
) -> tuple[asyncio.Queue, List[Dict[str, Any]]]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_LIMIT)
    with _lock:
        _subscribers.add((loop, queue))
        replay_events = get_recent_run_inspector_events(replay)
    return queue, replay_events


def unregister_run_inspector_event_subscriber(queue: asyncio.Queue) -> None:
    with _lock:
        for entry in list(_subscribers):
            if entry[1] is queue:
                _subscribers.discard(entry)


def clear_run_inspector_events_for_tests() -> None:
    global _next_id
    with _lock:
        _events.clear()
        _subscribers.clear()
        _next_id = count(1)


def _normalize_event_type(raw_type: str) -> str:
    mapping = {
        "tool.start": "tool.started",
        "tool.started": "tool.started",
        "tool.progress": "tool.progress",
        "tool.complete": "tool.completed",
        "tool.completed": "tool.completed",
        "run.completed": "run.completed",
        "run.failed": "run.failed",
        "run.cancelled": "run.cancelled",
        "approval.request": "approval.request",
        "message.delta": "message.delta",
    }
    return mapping.get(raw_type, raw_type)


def _status_for_event(
    event_type: str,
    payload: Dict[str, Any],
    error_message: Optional[str],
) -> Optional[str]:
    if event_type == "tool.started":
        return "running"
    if event_type == "tool.progress":
        return "running"
    if event_type == "tool.completed":
        return "failed" if error_message or payload.get("error") else "completed"
    if event_type == "run.completed":
        return "completed"
    if event_type == "run.failed":
        return "failed"
    if event_type == "run.cancelled":
        return "cancelled"
    return _first_text(payload, "status", "state")


def _offer_event(queue: asyncio.Queue, event: Dict[str, Any]) -> None:
    try:
        queue.put_nowait(dict(event))
        return
    except asyncio.QueueFull:
        pass
    try:
        queue.get_nowait()
    except Exception:
        pass
    try:
        queue.put_nowait(dict(event))
    except Exception:
        pass


def _first_text(payload: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = _string_or_none(payload.get(key))
        if value:
            return value
    return None


def _safe_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _safe_text(value)


def _safe_text(value: Any, *, fallback: str = "unknown") -> str:
    text = _string_or_none(value)
    if not text:
        return fallback
    if _SECRET_RE.search(text):
        return "Redacted"
    if len(text) > _SUMMARY_LIMIT:
        return text[: _SUMMARY_LIMIT - 3] + "..."
    return text


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
