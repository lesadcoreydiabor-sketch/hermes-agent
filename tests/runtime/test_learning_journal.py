import json

import pytest

import hermes_cli.learning_journal as learning_journal
from hermes_cli.learning_journal import (
    append_long_term_queue_entry,
    append_skills_journal_entry,
    build_failure_review_export_preview,
    build_learning_review_request,
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


def test_learning_review_request_previews_queue_promotion_without_applying() -> None:
    request = build_learning_review_request(
        "promote_queue_to_skills_journal",
        request_id="review-1",
        timestamp="2026-05-11T00:00:00Z",
        source_queue_id="queue-1",
        reviewer="human-reviewer",
        target_ref="product-manager",
        proposed_change="Add agent-ready verification checklist",
        evidence=["queue accepted by reviewer"],
        verification="pytest tests/runtime/test_learning_journal.py",
        rollback_note="Remove the journal entry before editing SKILL.md",
    )

    assert request == {
        "action": "promote_queue_to_skills_journal",
        "blocked_effects": [
            "edit_skill_files",
            "write_memory_provider_data",
            "mutate_config",
            "mutate_task_yaml",
            "dispatch_tools_without_review",
        ],
        "evidence": ["queue accepted by reviewer"],
        "privacy_class": "redacted_summary",
        "proposed_change": "Add agent-ready verification checklist",
        "requested_effect": "append_skills_journal_after_review",
        "request_id": "review-1",
        "requires_review": True,
        "reviewer": "human-reviewer",
        "rollback_note": "Remove the journal entry before editing SKILL.md",
        "schema_version": 1,
        "source_candidate_id": None,
        "source_queue_id": "queue-1",
        "state": "pending_review",
        "target_ref": "product-manager",
        "target_type": "skill_update",
        "timestamp": "2026-05-11T00:00:00Z",
        "verification": "pytest tests/runtime/test_learning_journal.py",
    }


def test_learning_review_request_validates_review_gate_fields() -> None:
    with pytest.raises(ValueError, match="supported review action is required"):
        build_learning_review_request("apply_now")
    with pytest.raises(ValueError, match="source_queue_id or source_candidate_id"):
        build_learning_review_request(
            "mark_badcase_covered",
            target_ref="tests/runtime/test_case.py",
            evidence=["reviewed"],
            verification="pytest",
        )
    with pytest.raises(ValueError, match="rollback_note is required"):
        build_learning_review_request(
            "promote_queue_to_skills_journal",
            source_queue_id="queue-1",
            target_ref="product-manager",
            proposed_change="Add checklist",
            evidence=["reviewed"],
            verification="pytest",
        )
    with pytest.raises(ValueError, match="requires target_type skill_update"):
        build_learning_review_request(
            "promote_queue_to_skills_journal",
            source_queue_id="queue-1",
            target_type="regression_test",
            target_ref="product-manager",
            proposed_change="Add checklist",
            evidence=["reviewed"],
            verification="pytest",
            rollback_note="rollback",
        )
    with pytest.raises(ValueError, match="unsupported target_type"):
        build_learning_review_request(
            "mark_badcase_covered",
            source_queue_id="queue-1",
            target_type="config_mutation",
            target_ref="tests/runtime/test_case.py",
            evidence=["reviewed"],
            verification="pytest",
        )


def test_learning_review_request_redacts_sensitive_values_and_bounds_evidence() -> None:
    request = build_learning_review_request(
        "export_failure_review_summary",
        request_id="review-ghp_1234567890",
        source_candidate_id="candidate-token=secret",
        target_ref="C:\\Users\\XQQ\\secret\\summary.md",
        proposed_change="diff --git a/secret b/secret\n+sk-secret123456",
        evidence=[
            "api_key=hidden",
            "safe evidence",
            *[f"extra-{index}" for index in range(10)],
        ],
    )

    rendered = json.dumps(request, sort_keys=True)
    assert "ghp_1234567890" not in rendered
    assert "token=secret" not in rendered
    assert "C:\\Users" not in rendered
    assert "diff --git" not in rendered
    assert "sk-secret123456" not in rendered
    assert "api_key=hidden" not in rendered
    assert request["request_id"] == "Redacted"
    assert request["source_candidate_id"] == "Redacted"
    assert request["target_ref"] == "Redacted"
    assert request["proposed_change"] == "Redacted"
    assert len(request["evidence"]) == 8
    assert "safe evidence" in request["evidence"]


def test_learning_review_request_build_only_does_not_write_files(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    build_learning_review_request(
        "mark_badcase_covered",
        source_candidate_id="failure-1",
        target_ref="tests/runtime/test_learning_journal.py",
        evidence=["badcase covered by regression"],
        verification="pytest tests/runtime/test_learning_journal.py",
    )

    assert not (tmp_path / ".hermes").exists()
    assert not (tmp_path / "skills").exists()


def test_failure_review_export_preview_summarizes_queue_entries_safely() -> None:
    preview = build_failure_review_export_preview(
        [
            {
                "entry_id": "queue-1",
                "timestamp": "2026-05-11T00:00:00Z",
                "category": "recurring_failure",
                "state": "needs_evidence",
                "title": "Delegate timeout repeated",
                "source_task_id": "HMAMO-29",
                "evidence": ["occurrences=3", "delegate child timed out"],
                "proposed_change": "Add timeout recovery regression",
                "acceptance_criteria": ["Candidate is reviewed before export"],
            },
            {
                "entry_id": "queue-2",
                "category": "missing_test",
                "state": "candidate",
                "title": "Redaction badcase missing",
                "evidence": ["redaction candidate reviewed"],
                "proposed_change": "Add redaction regression",
                "target_type": "regression_test",
                "target_ref": "tests/runtime/test_learning_journal.py",
            },
            {
                "entry_id": "queue-ignored",
                "category": "documentation_gap",
                "state": "rejected",
                "title": "Rejected item",
            },
        ],
        preview_id="export-1",
        timestamp="2026-05-11T00:01:00Z",
    )

    assert preview["state"] == "preview_only"
    assert preview["requires_review"] is True
    assert preview["output_kind"] == "failure_review_summary"
    assert preview["entry_count"] == 2
    assert preview["category_counts"] == {
        "missing_test": 1,
        "recurring_failure": 1,
    }
    assert preview["state_counts"] == {"candidate": 1, "needs_evidence": 1}
    assert preview["entries"][0]["entry_id"] == "queue-1"
    assert preview["entries"][0]["evidence"] == [
        "occurrences=3",
        "delegate child timed out",
    ]
    assert preview["entries"][1]["target_type"] == "regression_test"
    assert preview["summary_lines"] == [
        "recurring_failure/needs_evidence: Delegate timeout repeated -> Add timeout recovery regression",
        "missing_test/candidate: Redaction badcase missing -> Add redaction regression",
    ]
    assert "write_export_file_without_review" in preview["blocked_effects"]
    assert "mark_queue_entries_applied" in preview["blocked_effects"]


def test_failure_review_export_preview_redacts_and_bounds_entries() -> None:
    preview = build_failure_review_export_preview(
        [
            {
                "entry_id": "queue-ghp_1234567890",
                "category": "recurring_failure",
                "state": "needs_evidence",
                "title": "C:\\Users\\XQQ\\secret\\failure.txt",
                "source_event_id": "event-token=secret",
                "evidence": [
                    "api_key=hidden",
                    "safe evidence",
                    *[f"extra-{index}" for index in range(10)],
                ],
                "proposed_change": "diff --git a/secret b/secret\n+sk-secret123456",
                "acceptance_criteria": ["password=hidden", "safe criterion"],
                "target_ref": "/Users/xqq/secret.md",
            },
            *[
                {
                    "entry_id": f"queue-extra-{index}",
                    "category": "missing_test",
                    "state": "candidate",
                    "title": f"extra {index}",
                }
                for index in range(10)
            ],
        ],
        preview_id="export-token=secret",
        timestamp="token=secret",
        title="Review sk-secret123456",
        limit=3,
    )

    rendered = json.dumps(preview, sort_keys=True)
    assert preview["entry_count"] == 3
    assert preview["preview_id"] == "Redacted"
    assert preview["title"] == "Redacted"
    assert preview["entries"][0]["entry_id"] == "Redacted"
    assert preview["entries"][0]["source_event_id"] == "Redacted"
    assert preview["entries"][0]["target_ref"] == "Redacted"
    assert len(preview["entries"][0]["evidence"]) == 8
    assert "safe evidence" in preview["entries"][0]["evidence"]
    assert "token=secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert "ghp_1234567890" not in rendered
    assert "C:\\Users" not in rendered
    assert "/Users/xqq" not in rendered
    assert "diff --git" not in rendered
    assert "sk-secret123456" not in rendered


def test_failure_review_export_preview_build_only_does_not_write_files(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    preview = build_failure_review_export_preview(
        [
            {
                "category": "documentation_gap",
                "state": "candidate",
                "title": "Document repeated recovery",
            }
        ]
    )

    assert preview["entry_count"] == 1
    assert not (tmp_path / ".hermes").exists()
    assert not (tmp_path / "failure-review.md").exists()


def test_learning_journal_default_paths_are_workspace_local() -> None:
    assert default_long_term_queue_path("workspace").as_posix() == (
        "workspace/.hermes/long_term_queue.jsonl"
    )
    assert default_skills_journal_path("workspace").as_posix() == (
        "workspace/.hermes/skills_journal.jsonl"
    )
