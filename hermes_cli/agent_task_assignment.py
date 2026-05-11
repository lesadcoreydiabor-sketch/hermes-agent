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
TASK_STATUS_MAP = {
    "pending": "planned",
    "todo": "planned",
    "planned": "planned",
    "queued": "queued",
    "in_progress": "running",
    "in-progress": "running",
    "running": "running",
    "blocked": "blocked",
    "review": "review",
    "completed": "completed",
    "done": "completed",
    "failed": "failed",
}
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


def build_agent_task_assignments_from_task_contract(
    contract: Dict[str, Any],
) -> list[Dict[str, Any]]:
    """Build safe assignments from a .hermes/task.yaml-like contract dict."""

    if not isinstance(contract, dict):
        return []
    tasks = contract.get("tasks")
    if not isinstance(tasks, list):
        return []

    assignments = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id") or task.get("task_id")
        title = task.get("title") or task.get("description")
        if not task_id or not title:
            continue
        try:
            assignments.append(
                build_agent_task_assignment(
                    task_id,
                    title,
                    role=task.get("agent_role") or task.get("role") or "worker",
                    status=_task_status_to_assignment_status(task.get("status")),
                    dependencies={
                        "task_ids": task.get("depends_on") or task.get("dependencies") or [],
                        "required_artifacts": task.get("required_artifacts") or [],
                    },
                    write_scope=(
                        task.get("write_scope")
                        if isinstance(task.get("write_scope"), dict)
                        else {}
                    ),
                    allowed_tools=(
                        task.get("allowed_tools")
                        if isinstance(task.get("allowed_tools"), dict)
                        else {}
                    ),
                    delegate_limits=(
                        task.get("delegate_limits")
                        if isinstance(task.get("delegate_limits"), dict)
                        else {}
                    ),
                    verification=_verification_from_task(task),
                    handoff_payload={
                        "summary": task.get("description"),
                        "changed_files": task.get("changed_files") or [],
                        "verification_result": task.get("verification_result"),
                        "blockers": task.get("blockers") or [],
                        "next_step": task.get("next_step"),
                    },
                    conflict_policy=(
                        task.get("conflict_policy")
                        if isinstance(task.get("conflict_policy"), dict)
                        else {}
                    ),
                    privacy_class=task.get("privacy_class"),
                )
            )
        except (TypeError, ValueError):
            continue
    return assignments


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


def summarize_agent_handoff_protocol(
    assignments: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize handoff readiness and conflict policy gates."""

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

    conflict_pairs = find_agent_task_assignment_conflicts(normalized)
    conflict_task_id_list = _dedupe(
        task_id
        for conflict in conflict_pairs
        for task_id in conflict.get("task_ids", [])
    )
    conflict_task_ids = set(conflict_task_id_list)
    policy_counts = Counter(
        item["conflict_policy"]["conflict_resolution"] for item in normalized
    )

    handoff_task_ids = []
    ready_task_ids = []
    blocked_task_ids = []
    verification_missing_task_ids = []
    reviewer_required_task_ids = []
    human_decision_task_ids = []

    for item in normalized:
        task_id = item["task_id"]
        status = item["status"]
        handoff = item["handoff_payload"]
        verification = item["verification"]
        conflict_policy = item["conflict_policy"]
        write_scope = item["write_scope"]
        blockers = handoff["blockers"]
        is_handoff_candidate = status in {"review", "completed"} or bool(blockers)

        if is_handoff_candidate:
            handoff_task_ids.append(task_id)
        if blockers or status in {"blocked", "failed"}:
            blocked_task_ids.append(task_id)
        if (
            is_handoff_candidate
            and status not in {"blocked", "failed"}
            and verification["required_before_handoff"]
            and not handoff["verification_result"]
        ):
            verification_missing_task_ids.append(task_id)
        if conflict_policy["shared_contract_requires_reviewer"] and (
            write_scope["shared_contracts"] or task_id in conflict_task_ids
        ):
            reviewer_required_task_ids.append(task_id)
        if (
            conflict_policy["conflict_resolution"] == "human_decides"
            and task_id in conflict_task_ids
        ):
            human_decision_task_ids.append(task_id)

        if (
            is_handoff_candidate
            and task_id not in blocked_task_ids
            and task_id not in verification_missing_task_ids
            and task_id not in reviewer_required_task_ids
            and task_id not in human_decision_task_ids
        ):
            ready_task_ids.append(task_id)

    status = "empty"
    if normalized:
        status = "quiet"
    if ready_task_ids:
        status = "ready"
    if reviewer_required_task_ids:
        status = "needs_review"
    if verification_missing_task_ids:
        status = "needs_verification"
    if blocked_task_ids or human_decision_task_ids:
        status = "blocked"
    if invalid_count and not normalized:
        status = "degraded"

    return {
        "schema_version": AGENT_TASK_ASSIGNMENT_SCHEMA_VERSION,
        "status": status,
        "handoff_task_ids": handoff_task_ids[:LIST_LIMIT],
        "ready_task_ids": ready_task_ids[:LIST_LIMIT],
        "blocked_task_ids": _dedupe(blocked_task_ids)[:LIST_LIMIT],
        "verification_missing_task_ids": _dedupe(verification_missing_task_ids)[
            :LIST_LIMIT
        ],
        "reviewer_required_task_ids": _dedupe(reviewer_required_task_ids)[:LIST_LIMIT],
        "human_decision_task_ids": _dedupe(human_decision_task_ids)[:LIST_LIMIT],
        "conflict_task_ids": conflict_task_id_list[:LIST_LIMIT],
        "policy_counts": _counter_payload(policy_counts, CONFLICT_RESOLUTIONS),
        "degraded_reason": f"invalid_assignments:{invalid_count}" if invalid_count else None,
        "privacy_class": AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
    }


def plan_agent_assignment_batches(
    assignments: Iterable[Dict[str, Any]],
    *,
    max_parallel_workers: Any = None,
) -> Dict[str, Any]:
    """Build dependency-aware, write-scope-safe parallel assignment batches."""

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
    satisfied_task_ids = {
        item["task_id"] for item in normalized if item["status"] == "completed"
    }
    candidates = {
        item["task_id"]: item
        for item in normalized
        if item["status"] in {"planned", "queued"}
        and item["role"] not in {"observer", "reviewer"}
    }
    blocked_task_ids = [
        item["task_id"]
        for item in normalized
        if item["status"] in {"blocked", "failed", "review"}
    ]
    active_task_ids = [
        item["task_id"] for item in normalized if item["status"] == "running"
    ]
    missing_dependency_task_ids = [
        item["task_id"]
        for item in candidates.values()
        if any(dep not in known_task_ids for dep in item["dependencies"]["task_ids"])
    ]
    pending = {
        task_id: item
        for task_id, item in candidates.items()
        if task_id not in missing_dependency_task_ids
    }
    limit = _parallel_limit(max_parallel_workers, pending.values())

    batches = []
    while pending:
        ready = [
            item
            for item in pending.values()
            if set(item["dependencies"]["task_ids"]).issubset(satisfied_task_ids)
        ]
        if not ready:
            break
        batch = _next_parallel_batch(ready, limit)
        if not batch:
            break
        batch_task_ids = [item["task_id"] for item in batch]
        batches.append(
            {
                "index": len(batches) + 1,
                "task_ids": batch_task_ids,
                "roles": _counter_payload(Counter(item["role"] for item in batch), ROLES),
                "privacy_class": AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
            }
        )
        for task_id in batch_task_ids:
            pending.pop(task_id, None)
            satisfied_task_ids.add(task_id)

    waiting_task_ids = sorted(set(pending) | set(missing_dependency_task_ids))[:LIST_LIMIT]
    conflict_pairs = find_agent_task_assignment_conflicts(normalized)
    conflict_task_ids = _dedupe(
        task_id for conflict in conflict_pairs for task_id in conflict.get("task_ids", [])
    )[:LIST_LIMIT]

    status = "empty"
    if normalized:
        status = "ready"
    if active_task_ids:
        status = "active"
    if blocked_task_ids or waiting_task_ids:
        status = "blocked"
    if conflict_task_ids:
        status = "sequenced_conflicts"
    if not pending and not candidates and normalized and not active_task_ids and not blocked_task_ids:
        status = "complete"
    if invalid_count:
        status = "degraded" if status in {"empty", "complete"} else status

    degraded_reasons = []
    if invalid_count:
        degraded_reasons.append(f"invalid_assignments:{invalid_count}")
    if waiting_task_ids:
        degraded_reasons.append("dependency_waiting")

    return {
        "schema_version": AGENT_TASK_ASSIGNMENT_SCHEMA_VERSION,
        "status": status,
        "max_parallel_workers": limit,
        "batches": batches,
        "blocked_task_ids": blocked_task_ids[:LIST_LIMIT],
        "active_task_ids": active_task_ids[:LIST_LIMIT],
        "waiting_task_ids": waiting_task_ids,
        "conflict_task_ids": conflict_task_ids,
        "conflicts": conflict_pairs[:LIST_LIMIT],
        "degraded_reason": _join_reasons(degraded_reasons),
        "privacy_class": AGENT_TASK_ASSIGNMENT_PRIVACY_CLASS,
    }


def _safe_owner(value: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "agent_id": _safe_identifier(value.get("agent_id")),
        "parent_agent_id": _safe_identifier(value.get("parent_agent_id")),
        "human_owner": _safe_identifier(value.get("human_owner")),
    }


def _verification_from_task(task: Dict[str, Any]) -> Dict[str, Any]:
    verify = task.get("verify")
    if isinstance(verify, list) and verify:
        command = verify[0]
    elif isinstance(verify, str):
        command = verify
    else:
        command = ""
    return {
        "command": command,
        "expected_signal": "verification pass" if command else "",
        "required_before_handoff": True,
    }


def _task_status_to_assignment_status(value: Any) -> str:
    status = _safe_status(value)
    if not status:
        return "planned"
    return TASK_STATUS_MAP.get(status, _safe_choice(status, STATUSES, "planned"))


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


def _next_parallel_batch(assignments: list[Dict[str, Any]], limit: int) -> list[Dict[str, Any]]:
    batch: list[Dict[str, Any]] = []
    for item in sorted(assignments, key=lambda value: value["task_id"]):
        if len(batch) >= limit:
            break
        if any(_write_scope_overlap(item["write_scope"], other["write_scope"]) for other in batch):
            continue
        batch.append(item)
    return batch


def _parallel_limit(value: Any, assignments: Iterable[Dict[str, Any]]) -> int:
    explicit = _safe_optional_int(value, minimum=1, maximum=LIST_LIMIT)
    if explicit:
        return explicit
    limits = [
        item["delegate_limits"]["max_parallel_workers"]
        for item in assignments
        if item["delegate_limits"].get("max_parallel_workers")
    ]
    if limits:
        return max(1, min(LIST_LIMIT, min(limits)))
    return LIST_LIMIT


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


def _join_reasons(reasons: Iterable[Any]) -> Optional[str]:
    safe_reasons = []
    for reason in reasons:
        safe = _safe_identifier(reason)
        if safe and safe not in safe_reasons:
            safe_reasons.append(safe)
    if not safe_reasons:
        return None
    return ";".join(safe_reasons[:LIST_LIMIT])


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
