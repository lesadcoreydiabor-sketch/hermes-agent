"""Review-gated learning queue and skills journal helpers.

The helpers in this module normalize local, privacy-safe records only. They do
not edit SKILL.md files, prompts, config, memory providers, or runtime state.
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


LEARNING_SCHEMA_VERSION = 1
LEARNING_PRIVACY_CLASS = "redacted_summary"

LONG_TERM_QUEUE_PATH = Path(".hermes") / "long_term_queue.jsonl"
SKILLS_JOURNAL_PATH = Path(".hermes") / "skills_journal.jsonl"

SUMMARY_LIMIT = 240
ID_LIMIT = 96
LABEL_LIMIT = 96
LIST_LIMIT = 8

ALLOWED_PRIVACY_CLASSES = frozenset(
    {"safe", "redacted_summary", "local_only", "omitted"}
)
QUEUE_STATES = frozenset(
    {"candidate", "needs_evidence", "accepted", "rejected", "applied", "superseded"}
)
QUEUE_CATEGORIES = frozenset(
    {
        "recurring_failure",
        "missing_test",
        "recovery_pattern",
        "skill_improvement",
        "documentation_gap",
        "product_requirement",
        "code_issue",
    }
)
TARGET_TYPES = frozenset(
    {
        "memory_fact",
        "regression_test",
        "documentation_update",
        "skill_update",
        "product_requirement",
        "code_issue",
    }
)
TARGET_REQUIRED_STATES = frozenset({"accepted", "applied"})
REVIEW_ACTIONS = frozenset(
    {
        "promote_queue_to_skills_journal",
        "mark_badcase_covered",
        "export_failure_review_summary",
    }
)
REVIEW_ACTION_TARGET_TYPES = {
    "promote_queue_to_skills_journal": "skill_update",
    "mark_badcase_covered": "regression_test",
    "export_failure_review_summary": "documentation_update",
}
REVIEW_ACTION_EFFECTS = {
    "promote_queue_to_skills_journal": "append_skills_journal_after_review",
    "mark_badcase_covered": "record_badcase_coverage_after_review",
    "export_failure_review_summary": "export_safe_summary_after_review",
}
REVIEW_BLOCKED_EFFECTS = (
    "edit_skill_files",
    "write_memory_provider_data",
    "mutate_config",
    "mutate_task_yaml",
    "dispatch_tools_without_review",
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


def default_long_term_queue_path(root: str | Path = ".") -> Path:
    """Return the default workspace-local long-term queue path."""

    return Path(root) / LONG_TERM_QUEUE_PATH


def default_skills_journal_path(root: str | Path = ".") -> Path:
    """Return the default workspace-local skills journal path."""

    return Path(root) / SKILLS_JOURNAL_PATH


def build_long_term_queue_entry(
    category: Any,
    *,
    entry_id: Any = None,
    timestamp: Optional[str] = None,
    state: Any = "candidate",
    title: Any = None,
    source_task_id: Any = None,
    source_event_id: Any = None,
    evidence: Optional[Iterable[Any]] = None,
    proposed_change: Any = None,
    acceptance_criteria: Optional[Iterable[Any]] = None,
    target_type: Any = None,
    target_ref: Any = None,
    dedupe_key: Any = None,
    privacy_class: Any = LEARNING_PRIVACY_CLASS,
) -> Dict[str, Any]:
    """Build one normalized long-term queue entry."""

    safe_category = _safe_category(category)
    if not safe_category:
        raise ValueError("category is required")

    safe_state = _safe_queue_state(state)
    safe_target_type = _safe_target_type(target_type)
    safe_target_ref = _safe_summary(target_ref, fallback=None)
    if safe_state in TARGET_REQUIRED_STATES and (
        not safe_target_type or not safe_target_ref
    ):
        raise ValueError("accepted or applied queue entries require target_type and target_ref")

    return {
        "schema_version": LEARNING_SCHEMA_VERSION,
        "entry_id": _safe_identifier(entry_id) or _new_entry_id("queue"),
        "timestamp": timestamp or _utc_now_iso(),
        "category": safe_category,
        "state": safe_state,
        "title": _safe_summary(title, fallback="Untitled learning candidate"),
        "source_task_id": _safe_identifier(source_task_id),
        "source_event_id": _safe_identifier(source_event_id),
        "evidence": _safe_list(evidence or []),
        "proposed_change": _safe_summary(proposed_change, fallback=None),
        "acceptance_criteria": _safe_list(acceptance_criteria or []),
        "target_type": safe_target_type,
        "target_ref": safe_target_ref,
        "dedupe_key": _safe_identifier(dedupe_key),
        "privacy_class": _safe_privacy_class(privacy_class),
    }


def normalize_long_term_queue_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an existing dict into the long-term queue schema."""

    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")
    return build_long_term_queue_entry(
        entry.get("category"),
        entry_id=entry.get("entry_id"),
        timestamp=_safe_timestamp(entry.get("timestamp")),
        state=entry.get("state"),
        title=entry.get("title"),
        source_task_id=entry.get("source_task_id"),
        source_event_id=entry.get("source_event_id"),
        evidence=entry.get("evidence") if isinstance(entry.get("evidence"), list) else [],
        proposed_change=entry.get("proposed_change"),
        acceptance_criteria=(
            entry.get("acceptance_criteria")
            if isinstance(entry.get("acceptance_criteria"), list)
            else []
        ),
        target_type=entry.get("target_type"),
        target_ref=entry.get("target_ref"),
        dedupe_key=entry.get("dedupe_key"),
        privacy_class=entry.get("privacy_class"),
    )


def append_long_term_queue_entry(
    entry: Dict[str, Any],
    *,
    queue_path: str | Path = LONG_TERM_QUEUE_PATH,
) -> Dict[str, Any]:
    """Explicitly append a normalized queue entry to local JSONL storage."""

    normalized = normalize_long_term_queue_entry(entry)
    _atomic_append_jsonl(Path(queue_path), normalized)
    return normalized


def build_skills_journal_entry(
    skill_name: Any,
    *,
    entry_id: Any = None,
    timestamp: Optional[str] = None,
    source_task_id: Any = None,
    source_queue_id: Any = None,
    source_evidence: Optional[Iterable[Any]] = None,
    accepted_change: Any = None,
    eval_coverage: Any = None,
    rollback_note: Any = None,
    verification: Any = None,
    privacy_class: Any = LEARNING_PRIVACY_CLASS,
) -> Dict[str, Any]:
    """Build one normalized accepted skills journal entry."""

    safe_skill_name = _safe_identifier(skill_name)
    if not safe_skill_name:
        raise ValueError("skill_name is required")

    safe_source_evidence = _safe_list(source_evidence or [])
    safe_accepted_change = _safe_summary(accepted_change, fallback=None)
    safe_eval_coverage = _safe_summary(eval_coverage, fallback=None)
    safe_rollback_note = _safe_summary(rollback_note, fallback=None)
    if not safe_source_evidence:
        raise ValueError("source_evidence is required")
    if not safe_accepted_change:
        raise ValueError("accepted_change is required")
    if not safe_eval_coverage:
        raise ValueError("eval_coverage is required")
    if not safe_rollback_note:
        raise ValueError("rollback_note is required")

    return {
        "schema_version": LEARNING_SCHEMA_VERSION,
        "entry_id": _safe_identifier(entry_id) or _new_entry_id("skill"),
        "timestamp": timestamp or _utc_now_iso(),
        "skill_name": safe_skill_name,
        "source_task_id": _safe_identifier(source_task_id),
        "source_queue_id": _safe_identifier(source_queue_id),
        "source_evidence": safe_source_evidence,
        "accepted_change": safe_accepted_change,
        "eval_coverage": safe_eval_coverage,
        "rollback_note": safe_rollback_note,
        "verification": _safe_summary(verification, fallback=None),
        "privacy_class": _safe_privacy_class(privacy_class),
    }


def normalize_skills_journal_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an existing dict into the skills journal schema."""

    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")
    return build_skills_journal_entry(
        entry.get("skill_name"),
        entry_id=entry.get("entry_id"),
        timestamp=_safe_timestamp(entry.get("timestamp")),
        source_task_id=entry.get("source_task_id"),
        source_queue_id=entry.get("source_queue_id"),
        source_evidence=(
            entry.get("source_evidence") if isinstance(entry.get("source_evidence"), list) else []
        ),
        accepted_change=entry.get("accepted_change"),
        eval_coverage=entry.get("eval_coverage"),
        rollback_note=entry.get("rollback_note"),
        verification=entry.get("verification"),
        privacy_class=entry.get("privacy_class"),
    )


def append_skills_journal_entry(
    entry: Dict[str, Any],
    *,
    journal_path: str | Path = SKILLS_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Explicitly append a normalized skills journal entry to local JSONL storage."""

    normalized = normalize_skills_journal_entry(entry)
    _atomic_append_jsonl(Path(journal_path), normalized)
    return normalized


def build_learning_review_request(
    action: Any,
    *,
    request_id: Any = None,
    timestamp: Optional[str] = None,
    source_queue_id: Any = None,
    source_candidate_id: Any = None,
    reviewer: Any = None,
    target_type: Any = None,
    target_ref: Any = None,
    proposed_change: Any = None,
    evidence: Optional[Iterable[Any]] = None,
    verification: Any = None,
    rollback_note: Any = None,
    privacy_class: Any = LEARNING_PRIVACY_CLASS,
) -> Dict[str, Any]:
    """Build a safe manual-review request without applying the requested action."""

    safe_action = _safe_review_action(action)
    if not safe_action:
        raise ValueError("supported review action is required")

    safe_source_queue_id = _safe_identifier(source_queue_id)
    safe_source_candidate_id = _safe_identifier(source_candidate_id)
    if not safe_source_queue_id and not safe_source_candidate_id:
        raise ValueError("source_queue_id or source_candidate_id is required")

    expected_target_type = REVIEW_ACTION_TARGET_TYPES[safe_action]
    provided_target_type = _safe_status(target_type)
    if provided_target_type and provided_target_type not in TARGET_TYPES:
        raise ValueError("unsupported target_type")
    safe_target_type = provided_target_type or expected_target_type
    if safe_target_type != expected_target_type:
        raise ValueError(f"{safe_action} requires target_type {expected_target_type}")

    safe_target_ref = _safe_summary(target_ref, fallback=None)
    if not safe_target_ref:
        raise ValueError("target_ref is required")

    safe_evidence = _safe_list(evidence or [])
    if not safe_evidence:
        raise ValueError("evidence is required")

    safe_proposed_change = _safe_summary(proposed_change, fallback=None)
    if safe_action in {
        "promote_queue_to_skills_journal",
        "export_failure_review_summary",
    } and not safe_proposed_change:
        raise ValueError("proposed_change is required")

    safe_verification = _safe_summary(verification, fallback=None)
    if safe_action in {
        "promote_queue_to_skills_journal",
        "mark_badcase_covered",
    } and not safe_verification:
        raise ValueError("verification is required")

    safe_rollback_note = _safe_summary(rollback_note, fallback=None)
    if safe_action == "promote_queue_to_skills_journal" and not safe_rollback_note:
        raise ValueError("rollback_note is required")

    return {
        "schema_version": LEARNING_SCHEMA_VERSION,
        "request_id": _safe_identifier(request_id) or _new_entry_id("review"),
        "timestamp": _safe_timestamp(timestamp) or _utc_now_iso(),
        "action": safe_action,
        "state": "pending_review",
        "requires_review": True,
        "source_queue_id": safe_source_queue_id,
        "source_candidate_id": safe_source_candidate_id,
        "reviewer": _safe_identifier(reviewer),
        "target_type": safe_target_type,
        "target_ref": safe_target_ref,
        "proposed_change": safe_proposed_change,
        "evidence": safe_evidence,
        "verification": safe_verification,
        "rollback_note": safe_rollback_note,
        "requested_effect": REVIEW_ACTION_EFFECTS[safe_action],
        "blocked_effects": list(REVIEW_BLOCKED_EFFECTS),
        "privacy_class": _safe_privacy_class(privacy_class),
    }


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


def _safe_list(values: Iterable[Any]) -> list[str]:
    safe_values = []
    for value in values:
        safe = _safe_summary(value, fallback=None)
        if safe and safe not in safe_values:
            safe_values.append(safe)
        if len(safe_values) >= LIST_LIMIT:
            break
    return safe_values


def _safe_category(value: Any) -> Optional[str]:
    category = _safe_status(value)
    if not category:
        return None
    return category if category in QUEUE_CATEGORIES else "code_issue"


def _safe_queue_state(value: Any) -> str:
    state = _safe_status(value)
    if state in QUEUE_STATES:
        return state
    return "candidate"


def _safe_target_type(value: Any) -> Optional[str]:
    target_type = _safe_status(value)
    if target_type in TARGET_TYPES:
        return target_type
    return None


def _safe_review_action(value: Any) -> Optional[str]:
    action = _safe_status(value)
    if action in REVIEW_ACTIONS:
        return action
    return None


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
    return LEARNING_PRIVACY_CLASS


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


def _new_entry_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
