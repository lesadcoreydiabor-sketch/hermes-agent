import json

import pytest

import hermes_cli.learning_journal as learning_journal
from hermes_cli.learning_journal import (
    append_long_term_queue_entry,
    append_skills_journal_entry,
    build_long_term_queue_entry,
    build_skills_journal_entry,
    default_long_term_queue_path,
    default_skills_journal_path,
)


def test_build_long_term_queue_entries_cover_review_states_and_targets() -> None:
    candidate = build_long_term_queue_entry(
        "recurring_failure",
        entry_id="queue-1",
        timestamp="2026-05-11T00:00:00Z",
        state="needs_evidence",
        title="Repeated verification timeout",
        source_task_id="HMAM-07",
        evidence=["pytest timed out twice"],
        proposed_change="Add a regression test for timeout handling",
        acceptance_criteria=["test fails before fix", "test passes after fix"],
        dedupe_key="verification-timeout",
    )
    accepted = build_long_term_queue_entry(
        "skill_improvement",
        entry_id="queue-2",
        timestamp="2026-05-11T00:01:00Z",
        state="accepted",
        title="Promote PM skill checklist",
        evidence=["failure review accepted"],
        proposed_change="Update PM workflow checklist",
        target_type="skill_update",
        target_ref="product-manager skill",
    )

    assert candidate == {
        "acceptance_criteria": ["test fails before fix", "test passes after fix"],
        "category": "recurring_failure",
        "dedupe_key": "verification-timeout",
        "entry_id": "queue-1",
        "evidence": ["pytest timed out twice"],
        "privacy_class": "redacted_summary",
        "proposed_change": "Add a regression test for timeout handling",
        "schema_version": 1,
        "source_event_id": None,
        "source_task_id": "HMAM-07",
        "state": "needs_evidence",
        "target_ref": None,
        "target_type": None,
        "timestamp": "2026-05-11T00:00:00Z",
        "title": "Repeated verification timeout",
    }
    assert accepted["state"] == "accepted"
    assert accepted["target_type"] == "skill_update"
    assert accepted["target_ref"] == "product-manager skill"


def test_accepted_long_term_queue_entry_requires_target() -> None:
    with pytest.raises(ValueError, match="require target_type and target_ref"):
        build_long_term_queue_entry(
            "missing_test",
            state="accepted",
            title="Missing redaction regression",
        )


def test_long_term_queue_redacts_sensitive_values_and_bounds_lists() -> None:
    entry = build_long_term_queue_entry(
        "documentation_gap",
        entry_id="queue-ghp_1234567890",
        timestamp="2026-05-11T00:00:00Z",
        title="Inspect C:\\Users\\XQQ\\secret\\notes.txt",
        source_event_id="event-token=secret",
        evidence=[
            "api_key=hidden",
            "diff --git a/secret b/secret\n+sk-secret123456",
            "safe evidence",
            *[f"extra-{index}" for index in range(10)],
        ],
        proposed_change="p" * 400,
        acceptance_criteria=["password=hidden", "safe criterion"],
        target_type="documentation_update",
        target_ref="/Users/xqq/secret.md",
    )

    rendered = json.dumps(entry, sort_keys=True)
    assert "C:\\Users" not in rendered
    assert "/Users/xqq" not in rendered
    assert "token=secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert "diff --git" not in rendered
    assert "sk-secret123456" not in rendered
    assert "ghp_1234567890" not in rendered
    assert entry["entry_id"] == "Redacted"
    assert entry["source_event_id"] == "Redacted"
    assert entry["target_ref"] == "Redacted"
    assert len(entry["evidence"]) == 8
    assert entry["proposed_change"].endswith("...")


def test_append_long_term_queue_entry_writes_jsonl_only_when_explicit(
    tmp_path,
    monkeypatch,
) -> None:
    queue_path = tmp_path / ".hermes" / "long_term_queue.jsonl"
    calls = []
    original_atomic_replace = learning_journal.atomic_replace

    def recording_atomic_replace(tmp_file, target):
        calls.append((tmp_file, target))
        return original_atomic_replace(tmp_file, target)

    monkeypatch.setattr(learning_journal, "atomic_replace", recording_atomic_replace)

    built = build_long_term_queue_entry("missing_test", title="safe")
    assert not queue_path.exists()

    appended = append_long_term_queue_entry(built, queue_path=queue_path)

    assert len(calls) == 1
    assert [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines()] == [
        appended
    ]


def test_skills_journal_requires_review_gate_fields() -> None:
    with pytest.raises(ValueError, match="source_evidence is required"):
        build_skills_journal_entry(
            "product-manager",
            accepted_change="Add workflow",
            eval_coverage="test added",
            rollback_note="revert journal entry",
        )
    with pytest.raises(ValueError, match="accepted_change is required"):
        build_skills_journal_entry(
            "product-manager",
            source_evidence=["queue accepted"],
            eval_coverage="test added",
            rollback_note="revert journal entry",
        )
    with pytest.raises(ValueError, match="eval_coverage is required"):
        build_skills_journal_entry(
            "product-manager",
            source_evidence=["queue accepted"],
            accepted_change="Add workflow",
            rollback_note="revert journal entry",
        )
    with pytest.raises(ValueError, match="rollback_note is required"):
        build_skills_journal_entry(
            "product-manager",
            source_evidence=["queue accepted"],
            accepted_change="Add workflow",
            eval_coverage="test added",
        )


def test_build_skills_journal_entry_records_accepted_learning_safely() -> None:
    entry = build_skills_journal_entry(
        "product-manager",
        entry_id="skill-1",
        timestamp="2026-05-11T00:00:00Z",
        source_task_id="HMAM-07",
        source_queue_id="queue-1",
        source_evidence=["accepted queue entry"],
        accepted_change="Require PRD slices to include agent-ready verification",
        eval_coverage="tests/runtime/test_learning_journal.py",
        rollback_note="Remove the journal entry before editing the skill package",
        verification="passed: pytest",
    )

    assert entry == {
        "accepted_change": "Require PRD slices to include agent-ready verification",
        "entry_id": "skill-1",
        "eval_coverage": "tests/runtime/test_learning_journal.py",
        "privacy_class": "redacted_summary",
        "rollback_note": "Remove the journal entry before editing the skill package",
        "schema_version": 1,
        "skill_name": "product-manager",
        "source_evidence": ["accepted queue entry"],
        "source_queue_id": "queue-1",
        "source_task_id": "HMAM-07",
        "timestamp": "2026-05-11T00:00:00Z",
        "verification": "passed: pytest",
    }


def test_skills_journal_redacts_sensitive_values() -> None:
    entry = build_skills_journal_entry(
        "skill-ghp_1234567890",
        source_task_id="HMAM-07",
        source_queue_id="queue-token=secret",
        source_evidence=["C:\\Users\\XQQ\\secret\\failure.txt"],
        accepted_change="diff --git a/skill b/skill\n+secret",
        eval_coverage="api_key=hidden",
        rollback_note="/Users/xqq/secret rollback note",
        verification="sk-secret123456",
    )

    rendered = json.dumps(entry, sort_keys=True)
    assert "ghp_1234567890" not in rendered
    assert "token=secret" not in rendered
    assert "C:\\Users" not in rendered
    assert "/Users/xqq" not in rendered
    assert "diff --git" not in rendered
    assert "api_key=hidden" not in rendered
    assert "sk-secret123456" not in rendered
    assert rendered.count("Redacted") >= 6


def test_append_skills_journal_entry_writes_jsonl_without_editing_skills(
    tmp_path,
) -> None:
    journal_path = tmp_path / ".hermes" / "skills_journal.jsonl"
    skill_path = tmp_path / "skills" / "product-manager" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("original skill body", encoding="utf-8")

    appended = append_skills_journal_entry(
        {
            "skill_name": "product-manager",
            "source_evidence": ["queue accepted"],
            "accepted_change": "Add a review checklist",
            "eval_coverage": "pytest test_learning_journal.py",
            "rollback_note": "Delete this journal record before touching SKILL.md",
        },
        journal_path=journal_path,
    )

    assert json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0]) == appended
    assert skill_path.read_text(encoding="utf-8") == "original skill body"


def test_learning_journal_default_paths_are_workspace_local() -> None:
    assert default_long_term_queue_path("workspace").as_posix() == (
        "workspace/.hermes/long_term_queue.jsonl"
    )
    assert default_skills_journal_path("workspace").as_posix() == (
        "workspace/.hermes/skills_journal.jsonl"
    )
