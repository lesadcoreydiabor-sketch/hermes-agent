"""Privacy-safe agent task assignment and handoff helpers.

These helpers normalize the agent-ready task ownership template from the
Multi-Agent Memory PRD. They are pure: no scheduling, delegation, file writes,
memory mutations, config changes, or remote calls happen here.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, Optional


AGENT_TASK_ASSIGNMENT_SCHEMA_VERSION = 1
AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS = "redacted_summary"

SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96
LIST_LIMIT = 16

ROLES = frozenset({"planner", "orchestrator", "worker", "reviewer", "observer"})
STATUSES = frozenset(
    {"planned", "queued", "running", "blocked", "review", "completed", "failed"}
)
ACTIVE_STATUSES = frozenset({"planned", "queued", "running", "blocked", "review"})
INTERRUPT_POLICIES = frozenset({"cooperative", "parent_owned", "manual_review"})
CONFLICT_RESOLUTIONS = frozenset(
    {"pause_and_handoff", "reviewer_decides", "human_decides"}
)
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


def build_agent_task_assignment(
    task_id: Any,
    title: Any,
    *,
    role: Any = "worker",
    owner: Optional[Dict[str, Any]] = None,
    status: Any = "planned",
    dependencies: Optional[Dict[str, Any]] = None,
    write_scope: Optional[Dict[str, Any]] = None,
    allowed_tools: Optional[Dict[str, Any]] = None,
    delegate_limits: Optional[Dict[str, Any]] = None,
    verification: Optional[Dict[str, Any]] = None,
    handoff_payload: Optional[Dict[str, Any]] = None,
    conflict_policy: Optional[Dict[str, Any]] = None,
    privacy_class: Any = AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
) -> Dict[str, Any]:
    """Build one normalized, redacted agent-ready task assignment."""

    safe_task_id = _safe_identifier(task_id)
    if not safe_task_id:
        raise ValueError("task_id is required")

    safe_title = _safe_summary(title, fallback=None)
    if not safe_title:
        raise ValueError("title is required")

    safe_role = _safe_choice(role, ROLES, "worker")
    safe_status = _safe_choice(status, STATUSES, "planned")

    return {
        "schema_version": AGENT_TASK_ASSIGNMENT_SCHEMA_VERSION,
        "task_id": safe_task_id,
        "title": safe_title,
        "role": safe_role,
        "owner": _safe_owner(owner or {}),
        "status": safe_status,
        "dependencies": _safe_dependencies(dependencies or {}),
        "write_scope": _safe_write_scope(write_scope or {}),
        "allowed_tools": _safe_allowed_tools(allowed_tools or {}),
        "delegate_limits": _safe_delegate_limits(delegate_limits or {}),
        "verification": _safe_verification(verification or {}),
        "handoff_payload": _safe_handoff_payload(handoff_payload or {}),
        "conflict_policy": _safe_conflict_policy(conflict_policy or {}),
        "privacy_class": _safe_privacy_class(privacy_class),
    }


def normalize_agent_task_assignment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an existing dict into the agent task assignment schema."""

    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    return build_agent_task_assignment(
        payload.get("task_id"),
        payload.get("title"),
        role=payload.get("role"),
        owner=payload.get("owner") if isinstance(payload.get("owner"), dict) else {},
        status=payload.get("status"),
        dependencies=(
            payload.get("dependencies")
            if isinstance(payload.get("dependencies"), dict)
            else {}
        ),
        write_scope=(
            payload.get("write_scope") if isinstance(payload.get("write_scope"), dict) else {}
        ),
        allowed_tools=(
            payload.get("allowed_tools")
            if isinstance(payload.get("allowed_tools"), dict)
            else {}
        ),
        delegate_limits=(
            payload.get("delegate_limits")
            if isinstance(payload.get("delegate_limits"), dict)
            else {}
        ),
        verification=(
            payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
        ),
        handoff_payload=(
            payload.get("handoff_payload")
            if isinstance(payload.get("handoff_payload"), dict)
            else {}
        ),
        conflict_policy=(
            payload.get("conflict_policy")
            if isinstance(payload.get("conflict_policy"), dict)
            else {}
        ),
        privacy_class=payload.get("privacy_class"),
    )


def find_agent_task_assignment_conflicts(
    assignments: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Return direct write-scope conflicts among parallel active assignments."""

    normalized = []
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        try:
            item = normalize_agent_task_assignment(assignment)
        except (TypeError, ValueError):
            continue
        if item["status"] not in ACTIVE_STATUSES:
            continue
        if item["role"] in {"observer", "reviewer"}:
            continue
        normalized.append(item)

    conflicts: list[Dict[str, Any]] = []
    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            if _has_dependency_edge(left, right):
                continue
            overlap = _write_scope_overlap(left["write_scope"], right["write_scope"])
            if not overlap:
                continue
            conflicts.append(
                {
                    "task_ids": [left["task_id"], right["task_id"]],
                    "overlap": overlap,
                    "resolution": left["conflict_policy"]["conflict_resolution"],
                    "privacy_class": AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
                }
            )
    return conflicts


def summarize_agent_task_assignments(
    assignments: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize assignment health for read-only operator surfaces."""

    normalized = []
    invalid_count = 0
    for assignment in assignments:
        if not isinstance(assignment, dict):
            invalid_count += 1
            continue
        try:
            normalized.append(normalize_agent_task_assignment(assignment))
        except (TypeError, ValueError):
            invalid_count += 1

    known_task_ids = {item["task_id"] for item in normalized}
    completed_task_ids = {
        item["task_id"] for item in normalized if item["status"] == "completed"
    }
    role_counts = Counter(item["role"] for item in normalized)
    status_counts = Counter(item["status"] for item in normalized)
    conflicts = find_agent_task_assignment_conflicts(normalized)

    ready_task_ids = []
    dependency_waiting_task_ids = []
    blocked_task_ids = []
    for item in normalized:
        task_id = item["task_id"]
        status = item["status"]
        dependencies = item["dependencies"]["task_ids"]
        missing_dependencies = [dep for dep in dependencies if dep not in known_task_ids]
        unmet_dependencies = [
            dep
            for dep in dependencies
            if dep in known_task_ids and dep not in completed_task_ids
        ]
        if status == "blocked":
            blocked_task_ids.append(task_id)
        if status in {"planned", "queued"}:
            if missing_dependencies or unmet_dependencies:
                dependency_waiting_task_ids.append(task_id)
            else:
                ready_task_ids.append(task_id)

    status = "empty"
    if normalized:
        status = "active"
    if dependency_waiting_task_ids or blocked_task_ids:
        status = "blocked"
    if conflicts:
        status = "conflict"
    if normalized and len(completed_task_ids) == len(normalized):
        status = "completed"

    return {
        "schema_version": AGENT_TASK_ASSIGNMENT_SCHEMA_VERSION,
        "status": status,
        "total_count": len(normalized),
        "active_count": sum(
            1 for item in normalized if item["status"] in ACTIVE_STATUSES
        ),
        "completed_count": len(completed_task_ids),
        "failed_count": status_counts.get("failed", 0),
        "blocked_count": len(blocked_task_ids),
        "ready_task_ids": ready_task_ids[:LIST_LIMIT],
        "dependency_waiting_task_ids": dependency_waiting_task_ids[:LIST_LIMIT],
        "blocked_task_ids": blocked_task_ids[:LIST_LIMIT],
        "role_counts": _counter_payload(role_counts, ROLES),
        "status_counts": _counter_payload(status_counts, STATUSES),
        "conflicts": conflicts[:LIST_LIMIT],
        "degraded_reason": f"invalid_assignments:{invalid_count}" if invalid_count else None,
        "privacy_class": AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
    }


def _safe_owner(value: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "agent_id": _safe_identifier(value.get("agent_id")),
        "parent_agent_id": _safe_identifier(value.get("parent_agent_id")),
        "human_owner": _safe_identifier(value.get("human_owner")),
    }


def _counter_payload(counter: Counter[str], allowed: frozenset[str]) -> Dict[str, int]:
    return {key: counter.get(key, 0) for key in sorted(allowed)}


def _safe_dependencies(value: Dict[str, Any]) -> Dict[str, list[str]]:
    return {
        "task_ids": _safe_identifier_list(value.get("task_ids") or []),
        "required_artifacts": _safe_summary_list(value.get("required_artifacts") or []),
    }


def _safe_write_scope(value: Dict[str, Any]) -> Dict[str, list[str]]:
    return {
        "files": _safe_path_list(value.get("files") or []),
        "directories": _safe_path_list(value.get("directories") or []),
        "forbidden_paths": _safe_path_list(value.get("forbidden_paths") or []),
        "shared_contracts": _safe_path_list(value.get("shared_contracts") or []),
    }


def _safe_allowed_tools(value: Dict[str, Any]) -> Dict[str, list[str]]:
    return {
        "toolsets": _safe_identifier_list(value.get("toolsets") or []),
        "commands": _safe_summary_list(value.get("commands") or []),
        "disallowed": _safe_identifier_list(value.get("disallowed") or []),
    }


def _safe_delegate_limits(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "max_depth": _safe_optional_int(value.get("max_depth"), minimum=0, maximum=32),
        "max_parallel_workers": _safe_optional_int(
            value.get("max_parallel_workers"), minimum=0, maximum=64
        ),
        "interrupt_policy": _safe_choice(
            value.get("interrupt_policy"), INTERRUPT_POLICIES, "cooperative"
        ),
    }


def _safe_verification(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "command": _safe_summary(value.get("command"), fallback=""),
        "expected_signal": _safe_summary(value.get("expected_signal"), fallback=""),
        "required_before_handoff": bool(value.get("required_before_handoff", True)),
    }


def _safe_handoff_payload(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "summary": _safe_summary(value.get("summary"), fallback=""),
        "changed_files": _safe_path_list(value.get("changed_files") or []),
        "verification_result": _safe_summary(value.get("verification_result"), fallback=None),
        "blockers": _safe_summary_list(value.get("blockers") or []),
        "next_step": _safe_summary(value.get("next_step"), fallback=""),
        "privacy_class": _safe_privacy_class(value.get("privacy_class")),
    }


def _safe_conflict_policy(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "write_scope_must_be_disjoint": bool(
            value.get("write_scope_must_be_disjoint", True)
        ),
        "shared_contract_requires_reviewer": bool(
            value.get("shared_contract_requires_reviewer", True)
        ),
        "conflict_resolution": _safe_choice(
            value.get("conflict_resolution"),
            CONFLICT_RESOLUTIONS,
            "pause_and_handoff",
        ),
    }


def _write_scope_overlap(left: Dict[str, list[str]], right: Dict[str, list[str]]) -> list[str]:
    left_files = set(left.get("files") or [])
    right_files = set(right.get("files") or [])
    left_dirs = set(left.get("directories") or [])
    right_dirs = set(right.get("directories") or [])
    overlap = sorted((left_files & right_files) | (left_dirs & right_dirs))

    for file_path in left_files:
        for directory in right_dirs:
            if _path_is_under(file_path, directory):
                overlap.append(file_path)
    for file_path in right_files:
        for directory in left_dirs:
            if _path_is_under(file_path, directory):
                overlap.append(file_path)

    return _dedupe(overlap)[:LIST_LIMIT]


def _path_is_under(path: str, directory: str) -> bool:
    clean_path = path.replace("\\", "/").rstrip("/")
    clean_dir = directory.replace("\\", "/").rstrip("/")
    return clean_path == clean_dir or clean_path.startswith(f"{clean_dir}/")


def _has_dependency_edge(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_deps = set(left["dependencies"]["task_ids"])
    right_deps = set(right["dependencies"]["task_ids"])
    return right["task_id"] in left_deps or left["task_id"] in right_deps


def _safe_identifier_list(values: Iterable[Any]) -> list[str]:
    safe_values = []
    for value in values:
        safe = _safe_identifier(value)
        if safe and safe not in safe_values:
            safe_values.append(safe)
        if len(safe_values) >= LIST_LIMIT:
            break
    return safe_values


def _safe_summary_list(values: Iterable[Any]) -> list[str]:
    safe_values = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in safe_values:
            safe_values.append(safe)
        if len(safe_values) >= LIST_LIMIT:
            break
    return safe_values


def _safe_path_list(values: Iterable[Any]) -> list[str]:
    safe_values = []
    for value in values:
        safe = _safe_path(value)
        if safe and safe not in safe_values:
            safe_values.append(safe)
        if len(safe_values) >= LIST_LIMIT:
            break
    return safe_values


def _safe_path(value: Any) -> Optional[str]:
    text = _safe_summary(value, fallback=None)
    if text is None:
        return None
    if text == "Redacted":
        return text
    cleaned = text.replace("\\", "/").strip().lstrip("./")
    cleaned = _SAFE_LABEL_RE.sub("_", cleaned)
    if not cleaned:
        return None
    if len(cleaned) > SUMMARY_LIMIT:
        return cleaned[: SUMMARY_LIMIT - 3] + "..."
    return cleaned


def _safe_choice(value: Any, allowed: frozenset[str], fallback: str) -> str:
    text = _safe_status(value)
    if text in allowed:
        return text
    return fallback


def _safe_optional_int(value: Any, *, minimum: int, maximum: int) -> Optional[int]:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(number, maximum))


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


def _safe_status(value: Any) -> Optional[str]:
    text = _safe_identifier(value)
    return text.lower() if text else None


def _safe_privacy_class(value: Any) -> str:
    text = _safe_status(value)
    if text in ALLOWED_PRIVACY_CLASSES:
        return text
    return AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
