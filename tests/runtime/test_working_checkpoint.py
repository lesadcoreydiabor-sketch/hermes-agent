import json

import yaml

from hermes_cli.working_checkpoint import (
    build_working_checkpoint,
    build_working_checkpoint_from_files,
    default_working_checkpoint_path,
)


def test_build_working_checkpoint_summarizes_task_and_ledger_state() -> None:
    checkpoint = build_working_checkpoint(
        {
            "capability": "hermes-multi-agent-memory",
            "tasks": [
                {
                    "id": "HMAM-05",
                    "title": "Add local action ledger",
                    "status": "completed",
                },
                {
                    "id": "HMAM-06",
                    "title": "Generate working checkpoint",
                    "status": "pending",
                },
                {
                    "id": "HMAM-07",
                    "title": "Add long-term queue",
                    "status": "pending",
                },
                {
                    "id": "HMAM-BLOCKED",
                    "title": "Blocked follow-up",
                    "status": "blocked",
                },
            ],
            "progress_report": [
                {
                    "task_id": "HMAM-05",
                    "verification_result": "passed: action ledger tests",
                    "next_step": "Implement HMAM-06",
                }
            ],
        },
        [
            {
                "event_type": "verification.run",
                "task_id": "HMAM-05",
                "status": "completed",
                "summary": "action ledger verified",
                "verification": "passed: pytest",
                "timestamp": "2026-05-11T00:00:00Z",
            },
            {
                "event_type": "task.started",
                "task_id": "HMAM-06",
                "status": "running",
                "summary": "checkpoint work started",
                "timestamp": "2026-05-11T00:01:00Z",
            },
        ],
        generated_at="2026-05-11T00:02:00Z",
    )

    assert checkpoint["schema_version"] == 1
    assert checkpoint["generated_at"] == "2026-05-11T00:02:00Z"
    assert checkpoint["source"] == "generated"
    assert checkpoint["active_capability"] == "hermes-multi-agent-memory"
    assert checkpoint["current_task_id"] == "HMAM-06"
    assert checkpoint["completed_tasks"] == [
        {
            "task_id": "HMAM-05",
            "title": "Add local action ledger",
            "status": "completed",
        }
    ]
    assert [task["task_id"] for task in checkpoint["pending_tasks"]] == [
        "HMAM-06",
        "HMAM-07",
    ]
    assert checkpoint["blocked_tasks"] == [
        {
            "task_id": "HMAM-BLOCKED",
            "title": "Blocked follow-up",
            "status": "blocked",
        }
    ]
    assert checkpoint["last_verification"] == "passed: pytest"
    assert checkpoint["next_step"] == "Implement HMAM-06"
    assert checkpoint["degraded_reason"] is None
    assert checkpoint["privacy_class"] == "redacted_summary"


def test_working_checkpoint_redacts_secret_paths_diffs_and_raw_like_content() -> None:
    checkpoint = build_working_checkpoint(
        {
            "capability": "token=super-secret",
            "tasks": [
                {
                    "id": "HMAM-06-ghp_1234567890",
                    "title": "Inspect C:\\Users\\XQQ\\secret\\file.txt",
                    "status": "pending",
                }
            ],
            "progress_report": [
                {
                    "verification_result": "api_key=hidden",
                    "next_step": "diff --git a/secret b/secret\n+sk-secret123456",
                }
            ],
        },
        [
            {
                "event_type": "task.blocked",
                "task_id": "task-ghp_1234567890",
                "status": "failed",
                "summary": "raw output sk-secret123456 should not leak",
                "verification": "password=hidden",
                "blockers": ["C:\\Users\\XQQ\\secret\\notes.txt"],
            }
        ],
        current_task_id="C:\\Users\\XQQ\\secret\\task.txt",
        generated_at="2026-05-11T00:00:00Z",
    )

    rendered = json.dumps(checkpoint, sort_keys=True)
    assert "C:\\Users" not in rendered
    assert "token=super-secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert "diff --git" not in rendered
    assert "sk-secret123456" not in rendered
    assert "ghp_1234567890" not in rendered
    assert "Redacted" in rendered


def test_build_working_checkpoint_from_files_degrades_when_ledger_missing(tmp_path) -> None:
    task_path = tmp_path / ".hermes" / "task.yaml"
    task_path.parent.mkdir()
    task_path.write_text(
        yaml.safe_dump(
            {
                "capability": "hermes-multi-agent-memory",
                "tasks": [
                    {
                        "id": "HMAM-06",
                        "title": "Generate working checkpoint",
                        "status": "pending",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    checkpoint = build_working_checkpoint_from_files(
        task_yaml_path=task_path,
        ledger_path=tmp_path / ".hermes" / "action_ledger.jsonl",
        generated_at="2026-05-11T00:00:00Z",
    )

    assert checkpoint["degraded_reason"] == "ledger_missing"
    assert checkpoint["current_task_id"] == "HMAM-06"
    assert checkpoint["pending_tasks"][0]["task_id"] == "HMAM-06"


def test_build_working_checkpoint_from_files_keeps_valid_ledger_lines_after_parse_error(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    task_path = hermes_dir / "task.yaml"
    ledger_path = hermes_dir / "action_ledger.jsonl"
    task_path.write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    ledger_path.write_text(
        "{not-json}\n"
        + json.dumps(
            {
                "event_type": "task.blocked",
                "task_id": "HMAM-99",
                "status": "failed",
                "summary": "safe blocked ledger task",
                "blockers": ["needs review"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    checkpoint = build_working_checkpoint_from_files(
        task_yaml_path=task_path,
        ledger_path=ledger_path,
        generated_at="2026-05-11T00:00:00Z",
    )

    assert checkpoint["degraded_reason"] == "ledger_parse_error"
    assert checkpoint["blocked_tasks"] == [
        {
            "task_id": "HMAM-99",
            "title": "safe blocked ledger task",
            "status": "failed",
        }
    ]


def test_build_working_checkpoint_from_files_degrades_when_task_yaml_is_broken(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    task_path = hermes_dir / "task.yaml"
    ledger_path = hermes_dir / "action_ledger.jsonl"
    task_path.write_text("tasks: [", encoding="utf-8")
    ledger_path.write_text("", encoding="utf-8")

    checkpoint = build_working_checkpoint_from_files(
        task_yaml_path=task_path,
        ledger_path=ledger_path,
        generated_at="2026-05-11T00:00:00Z",
    )

    assert checkpoint["degraded_reason"] == "task_contract_parse_error"
    assert checkpoint["active_capability"] == "unknown"
    assert checkpoint["completed_tasks"] == []


def test_build_working_checkpoint_bounds_task_lists() -> None:
    checkpoint = build_working_checkpoint(
        {
            "tasks": [
                {"id": f"HMAM-{index}", "title": f"Task {index}", "status": "pending"}
                for index in range(45)
            ]
        },
        [],
        generated_at="2026-05-11T00:00:00Z",
    )

    assert len(checkpoint["pending_tasks"]) == 40
    assert checkpoint["pending_tasks"][-1]["task_id"] == "HMAM-39"


def test_default_working_checkpoint_path_is_workspace_local() -> None:
    assert default_working_checkpoint_path("workspace").as_posix() == (
        "workspace/.hermes/working_checkpoint.json"
    )
