"""Cross-process gateway run event forwarding for Run Inspector.

The gateway API server exposes per-run lifecycle events as SSE at
``/v1/runs/{run_id}/events``. When the dashboard and gateway run in different
processes, the in-process event ledger cannot see those events. This module
follows a configured gateway stream from the dashboard process and records the
same privacy-safe event contract used by Run Inspector.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Iterator, Optional

from agent.redact import redact_sensitive_text

from hermes_cli.run_inspector_events import (
    record_run_inspector_event,
    record_run_inspector_event_frame,
)


DEFAULT_GATEWAY_EVENT_TIMEOUT_SECONDS = 30.0
DEFAULT_GATEWAY_EVENT_PORT = 8642
TERMINAL_GATEWAY_EVENTS = frozenset({
    "run.completed",
    "run.failed",
    "run.cancelled",
})
_SUMMARY_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s;]+"
    r"|\b(?:sk|gh[pousr])-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)

_forwarders: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()


def resolve_gateway_event_base_url(env: Optional[dict[str, str]] = None) -> Optional[str]:
    """Return the configured gateway API base URL for event forwarding."""

    env_map = os.environ if env is None else env
    explicit = _clean_env(env_map.get("HERMES_RUN_INSPECTOR_GATEWAY_URL"))
    if explicit:
        return _normalize_gateway_base_url(explicit)

    health_url = _clean_env(env_map.get("GATEWAY_HEALTH_URL"))
    if health_url:
        return _normalize_gateway_base_url(health_url)

    configured = any(
        _clean_env(env_map.get(name))
        for name in (
            "API_SERVER_ENABLED",
            "API_SERVER_KEY",
            "API_SERVER_HOST",
            "API_SERVER_PORT",
        )
    )
    if not configured:
        return None

    host = _clean_env(env_map.get("API_SERVER_HOST")) or "127.0.0.1"
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = _clean_env(env_map.get("API_SERVER_PORT")) or str(DEFAULT_GATEWAY_EVENT_PORT)
    try:
        safe_port = int(port)
    except (TypeError, ValueError):
        safe_port = DEFAULT_GATEWAY_EVENT_PORT
    return f"http://{host}:{safe_port}"


def resolve_gateway_event_api_key(env: Optional[dict[str, str]] = None) -> Optional[str]:
    """Return the gateway auth key without exposing it to the frontend."""

    env_map = os.environ if env is None else env
    return _clean_env(env_map.get("HERMES_RUN_INSPECTOR_GATEWAY_KEY")) or _clean_env(
        env_map.get("API_SERVER_KEY")
    )


def get_gateway_run_event_forwarder_status(run_id: Optional[str] = None) -> dict[str, Any]:
    """Return a copy of one forwarder status or all known statuses."""

    with _lock:
        if run_id:
            return dict(_forwarders.get(run_id, {}))
        return {key: dict(value) for key, value in _forwarders.items()}


def clear_gateway_run_event_forwarders_for_tests() -> None:
    with _lock:
        _forwarders.clear()


def start_gateway_run_event_forwarder(
    run_id: str,
    *,
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_GATEWAY_EVENT_TIMEOUT_SECONDS,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Start a background follower for one gateway run event stream."""

    safe_run_id = _validate_run_id(run_id)
    safe_base_url = _normalize_gateway_base_url(base_url)
    with _lock:
        existing = _forwarders.get(safe_run_id)
        if existing and existing.get("state") == "running":
            status = dict(existing)
            status["already_running"] = True
            return status

        status = {
            "run_id": safe_run_id,
            "state": "running",
            "started_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "events_forwarded": 0,
            "last_error": None,
            "gateway_url": _redacted_gateway_url(safe_base_url),
            "already_running": False,
        }
        _forwarders[safe_run_id] = status

    record_run_inspector_event(
        "gateway.forwarder.started",
        source="run_inspector",
        run_id=safe_run_id,
        status="running",
    )

    thread = threading.Thread(
        target=_run_gateway_forwarder_thread,
        args=(safe_run_id, safe_base_url, api_key, timeout, urlopen),
        daemon=True,
        name=f"run-inspector-gateway-forwarder-{safe_run_id}",
    )
    thread.start()
    return get_gateway_run_event_forwarder_status(safe_run_id)


def forward_gateway_run_events(
    run_id: str,
    *,
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_GATEWAY_EVENT_TIMEOUT_SECONDS,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> int:
    """Synchronously forward one gateway SSE stream into Run Inspector."""

    safe_run_id = _validate_run_id(run_id)
    request = _build_gateway_events_request(safe_run_id, base_url, api_key)
    forwarded = 0
    with urlopen(request, timeout=timeout) as response:
        for data in _iter_sse_data(response):
            event = record_run_inspector_event_frame(
                data,
                source="gateway_run",
                session_id=safe_run_id,
            )
            if event is None:
                continue
            forwarded += 1
            if event.get("type") in TERMINAL_GATEWAY_EVENTS:
                break
    return forwarded


def fetch_gateway_run_summaries(
    *,
    base_url: str,
    api_key: Optional[str] = None,
    limit: int = 20,
    timeout: float = DEFAULT_GATEWAY_EVENT_TIMEOUT_SECONDS,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    """Fetch recent gateway runs and normalize to dashboard-safe summaries."""

    safe_limit = max(1, min(int(limit), 50))
    request = _build_gateway_runs_request(base_url, api_key, safe_limit)
    with urlopen(request, timeout=timeout) as response:
        raw_body = response.read()
    payload = json_loads_bytes(raw_body)
    raw_runs = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_runs, list):
        return []
    return [
        run
        for run in (_normalize_gateway_run_summary(item) for item in raw_runs)
        if run is not None
    ]


def _run_gateway_forwarder_thread(
    run_id: str,
    base_url: str,
    api_key: Optional[str],
    timeout: float,
    urlopen: Callable[..., Any],
) -> None:
    try:
        forwarded = forward_gateway_run_events(
            run_id,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            urlopen=urlopen,
        )
        _update_forwarder(run_id, state="completed", events_forwarded=forwarded)
        record_run_inspector_event(
            "gateway.forwarder.completed",
            source="run_inspector",
            run_id=run_id,
            status="completed",
            message=f"forwarded {forwarded} events",
        )
    except urllib.error.HTTPError as exc:
        message = f"gateway event stream returned HTTP {exc.code}"
        _update_forwarder(run_id, state="failed", last_error=message)
        record_run_inspector_event(
            "gateway.forwarder.failed",
            source="run_inspector",
            run_id=run_id,
            status="failed",
            message=message,
        )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        _update_forwarder(run_id, state="failed", last_error=message)
        record_run_inspector_event(
            "gateway.forwarder.failed",
            source="run_inspector",
            run_id=run_id,
            status="failed",
            message=message,
        )


def _build_gateway_events_request(
    run_id: str,
    base_url: str,
    api_key: Optional[str],
) -> urllib.request.Request:
    quoted_run_id = urllib.parse.quote(_validate_run_id(run_id), safe="")
    url = f"{_normalize_gateway_base_url(base_url)}/v1/runs/{quoted_run_id}/events"
    headers = {"Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return urllib.request.Request(url, headers=headers, method="GET")


def _build_gateway_runs_request(
    base_url: str,
    api_key: Optional[str],
    limit: int,
) -> urllib.request.Request:
    url = f"{_normalize_gateway_base_url(base_url)}/v1/runs?limit={int(limit)}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return urllib.request.Request(url, headers=headers, method="GET")


def _normalize_gateway_run_summary(value: Any) -> Optional[dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    run_id = _safe_summary_text(value.get("run_id"))
    if not run_id:
        return None
    return {
        "run_id": run_id,
        "status": _safe_summary_text(value.get("status")) or "unknown",
        "created_at": _safe_number(value.get("created_at")),
        "updated_at": _safe_number(value.get("updated_at")),
        "session_id": _safe_summary_text(value.get("session_id")),
        "model": _safe_summary_text(value.get("model")),
        "last_event": _safe_summary_text(value.get("last_event")),
        "has_error": bool(value.get("has_error")),
    }


def json_loads_bytes(raw_body: bytes | str) -> Any:
    import json

    text = raw_body.decode("utf-8", "replace") if isinstance(raw_body, bytes) else str(raw_body)
    return json.loads(text)


def _iter_sse_data(lines: Iterable[bytes | str]) -> Iterator[str]:
    data_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8", "replace") if isinstance(raw_line, bytes) else str(raw_line)
        line = line.rstrip("\r\n")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _update_forwarder(run_id: str, **fields: Any) -> None:
    with _lock:
        status = _forwarders.setdefault(run_id, {"run_id": run_id})
        status.update(fields)
        status["updated_at"] = _utc_now_iso()


def _normalize_gateway_base_url(url: str) -> str:
    text = str(url or "").strip().rstrip("/")
    if text.endswith("/health/detailed"):
        text = text[: -len("/health/detailed")]
    elif text.endswith("/health"):
        text = text[: -len("/health")]
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("gateway event URL must be an http(s) base URL")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _redacted_gateway_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _validate_run_id(run_id: str) -> str:
    text = str(run_id or "").strip()
    if not text:
        raise ValueError("run_id is required")
    if len(text) > 120:
        raise ValueError("run_id is too long")
    return text


def _safe_summary_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    redacted = redact_sensitive_text(text, force=True)
    return _SUMMARY_SECRET_RE.sub("Redacted", redacted)


def _safe_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_env(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
