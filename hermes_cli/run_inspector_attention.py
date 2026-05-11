"""Safe attention-signal policy for Run Inspector.

This module converts the existing privacy-safe Run Inspector snapshot and event
contracts into short attention signals. It deliberately does not deliver browser
or OS notifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from agent.redact import redact_sensitive_text

from hermes_cli.run_inspector import RunSnapshot


ATTENTION_SIGNAL_TTL_MS = 10 * 60 * 1000
ATTENTION_ROUTE = "/run-inspector"

ATTENTION_SIGNAL_KINDS = frozenset({
    "approval_waiting",
    "run_failed",
    "run_degraded",
    "mcp_degraded",
    "desktop_shell_degraded",
    "recovery_available",
})

ATTENTION_SEVERITIES = frozenset({
    "critical",
    "warning",
    "info",
})

ATTENTION_PRIVACY_CLASSES = frozenset({
    "safe_summary",
    "redacted_summary",
    "local_only",
})

_IDENTIFIER_LIMIT = 96
_PATH_RE = re.compile(
    r"([A-Za-z]:\\|/[^/\s]+/|~[/\\]|\\\\[^\\]+\\|[^\s]+[/\\][^\s]+)"
)
_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s;]+"
    r"|\b(?:sk|gh[pousr])-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
_SAFE_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class RunInspectorAttentionSignal:
    """Notification-safe summary of a run state that needs attention."""

    kind: str
    severity: str
    title: str
    body: str
    route: str = ATTENTION_ROUTE
    run_id: str | None = None
    session_id: str | None = None
    timestamp: str | None = None
    dedupe_key: str | None = None
    ttl_ms: int = ATTENTION_SIGNAL_TTL_MS
    privacy_class: str = "redacted_summary"

    def __post_init__(self) -> None:
        kind = self.kind if self.kind in ATTENTION_SIGNAL_KINDS else "run_degraded"
        severity = self.severity if self.severity in ATTENTION_SEVERITIES else "warning"
        route = _safe_route(self.route)
        run_id = _safe_identifier(self.run_id)
        session_id = _safe_identifier(self.session_id)
        timestamp = _safe_timestamp(self.timestamp)
        ttl_ms = _safe_ttl_ms(self.ttl_ms)
        privacy_class = (
            self.privacy_class
            if self.privacy_class in ATTENTION_PRIVACY_CLASSES
            else "redacted_summary"
        )
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "title", _safe_title(self.title, kind))
        object.__setattr__(self, "body", _safe_body(self.body, kind))
        object.__setattr__(self, "route", route)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(
            self,
            "dedupe_key",
            _safe_dedupe_key(self.dedupe_key, kind, run_id, session_id),
        )
        object.__setattr__(self, "ttl_ms", ttl_ms)
        object.__setattr__(self, "privacy_class", privacy_class)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | None,
    ) -> "RunInspectorAttentionSignal | None":
        if not isinstance(value, Mapping):
            return None
        try:
            return cls(
                kind=str(value.get("kind") or "run_degraded"),
                severity=str(value.get("severity") or "warning"),
                title=str(value.get("title") or ""),
                body=str(value.get("body") or ""),
                route=str(value.get("route") or ATTENTION_ROUTE),
                run_id=value.get("run_id"),
                session_id=value.get("session_id"),
                timestamp=value.get("timestamp"),
                dedupe_key=value.get("dedupe_key"),
                ttl_ms=int(value.get("ttl_ms") or ATTENTION_SIGNAL_TTL_MS),
                privacy_class=str(value.get("privacy_class") or "redacted_summary"),
            )
        except Exception:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "route": self.route,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "dedupe_key": self.dedupe_key,
            "ttl_ms": self.ttl_ms,
            "privacy_class": self.privacy_class,
        }


def attention_signals_for_snapshot(
    snapshot: RunSnapshot | Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> list[RunInspectorAttentionSignal]:
    """Return safe attention signals derived from one run snapshot."""

    snap = _coerce_snapshot(snapshot)
    current_time = _timestamp_for_now(now)
    signals: list[RunInspectorAttentionSignal] = []

    if _is_desktop_shell_degraded(snap.degraded_reason):
        signals.append(
            _signal(
                "desktop_shell_degraded",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
            )
        )

    if snap.status == "waiting_approval":
        signals.append(
            _signal(
                "approval_waiting",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
            )
        )
    elif snap.status == "failed":
        signals.append(
            _signal(
                "run_failed",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
            )
        )
    elif snap.status in {"rate_limited", "recovering", "unknown"} and snap.degraded_reason:
        signals.append(
            _signal(
                "run_degraded",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
            )
        )

    degraded_mcp_count = sum(
        1 for item in snap.mcp_health if item.status in {"degraded", "failed"}
    )
    if degraded_mcp_count:
        signals.append(
            _signal(
                "mcp_degraded",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
                body=_mcp_degraded_body(degraded_mcp_count),
            )
        )

    if snap.recovery_hint:
        signals.append(
            _signal(
                "recovery_available",
                run_id=snap.run_id,
                session_id=snap.session_id,
                timestamp=current_time,
            )
        )

    return dedupe_attention_signals(signals, now=now)


def attention_signals_for_events(
    events: Iterable[Mapping[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> list[RunInspectorAttentionSignal]:
    """Return safe attention signals derived from normalized Run Inspector events."""

    if events is None:
        return []

    signals: list[RunInspectorAttentionSignal] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_type = str(event.get("type") or "").strip().lower()
        status = str(event.get("status") or "").strip().lower()
        run_id = event.get("run_id")
        session_id = event.get("session_id")
        timestamp = _safe_timestamp(event.get("timestamp"))

        if event_type == "approval.request" or status == "waiting":
            signals.append(
                _signal(
                    "approval_waiting",
                    run_id=run_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
            )
        elif event_type == "run.failed" or (
            event_type.startswith("run.") and status == "failed"
        ):
            signals.append(
                _signal(
                    "run_failed",
                    run_id=run_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
            )
        elif event_type == "gateway.forwarder.failed" or status == "failed":
            signals.append(
                _signal(
                    "run_degraded",
                    run_id=run_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
            )

    return dedupe_attention_signals(signals, now=now)


def build_attention_signals(
    *,
    snapshot: RunSnapshot | Mapping[str, Any] | None = None,
    events: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build deduped attention signals from snapshot and event sources."""

    signals = [
        *attention_signals_for_snapshot(snapshot, now=now),
        *attention_signals_for_events(events, now=now),
    ]
    return [signal.to_dict() for signal in dedupe_attention_signals(signals, now=now)]


def dedupe_attention_signals(
    signals: Iterable[RunInspectorAttentionSignal | Mapping[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> list[RunInspectorAttentionSignal]:
    """Drop expired signals and keep the newest signal for each dedupe key."""

    if signals is None:
        return []
    current_time = now or datetime.now(timezone.utc)
    by_key: dict[str, RunInspectorAttentionSignal] = {}
    for raw_signal in signals:
        signal = _coerce_signal(raw_signal)
        if signal is None or is_attention_signal_expired(signal, now=current_time):
            continue
        existing = by_key.get(signal.dedupe_key or "")
        if existing is None or _timestamp_sort_key(signal) >= _timestamp_sort_key(existing):
            by_key[signal.dedupe_key or ""] = signal

    return sorted(by_key.values(), key=_timestamp_sort_key)


def is_attention_signal_expired(
    signal: RunInspectorAttentionSignal | Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether the signal is older than its TTL."""

    coerced = _coerce_signal(signal)
    if coerced is None:
        return True
    timestamp = _parse_timestamp(coerced.timestamp)
    if timestamp is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return (current_time - timestamp).total_seconds() * 1000 > coerced.ttl_ms


def _coerce_snapshot(snapshot: RunSnapshot | Mapping[str, Any] | None) -> RunSnapshot:
    if isinstance(snapshot, RunSnapshot):
        return snapshot
    return RunSnapshot.from_mapping(snapshot)


def _coerce_signal(
    signal: RunInspectorAttentionSignal | Mapping[str, Any],
) -> RunInspectorAttentionSignal | None:
    if isinstance(signal, RunInspectorAttentionSignal):
        return signal
    if isinstance(signal, Mapping):
        return RunInspectorAttentionSignal.from_mapping(signal)
    return None


def _signal(
    kind: str,
    *,
    run_id: Any = None,
    session_id: Any = None,
    timestamp: str | None = None,
    body: str | None = None,
) -> RunInspectorAttentionSignal:
    title, default_body, severity = _copy_for_kind(kind)
    return RunInspectorAttentionSignal(
        kind=kind,
        severity=severity,
        title=title,
        body=body or default_body,
        run_id=run_id,
        session_id=session_id,
        timestamp=timestamp,
        privacy_class="redacted_summary",
    )


def _copy_for_kind(kind: str) -> tuple[str, str, str]:
    mapping = {
        "approval_waiting": (
            "Approval waiting",
            "A HERMES run is waiting for approval. Open Run Inspector to review safe details.",
            "warning",
        ),
        "run_failed": (
            "Run failed",
            "A HERMES run failed. Open Run Inspector for the redacted failure summary.",
            "critical",
        ),
        "run_degraded": (
            "Run degraded",
            "A HERMES run is degraded. Open Run Inspector for safe diagnostics.",
            "warning",
        ),
        "mcp_degraded": (
            "MCP degraded",
            "One or more MCP servers are degraded. Open Run Inspector for safe details.",
            "warning",
        ),
        "desktop_shell_degraded": (
            "Desktop shell degraded",
            "The local desktop shell is degraded. Open Run Inspector or run hermes desktop --status.",
            "warning",
        ),
        "recovery_available": (
            "Recovery available",
            "Recovery guidance is available in Run Inspector.",
            "info",
        ),
    }
    return mapping.get(kind, mapping["run_degraded"])


def _mcp_degraded_body(count: int) -> str:
    noun = "server" if count == 1 else "servers"
    return f"{count} MCP {noun} need attention. Open Run Inspector for safe details."


def _is_desktop_shell_degraded(reason: str | None) -> bool:
    if not reason:
        return False
    normalized = reason.strip().lower()
    return any(
        token in normalized
        for token in ("desktop", "dashboard", "shell", "port_busy", "server_start")
    )


def _safe_route(route: Any) -> str:
    text = str(route or ATTENTION_ROUTE).strip()
    if not text.startswith("/") or "://" in text or "token=" in text.lower():
        return ATTENTION_ROUTE
    return text.split("?", 1)[0] or ATTENTION_ROUTE


def _safe_title(value: Any, kind: str) -> str:
    title = _safe_summary(value, limit=64)
    if title:
        return title
    return _copy_for_kind(kind)[0]


def _safe_body(value: Any, kind: str) -> str:
    body = _safe_summary(value, limit=180)
    if body:
        return body
    return _copy_for_kind(kind)[1]


def _safe_summary(value: Any, *, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    redacted = redact_sensitive_text(text, force=True)
    if _PATH_RE.search(redacted):
        redacted = _PATH_RE.sub("[redacted-path]", redacted)
    if len(redacted) > limit:
        redacted = redacted[: limit - 3] + "..."
    return redacted


def _safe_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    redacted = redact_sensitive_text(text, force=True)
    if "***" in redacted or _SECRET_RE.search(redacted) or _PATH_RE.search(redacted):
        return "redacted"
    normalized = _SAFE_IDENTIFIER_RE.sub("-", redacted).strip("-")
    if not normalized:
        return "redacted"
    return normalized[:_IDENTIFIER_LIMIT]


def _safe_timestamp(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return datetime.now(timezone.utc).isoformat()
    return parsed.isoformat()


def _timestamp_for_now(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(float(value), timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_ttl_ms(value: Any) -> int:
    try:
        ttl_ms = int(value)
    except (TypeError, ValueError):
        return ATTENTION_SIGNAL_TTL_MS
    if ttl_ms <= 0:
        return ATTENTION_SIGNAL_TTL_MS
    return min(ttl_ms, 24 * 60 * 60 * 1000)


def _safe_dedupe_key(
    dedupe_key: Any,
    kind: str,
    run_id: str | None,
    session_id: str | None,
) -> str:
    explicit = _safe_identifier(dedupe_key)
    if explicit:
        return explicit
    scope = run_id or session_id or "global"
    return f"{kind}:{scope}"


def _timestamp_sort_key(signal: RunInspectorAttentionSignal) -> datetime:
    return _parse_timestamp(signal.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
