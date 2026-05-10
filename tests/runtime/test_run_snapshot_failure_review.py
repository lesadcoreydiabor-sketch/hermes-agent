import yaml

from hermes_cli.run_inspector import (
    FAILURE_REVIEW_FIELDS,
    RunSnapshot,
    append_failure_review_entry,
    build_failure_review_entry,
    detect_repeated_unknown_state,
)


SECRET = "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456"


def test_failed_verification_entry_records_required_fields_and_redacts():
    entry = build_failure_review_entry(
        trigger="failed_verification",
        task_id="HRI-06",
        what_happened=f"pytest failed while printing {SECRET}",
        why_it_failed="The expected status mapping was wrong.",
        what_changed="Updated the status mapping regression.",
        how_it_was_verified="Re-ran focused pytest.",
        added_eval_or_badcase="tests/runtime/test_run_snapshot_failure_review.py",
    )
    payload = entry.to_dict()
    rendered = str(payload)

    assert tuple(payload.keys()) == FAILURE_REVIEW_FIELDS
    assert payload["trigger"] == "failed_verification"
    assert payload["task_id"] == "HRI-06"
    assert payload["blocker"] is False
    assert "OPENAI_API_KEY=***" in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered


def test_redaction_failure_is_always_blocker():
    entry = build_failure_review_entry(
        trigger="redaction_failure",
        task_id="HRI-04",
        what_happened="A raw token reached a snapshot.",
        why_it_failed="The payload bypassed argument summarization.",
        what_changed="Blocked release until a regression test exists.",
        how_it_was_verified="Manual inspection.",
        added_eval_or_badcase="tests/runtime/test_run_snapshot_redaction.py",
        blocker=False,
    )

    assert entry.to_dict()["blocker"] is True


def test_repeated_unknown_state_creates_regression_entry():
    snapshots = [
        RunSnapshot(status="unknown", degraded_reason="gateway_state_unknown"),
        RunSnapshot(status="unknown", degraded_reason="gateway_state_unknown"),
        RunSnapshot(status="unknown", degraded_reason="gateway_state_unknown"),
        RunSnapshot(status="thinking"),
    ]

    entry = detect_repeated_unknown_state(snapshots, threshold=3)
    payload = entry.to_dict()

    assert payload["trigger"] == "repeated_unknown_state"
    assert payload["task_id"] == "HRI-06"
    assert "3 Run Inspector snapshots returned unknown" in payload["what_happened"]
    assert payload["added_eval_or_badcase"] == "repeated_unknown_state:gateway_state_unknown"


def test_repeated_unknown_state_below_threshold_is_not_recorded():
    snapshots = [
        RunSnapshot(status="unknown", degraded_reason="gateway_state_unknown"),
        RunSnapshot(status="unknown", degraded_reason="gateway_state_unknown"),
    ]

    assert detect_repeated_unknown_state(snapshots, threshold=3) is None


def test_append_failure_review_entry_writes_task_yaml(tmp_path):
    task_yaml = tmp_path / "task.yaml"
    task_yaml.write_text(
        """
version: 1
failure_review:
  enabled: true
  entries: []
""".lstrip(),
        encoding="utf-8",
    )
    entry = build_failure_review_entry(
        trigger="blocked_task",
        task_id="HRI-06",
        what_happened="Verification could not run.",
        why_it_failed="Local test environment was unavailable.",
        what_changed="Recorded a blocker for follow-up.",
        how_it_was_verified="Opened the task file.",
        added_eval_or_badcase="manual-review",
    )

    data = append_failure_review_entry(task_yaml, entry)
    persisted = yaml.safe_load(task_yaml.read_text(encoding="utf-8"))

    assert data["failure_review"]["entries"][0]["trigger"] == "blocked_task"
    assert persisted["failure_review"]["entries"][0]["task_id"] == "HRI-06"
