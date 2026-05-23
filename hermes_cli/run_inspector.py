"""Read-only run snapshot contract for HERMES operator inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from agent.redact import redact_sensitive_text


RUN_SNAPSHOT_VERSION = 1

RUN_SOURCES = frozenset({
    "cli",
    "gateway",
    "acp",
    "mcp",
    "eval",
    "unknown",
})

RUN_STATUSES = frozenset({
    "starting",
    "thinking",
    "executing_tool",
    "waiting_input",
    "waiting_approval",
    "rate_limited",
    "recovering",
    "completed",
    "failed",
    "stopped",
    "unknown",
})

MCP_HEALTH_STATUSES = frozenset({
    "connected",
    "degraded",
    "failed",
    "unknown",
})

TOOL_HEALTH_STATUSES = frozenset({
    "available",
    "unavailable",
    "running",
    "failed",
    "unknown",
})

PRIVACY_FLAGS = frozenset({
    "safe",
    "redacted",
    "local_only",
    "unknown",
})

FAILURE_REVIEW_TRIGGERS = frozenset({
    "failed_verification",
    "blocked_task",
    "repeated_tool_error",
    "redaction_failure",
    "user_interruption",
    "repeated_unknown_state",
    "unknown",
})

BLOCKING_FAILURE_TRIGGERS = frozenset({
    "redaction_failure",
})

FAILURE_REVIEW_FIELDS = (
    "trigger",
    "task_id",
    "what_happened",
    "why_it_failed",
    "what_changed",
    "how_it_was_verified",
    "added_eval_or_badcase",
    "blocker",
)

SNAPSHOT_FIELD_PRIVACY = {
    "version": "safe",
    "run_id": "local_only",
    "source": "safe",
    "status": "safe",
    "reason": "redacted",
    "workspace": "local_only",
    "session_id": "local_only",
    "last_activity_at": "safe",
    "active_tool": "redacted",
    "tool_health": "safe",
    "mcp_health": "local_only",
    "recovery_hint": "redacted",
    "privacy_flags": "safe",
    "degraded_reason": "safe",
}

_ACTIVE_SESSION_WINDOW_SECONDS = 300.0
_PRIVATE_PAYLOAD_MAX_KEYS = 20
_FAILED_SESSION_REASONS = frozenset({
    "error",
    "failed",
    "failure",
    "exception",
    "crash",
    "startup_failed",
})
_STOPPED_SESSION_REASONS = frozenset({
    "cancelled",
    "canceled",
    "interrupted",
    "stopped",
    "user_exit",
})
_GATEWAY_SESSION_SOURCES = frozenset({
    "bluebubbles",
    "dingtalk",
    "discord",
    "email",
    "feishu",
    "google_chat",
    "homeassistant",
    "matrix",
    "mattermost",
    "qqbot",
    "signal",
    "slack",
    "sms",
    "telegram",
    "teams",
    "webhook",
    "wecom",
    "weixin",
    "whatsapp",
    "yuanbao",
})


def _normalize_choice(value: Any, allowed: frozenset[str], default: str = "unknown") -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in allowed:
            return normalized
    return default


def _safe_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return redact_sensitive_text(text, force=True)


def _safe_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _safe_text(value)
        return (text,) if text else ()
    try:
        values = tuple(value)
    except TypeError:
        text = _safe_text(value)
        return (text,) if text else ()
    result: list[str] = []
    for item in values:
        text = _safe_text(item)
        if text:
            result.append(text)
    return tuple(result)


def _normalize_privacy_flags(value: Any) -> tuple[str, ...]:
    flags: list[str] = []
    for item in _safe_tuple(value):
        normalized = _normalize_choice(item, PRIVACY_FLAGS)
        if normalized not in flags:
            flags.append(normalized)
    return tuple(flags)


def _duration_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return None
    if duration < 0:
        return None
    return duration


def _unix_timestamp_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return _safe_text(value)
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return _safe_text(value)


def _session_source(value: Any) -> str:
    source = _safe_text(value)
    if source is None:
        return "unknown"
    normalized = source.strip().lower()
    if normalized in RUN_SOURCES:
        return normalized
    if normalized in _GATEWAY_SESSION_SOURCES:
        return "gateway"
    return "unknown"


def _reason_contains(reason: str | None, needles: frozenset[str]) -> bool:
    if not reason:
        return False
    normalized = reason.strip().lower()
    return any(needle in normalized for needle in needles)


def _session_status(record: Mapping[str, Any], *, now: float | None = None) -> str:
    explicit_status = record.get("status")
    if explicit_status is not None:
        status = _normalize_choice(explicit_status, RUN_STATUSES)
        if status != "unknown":
            return status

    ended_at = record.get("ended_at")
    end_reason = _safe_text(record.get("end_reason"))
    if ended_at is not None:
        if _reason_contains(end_reason, _FAILED_SESSION_REASONS):
            return "failed"
        if _reason_contains(end_reason, _STOPPED_SESSION_REASONS):
            return "stopped"
        return "completed"

    last_active = record.get("last_active", record.get("started_at"))
    if now is not None and last_active is not None:
        try:
            age = float(now) - float(last_active)
        except (TypeError, ValueError):
            return "unknown"
        if age < 0:
            return "unknown"
        if age <= _ACTIVE_SESSION_WINDOW_SECONDS:
            return "thinking"
        return "waiting_input"

    return "unknown"


def _gateway_status(record: Mapping[str, Any]) -> str:
    state = _safe_text(record.get("gateway_state"))
    if not state:
        return "unknown"
    normalized = state.strip().lower()
    if normalized == "starting":
        return "starting"
    if normalized in {"running", "ready", "healthy"}:
        try:
            active_agents = int(record.get("active_agents") or 0)
        except (TypeError, ValueError):
            active_agents = 0
        return "thinking" if active_agents > 0 else "waiting_input"
    if normalized in {"stopping", "stopped"}:
        return "stopped"
    if normalized in {"startup_failed", "failed", "fatal"}:
        return "failed"
    if normalized in {"recovering", "restarting"}:
        return "recovering"
    return "unknown"


def _gateway_run_id(record: Mapping[str, Any]) -> str:
    pid = _safe_text(record.get("pid"))
    if pid:
        return f"gateway:{pid}"
    return "gateway"


def _payload_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _safe_mapping_pairs(value: Mapping[Any, Any]) -> list[tuple[str, Any]]:
    pairs = [(_safe_text(key) or "unknown", item) for key, item in value.items()]
    return sorted(pairs, key=lambda pair: pair[0])


def _coerce_args_summary(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return summarize_tool_arguments(value)


@dataclass(frozen=True)
class ActiveToolSnapshot:
    """Safe metadata for the currently executing tool, when known."""

    name: str | None = None
    call_id: str | None = None
    duration_ms: int | None = None
    args_summary: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _safe_text(self.name))
        object.__setattr__(self, "call_id", _safe_text(self.call_id))
        object.__setattr__(self, "duration_ms", _duration_ms(self.duration_ms))
        object.__setattr__(self, "args_summary", _coerce_args_summary(self.args_summary))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ActiveToolSnapshot":
        if not isinstance(value, Mapping):
            return cls()
        args = None
        for key in ("args", "arguments", "tool_args", "input"):
            if key in value:
                args = value.get(key)
                break
        return cls(
            name=value.get("name"),
            call_id=value.get("call_id"),
            duration_ms=value.get("duration_ms"),
            args_summary=args,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "call_id": self.call_id,
            "duration_ms": self.duration_ms,
            "args_summary": self.args_summary,
        }


@dataclass(frozen=True)
class MCPHealthSnapshot:
    """Safe metadata for one MCP server's health."""

    name: str | None = None
    status: str = "unknown"
    last_error_class: str | None = None
    affected_tools: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _safe_text(self.name))
        object.__setattr__(
            self,
            "status",
            _normalize_choice(self.status, MCP_HEALTH_STATUSES),
        )
        object.__setattr__(self, "last_error_class", _safe_text(self.last_error_class))
        object.__setattr__(self, "affected_tools", _safe_tuple(self.affected_tools))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "MCPHealthSnapshot":
        if not isinstance(value, Mapping):
            return cls()
        return cls(
            name=value.get("name"),
            status=value.get("status", "unknown"),
            last_error_class=value.get("last_error_class"),
            affected_tools=value.get("affected_tools") or (),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "last_error_class": self.last_error_class,
            "affected_tools": list(self.affected_tools),
        }


@dataclass(frozen=True)
class ToolHealthSnapshot:
    """Safe metadata for one registered tool's availability."""

    name: str | None = None
    toolset: str | None = None
    status: str = "unknown"
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _safe_text(self.name))
        object.__setattr__(self, "toolset", _safe_text(self.toolset))
        object.__setattr__(
            self,
            "status",
            _normalize_choice(self.status, TOOL_HEALTH_STATUSES),
        )
        object.__setattr__(self, "reason", _safe_text(self.reason))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ToolHealthSnapshot":
        if not isinstance(value, Mapping):
            return cls()
        return cls(
            name=value.get("name"),
            toolset=value.get("toolset"),
            status=value.get("status", "unknown"),
            reason=value.get("reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "toolset": self.toolset,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RunSnapshot:
    """Versioned, privacy-safe, read-only snapshot of a HERMES run."""

    version: int = RUN_SNAPSHOT_VERSION
    run_id: str = "unknown"
    source: str = "unknown"
    status: str = "unknown"
    reason: str | None = None
    workspace: str | None = None
    session_id: str | None = None
    last_activity_at: str | None = None
    active_tool: ActiveToolSnapshot = field(default_factory=ActiveToolSnapshot)
    tool_health: tuple[ToolHealthSnapshot, ...] = field(default_factory=tuple)
    mcp_health: tuple[MCPHealthSnapshot, ...] = field(default_factory=tuple)
    recovery_hint: str | None = None
    privacy_flags: tuple[str, ...] = field(default_factory=tuple)
    degraded_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", RUN_SNAPSHOT_VERSION)
        object.__setattr__(self, "run_id", _safe_text(self.run_id) or "unknown")
        object.__setattr__(self, "source", _normalize_choice(self.source, RUN_SOURCES))
        object.__setattr__(self, "status", _normalize_choice(self.status, RUN_STATUSES))
        object.__setattr__(self, "reason", _safe_text(self.reason))
        object.__setattr__(self, "workspace", _safe_text(self.workspace))
        object.__setattr__(self, "session_id", _safe_text(self.session_id))
        object.__setattr__(self, "last_activity_at", _safe_text(self.last_activity_at))
        object.__setattr__(self, "active_tool", _coerce_active_tool(self.active_tool))
        object.__setattr__(self, "tool_health", _coerce_tool_health(self.tool_health))
        object.__setattr__(self, "mcp_health", _coerce_mcp_health(self.mcp_health))
        object.__setattr__(self, "recovery_hint", _safe_text(self.recovery_hint))
        object.__setattr__(
            self,
            "privacy_flags",
            _normalize_privacy_flags(self.privacy_flags),
        )
        object.__setattr__(self, "degraded_reason", _safe_text(self.degraded_reason))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "RunSnapshot":
        if not isinstance(value, Mapping):
            return cls(degraded_reason="invalid_snapshot_payload")
        return cls(
            run_id=value.get("run_id", "unknown"),
            source=value.get("source", "unknown"),
            status=value.get("status", "unknown"),
            reason=value.get("reason"),
            workspace=value.get("workspace"),
            session_id=value.get("session_id"),
            last_activity_at=value.get("last_activity_at"),
            active_tool=ActiveToolSnapshot.from_mapping(value.get("active_tool")),
            tool_health=tuple(
                ToolHealthSnapshot.from_mapping(item)
                for item in value.get("tool_health") or ()
                if isinstance(item, Mapping)
            ),
            mcp_health=tuple(
                MCPHealthSnapshot.from_mapping(item)
                for item in value.get("mcp_health") or ()
                if isinstance(item, Mapping)
            ),
            recovery_hint=value.get("recovery_hint"),
            privacy_flags=value.get("privacy_flags") or (),
            degraded_reason=value.get("degraded_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "source": self.source,
            "status": self.status,
            "reason": self.reason,
            "workspace": self.workspace,
            "session_id": self.session_id,
            "last_activity_at": self.last_activity_at,
            "active_tool": self.active_tool.to_dict(),
            "tool_health": [item.to_dict() for item in self.tool_health],
            "mcp_health": [item.to_dict() for item in self.mcp_health],
            "recovery_hint": self.recovery_hint,
            "privacy_flags": list(self.privacy_flags),
            "degraded_reason": self.degraded_reason,
        }


@dataclass(frozen=True)
class FailureReviewEntry:
    """Structured failure review record for task.yaml or badcase capture."""

    trigger: str
    task_id: str
    what_happened: str
    why_it_failed: str
    what_changed: str
    how_it_was_verified: str
    added_eval_or_badcase: str
    blocker: bool = False

    def __post_init__(self) -> None:
        trigger = _normalize_choice(self.trigger, FAILURE_REVIEW_TRIGGERS)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "task_id", _safe_text(self.task_id) or "unknown")
        object.__setattr__(self, "what_happened", _safe_text(self.what_happened) or "unknown")
        object.__setattr__(self, "why_it_failed", _safe_text(self.why_it_failed) or "unknown")
        object.__setattr__(self, "what_changed", _safe_text(self.what_changed) or "unknown")
        object.__setattr__(
            self,
            "how_it_was_verified",
            _safe_text(self.how_it_was_verified) or "unknown",
        )
        object.__setattr__(
            self,
            "added_eval_or_badcase",
            _safe_text(self.added_eval_or_badcase) or "unknown",
        )
        object.__setattr__(
            self,
            "blocker",
            bool(self.blocker or trigger in BLOCKING_FAILURE_TRIGGERS),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "task_id": self.task_id,
            "what_happened": self.what_happened,
            "why_it_failed": self.why_it_failed,
            "what_changed": self.what_changed,
            "how_it_was_verified": self.how_it_was_verified,
            "added_eval_or_badcase": self.added_eval_or_badcase,
            "blocker": self.blocker,
        }


def _coerce_active_tool(value: Any) -> ActiveToolSnapshot:
    if isinstance(value, ActiveToolSnapshot):
        return value
    if isinstance(value, Mapping):
        return ActiveToolSnapshot.from_mapping(value)
    return ActiveToolSnapshot()


def _coerce_tool_health(value: Any) -> tuple[ToolHealthSnapshot, ...]:
    if value is None:
        return ()
    result: list[ToolHealthSnapshot] = []
    try:
        items = tuple(value)
    except TypeError:
        return ()
    for item in items:
        if isinstance(item, ToolHealthSnapshot):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(ToolHealthSnapshot.from_mapping(item))
    return tuple(result)


def _coerce_mcp_health(value: Any) -> tuple[MCPHealthSnapshot, ...]:
    if value is None:
        return ()
    result: list[MCPHealthSnapshot] = []
    try:
        items = tuple(value)
    except TypeError:
        return ()
    for item in items:
        if isinstance(item, MCPHealthSnapshot):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(MCPHealthSnapshot.from_mapping(item))
    return tuple(result)


def empty_run_snapshot(
    *,
    run_id: str = "unknown",
    source: str = "unknown",
    degraded_reason: str | None = None,
) -> RunSnapshot:
    """Return a valid unknown-state snapshot for missing or partial state."""
    return RunSnapshot(
        run_id=run_id,
        source=source,
        status="unknown",
        degraded_reason=degraded_reason,
        privacy_flags=("safe",),
    )


def summarize_private_payload(value: Any) -> dict[str, Any]:
    """Summarize a private payload without returning raw values."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, Mapping):
        keys = [key for key, _item in _safe_mapping_pairs(value)]
        return {
            "type": "object",
            "key_count": len(value),
            "keys": keys[:_PRIVATE_PAYLOAD_MAX_KEYS],
            "truncated": len(keys) > _PRIVATE_PAYLOAD_MAX_KEYS,
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return {
            "type": "array",
            "item_count": len(value),
        }
    if isinstance(value, str):
        return {
            "type": "string",
            "char_count": len(value),
        }
    return {
        "type": type(value).__name__,
    }


def summarize_tool_arguments(value: Any) -> dict[str, Any]:
    """Summarize tool arguments without returning raw argument values."""
    summary = summarize_private_payload(value)
    summary["privacy"] = "redacted"
    if isinstance(value, Mapping):
        pairs = _safe_mapping_pairs(value)
        summary["value_types"] = {
            key: _payload_type(item)
            for key, item in pairs[:_PRIVATE_PAYLOAD_MAX_KEYS]
        }
    elif isinstance(value, (list, tuple, set, frozenset)):
        summary["item_types"] = sorted({_payload_type(item) for item in value})
    return summary


def classify_snapshot_privacy(snapshot: RunSnapshot | Mapping[str, Any]) -> dict[str, str]:
    """Return privacy classification for every exposed snapshot field."""
    if isinstance(snapshot, RunSnapshot):
        payload = snapshot.to_dict()
    elif isinstance(snapshot, Mapping):
        payload = dict(snapshot)
    else:
        payload = {}
    return {
        str(key): SNAPSHOT_FIELD_PRIVACY.get(str(key), "unknown")
        for key in payload.keys()
    }


def build_failure_review_entry(
    *,
    trigger: str,
    task_id: str,
    what_happened: str,
    why_it_failed: str,
    what_changed: str,
    how_it_was_verified: str,
    added_eval_or_badcase: str,
    blocker: bool = False,
) -> FailureReviewEntry:
    """Create a redacted, blocker-aware failure review entry."""
    return FailureReviewEntry(
        trigger=trigger,
        task_id=task_id,
        what_happened=what_happened,
        why_it_failed=why_it_failed,
        what_changed=what_changed,
        how_it_was_verified=how_it_was_verified,
        added_eval_or_badcase=added_eval_or_badcase,
        blocker=blocker,
    )


def detect_repeated_unknown_state(
    snapshots: list[RunSnapshot] | tuple[RunSnapshot, ...],
    *,
    task_id: str = "HRI-06",
    threshold: int = 3,
) -> FailureReviewEntry | None:
    """Return a regression-capture entry when unknown states repeat."""
    counts: dict[str, int] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, RunSnapshot):
            continue
        if snapshot.status != "unknown":
            continue
        reason = snapshot.degraded_reason or "unknown"
        counts[reason] = counts.get(reason, 0) + 1

    if not counts:
        return None
    reason, count = max(counts.items(), key=lambda item: item[1])
    if count < threshold:
        return None

    return FailureReviewEntry(
        trigger="repeated_unknown_state",
        task_id=task_id,
        what_happened=f"{count} Run Inspector snapshots returned unknown with degraded_reason={reason}.",
        why_it_failed="The inspector could not classify available runtime state reliably.",
        what_changed="Capture this unknown-state pattern as a regression case or update .hermes/task.yaml before continuing.",
        how_it_was_verified="Detected by repeated unknown-state threshold.",
        added_eval_or_badcase=f"repeated_unknown_state:{reason}",
    )


def append_failure_review_entry(
    task_yaml_path: str | Path,
    entry: FailureReviewEntry,
) -> dict[str, Any]:
    """Append a failure review entry to a HERMES task.yaml file."""
    import yaml

    path = Path(task_yaml_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    failure_review = data.setdefault("failure_review", {})
    entries = failure_review.setdefault("entries", [])
    entries.append(entry.to_dict())
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return data


def run_snapshot_from_session_record(
    record: Mapping[str, Any] | None,
    *,
    now: float | None = None,
) -> RunSnapshot:
    """Build a snapshot from one SessionDB.list_sessions_rich row."""
    if not isinstance(record, Mapping):
        return empty_run_snapshot(degraded_reason="missing_session_record")

    session_id = _safe_text(record.get("id"))
    if not session_id:
        return empty_run_snapshot(degraded_reason="session_record_missing_id")

    status = _session_status(record, now=now)
    degraded_reason = _safe_text(record.get("degraded_reason"))
    if status == "unknown" and degraded_reason is None:
        degraded_reason = "session_state_unknown"

    return RunSnapshot(
        run_id=session_id,
        source=_session_source(record.get("source")),
        status=status,
        reason=record.get("end_reason"),
        session_id=session_id,
        last_activity_at=_unix_timestamp_to_iso(
            record.get("last_active", record.get("started_at"))
        ),
        recovery_hint=record.get("recovery_hint"),
        privacy_flags=("safe", "local_only"),
        degraded_reason=degraded_reason,
    )


def run_snapshot_from_gateway_runtime_status(
    record: Mapping[str, Any] | None,
) -> RunSnapshot:
    """Build a snapshot from gateway.status.read_runtime_status output."""
    if not isinstance(record, Mapping):
        return empty_run_snapshot(source="gateway", degraded_reason="missing_gateway_runtime_status")

    status = _gateway_status(record)
    degraded_reason = _safe_text(record.get("degraded_reason"))
    if status == "unknown" and degraded_reason is None:
        degraded_reason = "gateway_state_unknown"

    return RunSnapshot(
        run_id=_gateway_run_id(record),
        source="gateway",
        status=status,
        reason=record.get("exit_reason"),
        last_activity_at=record.get("updated_at"),
        recovery_hint=record.get("recovery_hint"),
        privacy_flags=("safe", "local_only"),
        degraded_reason=degraded_reason,
    )


def collect_latest_session_snapshot(
    *,
    session_db_factory: Any | None = None,
    now: float | None = None,
) -> RunSnapshot:
    """Read the latest known session without mutating session state."""
    if session_db_factory is None:
        from hermes_state import SessionDB

        session_db_factory = SessionDB

    db = None
    try:
        db = session_db_factory()
        rows = db.list_sessions_rich(limit=1, order_by_last_active=True)
    except Exception as exc:
        return empty_run_snapshot(
            degraded_reason=f"session_state_unavailable:{type(exc).__name__}"
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    if not rows:
        return empty_run_snapshot(degraded_reason="no_sessions_found")
    return run_snapshot_from_session_record(rows[0], now=now)


def collect_gateway_runtime_snapshot(
    *,
    runtime_status_reader: Any | None = None,
) -> RunSnapshot:
    """Read gateway runtime status without probing, starting, or stopping it."""
    if runtime_status_reader is None:
        from gateway.status import read_runtime_status

        runtime_status_reader = read_runtime_status

    try:
        record = runtime_status_reader()
    except Exception as exc:
        return empty_run_snapshot(
            source="gateway",
            degraded_reason=f"gateway_state_unavailable:{type(exc).__name__}",
        )
    return run_snapshot_from_gateway_runtime_status(record)


def summarize_tool_registry(registry_obj: Any) -> tuple[ToolHealthSnapshot, ...]:
    """Summarize ToolRegistry availability without dispatching any tools."""
    try:
        entries, toolset_checks = registry_obj._snapshot_state()
    except Exception as exc:
        return (
            ToolHealthSnapshot(
                status="unknown",
                reason=f"tool_registry_unavailable:{type(exc).__name__}",
            ),
        )

    toolset_status: dict[str, tuple[str, str | None]] = {}
    for toolset in sorted({getattr(entry, "toolset", None) for entry in entries}):
        if not toolset:
            continue
        check = toolset_checks.get(toolset)
        if check is None:
            toolset_status[toolset] = ("available", None)
            continue
        try:
            available = bool(check())
        except Exception as exc:
            toolset_status[toolset] = (
                "failed",
                f"check_failed:{type(exc).__name__}",
            )
        else:
            toolset_status[toolset] = (
                "available" if available else "unavailable",
                None if available else "check_returned_false",
            )

    return tuple(
        ToolHealthSnapshot(
            name=getattr(entry, "name", None),
            toolset=getattr(entry, "toolset", None),
            status=toolset_status.get(
                getattr(entry, "toolset", None),
                ("unknown", "toolset_state_unknown"),
            )[0],
            reason=toolset_status.get(
                getattr(entry, "toolset", None),
                ("unknown", "toolset_state_unknown"),
            )[1],
        )
        for entry in sorted(entries, key=lambda item: getattr(item, "name", ""))
    )


def summarize_mcp_servers(
    servers: Mapping[str, Any] | None,
    *,
    configured_servers: Mapping[str, Any] | None = None,
) -> tuple[MCPHealthSnapshot, ...]:
    """Summarize MCP server objects without connecting or refreshing them."""
    servers = servers or {}
    configured_servers = configured_servers or {}
    names = sorted({*servers.keys(), *configured_servers.keys()})
    result: list[MCPHealthSnapshot] = []

    for name in names:
        server = servers.get(name)
        configured = name in configured_servers
        if server is None:
            status = "unknown" if configured else "failed"
            result.append(MCPHealthSnapshot(
                name=name,
                status=status,
                last_error_class="not_connected" if configured else None,
                affected_tools=(),
            ))
            continue

        error = getattr(server, "_error", None)
        registered = tuple(getattr(server, "_registered_tool_names", ()) or ())
        session = getattr(server, "session", None)
        ready = getattr(server, "_ready", None)
        is_ready = bool(ready.is_set()) if hasattr(ready, "is_set") else False

        if error is not None:
            status = "failed"
            last_error_class = type(error).__name__
        elif session is not None:
            status = "connected"
            last_error_class = None
        elif is_ready:
            status = "degraded"
            last_error_class = "session_unavailable"
        else:
            status = "unknown"
            last_error_class = "not_ready"

        result.append(MCPHealthSnapshot(
            name=name,
            status=status,
            last_error_class=last_error_class,
            affected_tools=registered,
        ))

    return tuple(result)


def collect_tool_and_mcp_health(
    *,
    registry_obj: Any | None = None,
    mcp_servers: Mapping[str, Any] | None = None,
    configured_mcp_servers: Mapping[str, Any] | None = None,
) -> tuple[tuple[ToolHealthSnapshot, ...], tuple[MCPHealthSnapshot, ...]]:
    """Collect tool and MCP health with read-only in-memory inspection."""
    if registry_obj is None:
        from tools.registry import registry

        registry_obj = registry
    if mcp_servers is None:
        try:
            from tools import mcp_tool

            lock = getattr(mcp_tool, "_lock", None)
            if lock is not None:
                with lock:
                    mcp_servers = dict(getattr(mcp_tool, "_servers", {}))
            else:
                mcp_servers = dict(getattr(mcp_tool, "_servers", {}))
        except Exception:
            mcp_servers = {}

    return (
        summarize_tool_registry(registry_obj),
        summarize_mcp_servers(mcp_servers, configured_servers=configured_mcp_servers),
    )


def build_run_inspector_snapshot(
    *,
    session_snapshot: RunSnapshot | None = None,
    gateway_snapshot: RunSnapshot | None = None,
    tool_health: tuple[ToolHealthSnapshot, ...] | None = None,
    mcp_health: tuple[MCPHealthSnapshot, ...] | None = None,
    now: float | None = None,
) -> RunSnapshot:
    """Build the operator-facing run snapshot from read-only collectors."""
    if session_snapshot is None:
        session_snapshot = collect_latest_session_snapshot(now=now)
    if gateway_snapshot is None:
        gateway_snapshot = collect_gateway_runtime_snapshot()
    if tool_health is None or mcp_health is None:
        collected_tool_health, collected_mcp_health = collect_tool_and_mcp_health()
        if tool_health is None:
            tool_health = collected_tool_health
        if mcp_health is None:
            mcp_health = collected_mcp_health

    base = session_snapshot
    if (
        base.status == "unknown"
        and base.session_id is None
        and gateway_snapshot.status != "unknown"
    ):
        base = gateway_snapshot

    degraded_parts = [
        part
        for part in (
            base.degraded_reason,
            None if base is gateway_snapshot else gateway_snapshot.degraded_reason,
        )
        if part
    ]
    degraded_reason = "; ".join(degraded_parts) if degraded_parts else None

    return RunSnapshot(
        run_id=base.run_id,
        source=base.source,
        status=base.status,
        reason=base.reason,
        workspace=base.workspace,
        session_id=base.session_id,
        last_activity_at=base.last_activity_at,
        active_tool=base.active_tool,
        tool_health=tool_health or (),
        mcp_health=mcp_health or (),
        recovery_hint=base.recovery_hint,
        privacy_flags=("safe", "redacted", "local_only"),
        degraded_reason=degraded_reason,
    )
