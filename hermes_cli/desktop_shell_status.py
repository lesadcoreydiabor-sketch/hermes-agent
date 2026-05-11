"""Read-only desktop shell status helpers.

This module is intentionally independent from ``hermes_cli.main`` so the
dashboard server can inspect desktop-shell state without importing the CLI
entrypoint a second time.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError

from hermes_cli.config import get_hermes_home

DESKTOP_DEFAULT_PATH = "/run-inspector"
DESKTOP_RUNTIME_FILE = "desktop_shell.json"

PidStatusResolver = Callable[[dict | None], tuple[int, bool, str]]


def desktop_dashboard_url(
    host: str,
    port: int,
    path: str = DESKTOP_DEFAULT_PATH,
) -> str:
    """Build the local dashboard URL opened by ``hermes desktop``."""
    safe_path = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{port}{safe_path}"


def coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def desktop_runtime_path() -> Path:
    """Return the local runtime record path for the desktop shell."""
    return get_hermes_home() / DESKTOP_RUNTIME_FILE


def read_desktop_runtime_record() -> dict | None:
    path = desktop_runtime_path()
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def remove_desktop_runtime_record() -> None:
    try:
        desktop_runtime_path().unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def desktop_record_url(
    record: dict | None,
    *,
    fallback_port: int,
) -> tuple[str, int, str, str]:
    payload = record or {}
    host = str(payload.get("host") or "127.0.0.1")
    port = coerce_int(payload.get("port"), fallback_port)
    route = str(payload.get("route") or DESKTOP_DEFAULT_PATH)
    url = desktop_dashboard_url(host, port, route)
    return host, port, route, url


def default_desktop_pid_status(record: dict | None) -> tuple[int, bool, str]:
    """Return best-effort runtime PID status without CLI process scanning."""
    pid = coerce_int((record or {}).get("pid"))
    if pid <= 0:
        return 0, False, "invalid_pid"
    if pid == os.getpid():
        return pid, True, "current_process"
    try:
        from gateway.status import _pid_exists
    except Exception:
        return pid, False, "process_scan_unavailable"
    try:
        return (pid, True, "running") if _pid_exists(pid) else (pid, False, "not_found")
    except Exception:
        return pid, False, "process_scan_failed"


def probe_dashboard_status(
    host: str,
    port: int,
    *,
    timeout: float = 0.75,
) -> tuple[bool, str]:
    """Return whether a local port is serving the Hermes dashboard status API."""
    url = desktop_dashboard_url(host, port, "/api/status")
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096)
    except HTTPError as exc:
        return False, f"http_{exc.code}"
    except (OSError, TimeoutError, URLError) as exc:
        return False, exc.__class__.__name__

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "invalid_status_payload"

    if isinstance(payload, dict) and "version" in payload and "hermes_home" in payload:
        return True, "ok"
    return False, "non_hermes_status_payload"


def build_desktop_status_payload(
    *,
    clear_stale_record: bool = False,
    pid_status_fn: PidStatusResolver | None = None,
    port: int = 9119,
) -> dict:
    """Return a token-free, machine-readable desktop shell status payload."""
    record = read_desktop_runtime_record()
    host, resolved_port, route, url = desktop_record_url(
        record,
        fallback_port=port,
    )
    pid = 0
    pid_reason = "no_record"
    pid_status = "none"
    runtime_record_cleared = False

    if record:
        resolver = pid_status_fn or default_desktop_pid_status
        pid, running, pid_reason = resolver(record)
        pid_status = "running" if running else "stale"
        if not running and clear_stale_record:
            remove_desktop_runtime_record()
            runtime_record_cleared = True

    reachable, reason = probe_dashboard_status(host, resolved_port)
    compatible_dashboard = not record and reachable
    next_action, next_command, attention_level = desktop_operator_next_action(
        record_present=bool(record),
        pid_status=pid_status,
        health_ok=reachable,
        compatible_dashboard=compatible_dashboard,
        port=resolved_port,
    )
    return {
        "ok": True,
        "record_present": bool(record),
        "runtime_record_cleared": runtime_record_cleared,
        "pid": pid or None,
        "pid_status": pid_status,
        "pid_reason": pid_reason,
        "host": host,
        "port": resolved_port,
        "route": route,
        "url": url,
        "started_at": record.get("started_at") if record else None,
        "health": "ok" if reachable else "unavailable",
        "health_reason": reason,
        "compatible_dashboard": compatible_dashboard,
        "attention_level": attention_level,
        "next_action": next_action,
        "next_command": next_command,
        "reuse_command": (
            f"hermes desktop --port {resolved_port}"
            if compatible_dashboard
            else None
        ),
        "manual_url": url if compatible_dashboard else None,
        "stop_command": (
            "hermes dashboard --stop"
            if compatible_dashboard
            else f"hermes desktop --port {resolved_port} --stop"
            if record
            else None
        ),
    }


def desktop_operator_next_action(
    *,
    record_present: bool,
    pid_status: str,
    health_ok: bool,
    compatible_dashboard: bool,
    port: int,
) -> tuple[str, str | None, str]:
    """Return the safe operator action implied by desktop shell status."""
    desktop_command = f"hermes desktop --port {port}"
    if record_present and pid_status == "running" and health_ok:
        return "Open Run Inspector", None, "ok"
    if compatible_dashboard:
        return "Reuse compatible dashboard", desktop_command, "info"
    if record_present and pid_status == "stale":
        return "Restart desktop shell", desktop_command, "warning"
    if record_present and not health_ok:
        return "Check dashboard health", f"{desktop_command} --status", "warning"
    if not record_present and not health_ok:
        return "Start desktop shell", desktop_command, "info"
    return "Check desktop shell", f"{desktop_command} --status", "warning"
