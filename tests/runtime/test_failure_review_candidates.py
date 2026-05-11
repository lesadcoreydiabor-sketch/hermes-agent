import json

import pytest

from hermes_cli.failure_review_candidates import (
    build_failure_review_candidate,
    build_failure_review_candidates,
)


def test_failed_verification_creates_long_term_queue_candidate() -> None:
    candidate = build_failure_review_candidate(
        "failed_verification",
        candidate_id="failure-1",
        timestamp="2026-05-11T00:00:00Z",
        task_id="HMAM-09",
        what_happened="pytest failed in test_redaction",
        likely_cause="redaction case missing",
        verification_command="pytest tests/runtime/test_failure_review_candidates.py",
        proposed_badcase="Add redaction regression for leaked token",
        evidence=["exit_code=1"],
    )

    assert candidate["trigger"] == "failed_verification"
    assert candidate["task_id"] == "HMAM-09"
    assert candidate["blocker"] is False
    assert candidate["verification_command"] == (
        "pytest tests/runtime/test_failure_review_candidates.py"
    )
    assert candidate["proposed_badcase"] == "Add redaction regression for leaked token"
    queue_entry = candidate["queue_entry"]
    assert queue_entry["category"] == "missing_test"
    assert queue_entry["state"] == "candidate"
    assert queue_entry["source_task_id"] == "HMAM-09"
    assert queue_entry["proposed_change"] == "Add redaction regression for leaked token"
    assert "pytest failed in test_redaction" in queue_entry["evidence"]
    assert any(
        "Verification command covered" in item
        for item in queue_entry["acceptance_criteria"]
    )


def test_repeated_runtime_errors_dedupe_into_one_candidate() -> None:
    candidates = build_failure_review_candidates(
        [
            {
                "trigger": "repeated_tool_error",
                "tool_name": "delegate_task",
                "error_type": "TimeoutError",
                "what_happened": "delegate timed out",
                "likely_cause": "child worker hung",
            },
            {
                "trigger": "repeated_tool_error",
                "tool_name": "delegate_task",
                "error_type": "TimeoutError",
                "what_happened": "delegate timed out again",
                "likely_cause": "child worker hung",
            },
            {
                "trigger": "repeated_tool_error",
                "tool_name": "delegate_task",
                "error_type": "TimeoutError",
                "what_happened": "delegate timed out third time",
                "likely_cause": "child worker hung",
            },
        ],
        timestamp="2026-05-11T00:00:00Z",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["occurrence_count"] == 3
    assert candidate["queue_entry"]["category"] == "recurring_failure"
    assert candidate["queue_entry"]["dedupe_key"] == (
        "repeated_tool_error:delegate_task:TimeoutError"
    )
    assert "occurrences=3" in candidate["queue_entry"]["evidence"]


def test_repeated_unknown_state_creates_recovery_pattern_candidate() -> None:
    candidates = build_failure_review_candidates(
        [
            {
                "trigger": "repeated_unknown_state",
                "task_id": "HMAM-09",
                "what_happened": "status=unknown three times",
                "likely_cause": "collector classification gap",
            }
        ],
        timestamp="2026-05-11T00:00:00Z",
    )

    assert len(candidates) == 1
    assert candidates[0]["queue_entry"]["category"] == "recovery_pattern"
    assert candidates[0]["queue_entry"]["title"] == "Repeated unknown run state"


def test_redaction_failure_remains_blocker_and_redacts_sensitive_values() -> None:
    candidate = build_failure_review_candidate(
        "redaction_failure",
        candidate_id="candidate-token=secret",
        task_id="HMAM-ghp_1234567890",
        tool_name="shell",
        error_type="LeakError",
        what_happened="OPENAI_API_KEY=sk-secret123456 reached C:\\Users\\XQQ\\secret.txt",
        likely_cause="diff --git a/secret b/secret\n+token=secret",
        verification_command="pytest --token=secret",
        proposed_badcase="Cover ghp_1234567890 leak",
        evidence=["password=hidden", "safe evidence"],
        timestamp="2026-05-11T00:00:00Z",
    )

    rendered = json.dumps(candidate, sort_keys=True)
    assert candidate["blocker"] is True
    assert candidate["queue_entry"]["state"] == "needs_evidence"
    assert "Redaction regression blocks promotion" in " ".join(
        candidate["queue_entry"]["acceptance_criteria"]
    )
    assert "token=secret" not in rendered
    assert "sk-secret123456" not in rendered
    assert "C:\\Users" not in rendered
    assert "diff --git" not in rendered
    assert "ghp_1234567890" not in rendered
    assert "password=hidden" not in rendered
    assert "Redacted" in rendered


def test_failure_review_candidate_build_only_does_not_write_files(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    build_failure_review_candidate(
        "failed_verification",
        task_id="HMAM-09",
        what_happened="safe failure",
    )

    assert not (tmp_path / ".hermes" / "long_term_queue.jsonl").exists()
    assert not (tmp_path / ".hermes" / "task.yaml").exists()


def test_failure_review_candidate_rejects_missing_trigger() -> None:
    with pytest.raises(ValueError, match="trigger is required"):
        build_failure_review_candidate(None)
