"""Reviewable failure-review and long-term queue candidate helpers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from hermes_cli.learning_journal import build_long_term_queue_entry


FAILURE_CANDIDATE_SCHEMA_VERSION = 1
FAILURE_CANDIDATE_PRIVACY_CLASS = "redacted_summary"

SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96
EVIDENCE_LIMIT = 8

TRIGGER_CATEGORIES = {
    "failed_verification": "missing_test",
    "repeated_tool_error": "recurring_failure",
    "repeated_runtime_error": "recurring_failure",
    "repeated_unknown_state": "recovery_pattern",
    "redaction_failure": "code_issue",
}
BLOCKER_TRIGGERS = frozenset({"redaction_failure", "blocked_task"})

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


def build_failure_review_candidate(
    trigger: Any,
    *,
    candidate_id: Any = None,
    timestamp: Optional[str] = None,
    task_id: Any = None,
    tool_name: Any = None,
    error_type: Any = None,
    what_happened: Any = None,
    likely_cause: Any = None,
    verification_command: Any = None,
    proposed_badcase: Any = None,
    evidence: Optional[Iterable[Any]] = None,
    blocker: Optional[bool] = None,
    dedupe_key: Any = None,
    occurrence_count: Any = 1,
) -> Dict[str, Any]:
    """Build one redacted, reviewable failure candidate."""

    safe_trigger = _safe_trigger(trigger)
    if not safe_trigger:
        raise ValueError("trigger is required")

    safe_task_id = _safe_identifier(task_id)
    safe_tool_name = _safe_identifier(tool_name)
    safe_error_type = _safe_identifier(error_type)
    happened = _safe_summary(what_happened, fallback=_default_happened(safe_trigger))
    cause = _safe_summary(likely_cause, fallback="Needs review")
    command = _safe_summary(verification_command, fallback=None)
    badcase = _safe_summary(proposed_badcase, fallback=_default_badcase(safe_trigger))
    safe_evidence = _safe_evidence(evidence or [])
    count = _safe_occurrence_count(occurrence_count)
    is_blocker = bool(blocker) or safe_trigger in BLOCKER_TRIGGERS
    safe_dedupe_key = _safe_identifier(dedupe_key) or _default_dedupe_key(
        safe_trigger,
        safe_task_id,
        safe_tool_name,
        safe_error_type,
        command,
    )

    queue_entry = build_long_term_queue_entry(
        TRIGGER_CATEGORIES.get(safe_trigger, "code_issue"),
        entry_id=f"queue-{safe_dedupe_key}" if safe_dedupe_key else None,
        timestamp=timestamp,
        state="needs_evidence" if is_blocker else "candidate",
        title=_candidate_title(safe_trigger, safe_task_id, safe_tool_name),
        source_task_id=safe_task_id,
        source_event_id=_safe_identifier(candidate_id),
        evidence=[
            f"trigger={safe_trigger}",
            f"occurrences={count}",
            happened,
            cause,
            *(safe_evidence[:EVIDENCE_LIMIT]),
        ],
        proposed_change=badcase,
        acceptance_criteria=_acceptance_criteria(safe_trigger, command, badcase),
        dedupe_key=safe_dedupe_key,
    )

    return {
        "schema_version": FAILURE_CANDIDATE_SCHEMA_VERSION,
        "candidate_id": _safe_identifier(candidate_id) or _new_candidate_id(),
        "timestamp": timestamp or _utc_now_iso(),
        "trigger": safe_trigger,
        "task_id": safe_task_id,
        "tool_name": safe_tool_name,
        "error_type": safe_error_type,
        "what_happened": happened,
        "likely_cause": cause,
        "verification_command": command,
        "proposed_badcase": badcase,
        "evidence": safe_evidence,
        "blocker": is_blocker,
        "dedupe_key": safe_dedupe_key,
        "occurrence_count": count,
        "queue_entry": queue_entry,
        "privacy_class": FAILURE_CANDIDATE_PRIVACY_CLASS,
    }


def build_failure_review_candidates(
    events: Iterable[Dict[str, Any]],
    *,
    timestamp: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """Build and dedupe candidates from raw safe-ish failure events."""

    candidates = []
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            candidates.append(
                build_failure_review_candidate(
                    event.get("trigger"),
                    candidate_id=event.get("candidate_id"),
                    timestamp=event.get("timestamp") or timestamp,
                    task_id=event.get("task_id"),
                    tool_name=event.get("tool_name"),
                    error_type=event.get("error_type"),
                    what_happened=event.get("what_happened"),
                    likely_cause=event.get("likely_cause"),
                    verification_command=event.get("verification_command"),
                    proposed_badcase=event.get("proposed_badcase"),
                    evidence=event.get("evidence") if isinstance(event.get("evidence"), list) else [],
                    blocker=event.get("blocker") if isinstance(event.get("blocker"), bool) else None,
                    dedupe_key=event.get("dedupe_key"),
                    occurrence_count=event.get("occurrence_count", 1),
                )
            )
        except ValueError:
            continue
    return dedupe_failure_review_candidates(candidates)


def dedupe_failure_review_candidates(
    candidates: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Merge repeated candidates by safe dedupe key."""

    merged: dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        key = _safe_identifier(candidate.get("dedupe_key")) or _safe_identifier(
            candidate.get("candidate_id")
        )
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(candidate)
            merged[key]["evidence"] = list(candidate.get("evidence") or [])[:EVIDENCE_LIMIT]
            continue
        existing = merged[key]
        existing["occurrence_count"] = _safe_occurrence_count(
            existing.get("occurrence_count", 1)
        ) + _safe_occurrence_count(candidate.get("occurrence_count", 1))
        existing["blocker"] = bool(existing.get("blocker")) or bool(candidate.get("blocker"))
        existing["evidence"] = _merge_evidence(
            existing.get("evidence") or [],
            candidate.get("evidence") or [],
        )
        existing["queue_entry"] = _with_occurrence_evidence(
            existing["queue_entry"],
            existing["occurrence_count"],
        )
    return list(merged.values())


def _with_occurrence_evidence(
    queue_entry: Dict[str, Any],
    occurrence_count: int,
) -> Dict[str, Any]:
    updated = dict(queue_entry)
    evidence = [
        value
        for value in updated.get("evidence", [])
        if not str(value).startswith("occurrences=")
    ]
    updated["evidence"] = [f"occurrences={occurrence_count}", *evidence][:EVIDENCE_LIMIT]
    return updated


def _merge_evidence(left: Iterable[Any], right: Iterable[Any]) -> list[str]:
    merged = []
    for value in [*left, *right]:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in merged:
            merged.append(safe)
        if len(merged) >= EVIDENCE_LIMIT:
            break
    return merged


def _acceptance_criteria(
    trigger: str,
    command: Optional[str],
    badcase: str,
) -> list[str]:
    criteria = [
        "Candidate is reviewed before any durable change",
        "Safe summary contains no prompts, logs, diffs, paths, or secrets",
    ]
    if command:
        criteria.append(f"Verification command covered: {command}")
    if trigger == "redaction_failure":
        criteria.append("Redaction regression blocks promotion until covered")
    if badcase:
        criteria.append(f"Badcase proposed: {badcase}")
    return criteria[:EVIDENCE_LIMIT]


def _candidate_title(
    trigger: str,
    task_id: Optional[str],
    tool_name: Optional[str],
) -> str:
    if trigger == "failed_verification":
        return f"Failed verification for {task_id or 'unknown task'}"
    if trigger in {"repeated_tool_error", "repeated_runtime_error"}:
        return f"Repeated runtime error in {tool_name or 'unknown tool'}"
    if trigger == "repeated_unknown_state":
        return "Repeated unknown run state"
    if trigger == "redaction_failure":
        return "Redaction failure requires blocker review"
    return trigger.replace("_", " ")


def _default_happened(trigger: str) -> str:
    if trigger == "failed_verification":
        return "Verification failed"
    if trigger == "redaction_failure":
        return "Sensitive content reached a safe-summary boundary"
    if trigger == "repeated_unknown_state":
        return "Run Inspector reported repeated unknown state"
    return "Runtime error repeated"


def _default_badcase(trigger: str) -> str:
    if trigger == "redaction_failure":
        return "Add a redaction regression before promotion"
    if trigger == "failed_verification":
        return "Add or update a failing verification regression"
    return "Add a regression or diagnostic for this repeated failure"


def _default_dedupe_key(
    trigger: str,
    task_id: Optional[str],
    tool_name: Optional[str],
    error_type: Optional[str],
    command: Optional[str],
) -> str:
    parts = [trigger, task_id, tool_name, error_type, command]
    text = ":".join(part for part in parts if part)
    return _safe_identifier(text) or trigger


def _safe_evidence(values: Iterable[Any]) -> list[str]:
    evidence = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in evidence:
            evidence.append(safe)
        if len(evidence) >= EVIDENCE_LIMIT:
            break
    return evidence


def _safe_trigger(value: Any) -> Optional[str]:
    trigger = _safe_status(value)
    if not trigger:
        return None
    return trigger


def _safe_occurrence_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(count, 1000))


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


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _new_candidate_id() -> str:
    return f"failure-{uuid.uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
