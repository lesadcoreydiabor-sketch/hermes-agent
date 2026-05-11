import json

import pytest

import hermes_cli.action_ledger as action_ledger
from hermes_cli.action_ledger import (
    append_action_ledger_entry,
    build_action_ledger_entry,
    default_action_ledger_path,
    normalize_action_ledger_entry,
)


def test_build_action_ledger_entry_redacts_sensitive_values() -> None:
    entry = build_action_ledger_entry(
        "verification.run",
        event_id="evt-token=super-secret",
        run_id="run-ghp_1234567890",
        session_id="session-1",
        task_id="HMAM-05",
        work_id="work-1",
        agent_id="agent-1",
        parent_agent_id="parent-1",
        status="Completed",
        summary="Inspect C:\\Users\\XQQ\\secret\\project",
        verification="api_key=abc123 should not leak",
        blockers=["password=abc", "safe blocker"],
        next_step="Continue HMAM-06",
        timestamp="2026-05-11T00:00:00Z",
    )

    assert entry == {
        "agent_id": "agent-1",
        "blockers": ["Redacted", "safe blocker"],
        "event_id": "Redacted",
        "event_type": "verification.run",
        "next_step": "Continue HMAM-06",
        "parent_agent_id": "parent-1",
        "privacy_class": "redacted_summary",
        "run_id": "Redacted",
        "schema_version": 1,
        "session_id": "session-1",
        "status": "completed",
        "summary": "Redacted",
        "task_id": "HMAM-05",
        "timestamp": "2026-05-11T00:00:00Z",
        "verification": "Redacted",
        "work_id": "work-1",
    }


def test_build_action_ledger_entry_truncates_long_fields() -> None:
    entry = build_action_ledger_entry(
        "task.started",
        summary="s" * 400,
        next_step="n" * 400,
        blockers=[f"blocker-{i}" for i in range(20)],
    )

    assert entry["summary"].endswith("...")
    assert len(entry["summary"]) <= 240
    assert entry["next_step"].endswith("...")
    assert len(entry["next_step"]) <= 240
    assert len(entry["blockers"]) == 12


def test_normalize_rejects_missing_event_type() -> None:
    with pytest.raises(ValueError, match="event_type is required"):
        normalize_action_ledger_entry({"summary": "missing event"})


def test_build_redacts_diff_like_content() -> None:
    entry = build_action_ledger_entry(
        "failure.reviewed",
        summary="diff --git a/secret b/secret\n+token=secret",
        verification="@@ -1 +1 @@\n-old\n+new",
    )

    assert entry["summary"] == "Redacted"
    assert entry["verification"] == "Redacted"


def test_default_action_ledger_path_is_workspace_local() -> None:
    assert default_action_ledger_path("workspace").as_posix() == (
        "workspace/.hermes/action_ledger.jsonl"
    )


def test_build_only_does_not_create_ledger_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    build_action_ledger_entry("task.started", summary="safe")

    assert not (tmp_path / ".hermes" / "action_ledger.jsonl").exists()


def test_append_action_ledger_entry_writes_jsonl_atomically(tmp_path, monkeypatch) -> None:
    ledger_path = tmp_path / ".hermes" / "action_ledger.jsonl"
    calls = []
    original_atomic_replace = action_ledger.atomic_replace

    def recording_atomic_replace(tmp_file, target):
        calls.append((tmp_file, target))
        return original_atomic_replace(tmp_file, target)

    monkeypatch.setattr(action_ledger, "atomic_replace", recording_atomic_replace)

    first = append_action_ledger_entry(
        {"event_type": "task.started", "summary": "started", "task_id": "HMAM-05"},
        ledger_path=ledger_path,
    )
    second = append_action_ledger_entry(
        {"event_type": "verification.run", "summary": "passed", "task_id": "HMAM-05"},
        ledger_path=ledger_path,
    )

    assert len(calls) == 2
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [first, second]


def test_append_action_ledger_entry_redacts_before_write(tmp_path) -> None:
    ledger_path = tmp_path / ".hermes" / "action_ledger.jsonl"

    append_action_ledger_entry(
        {
            "event_type": "task.blocked",
            "summary": "C:\\Users\\XQQ\\secret\\file.txt",
            "verification": "token=secret",
            "blockers": ["api_key=hidden"],
        },
        ledger_path=ledger_path,
    )

    rendered = ledger_path.read_text(encoding="utf-8")
    assert "C:\\Users" not in rendered
    assert "token=secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert rendered.count("Redacted") == 3
