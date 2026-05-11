import json

import pytest

from hermes_cli.agent_task_assignment import (
    build_agent_task_assignments_from_task_contract,
    build_agent_task_assignment,
    find_agent_task_assignment_conflicts,
    normalize_agent_task_assignment,
    summarize_agent_task_assignments,
)


def test_build_agent_task_assignment_normalizes_policy_fields() -> None:
    assignment = build_agent_task_assignment(
        "HMAMO-01",
        "Add agent assignment schema",
        role="Worker",
        owner={
            "agent_id": "worker-1",
            "parent_agent_id": "orchestrator-1",
            "human_owner": "XQQ",
        },
        status="Queued",
        dependencies={
            "task_ids": ["HMAM-11"],
            "required_artifacts": ["docs/plans/hermes-multi-agent-memory-prd.md"],
        },
        write_scope={
            "files": ["hermes_cli/agent_task_assignment.py"],
            "directories": ["tests/runtime"],
            "forbidden_paths": [".env"],
            "shared_contracts": [".hermes/task.yaml"],
        },
        allowed_tools={
            "toolsets": ["shell", "apply_patch"],
            "commands": ["venv/Scripts/python.exe -m pytest tests/runtime/test_agent_task_assignment.py"],
            "disallowed": ["network_write"],
        },
        delegate_limits={
            "max_depth": 1,
            "max_parallel_workers": 2,
            "interrupt_policy": "parent_owned",
        },
        verification={
            "command": "venv/Scripts/python.exe -m pytest tests/runtime/test_agent_task_assignment.py",
            "expected_signal": "all tests pass",
            "required_before_handoff": True,
        },
        handoff_payload={
            "summary": "Implemented safe schema helper",
            "changed_files": [
                "hermes_cli/agent_task_assignment.py",
                "tests/runtime/test_agent_task_assignment.py",
            ],
            "verification_result": "passed",
            "blockers": [],
            "next_step": "Review runtime scheduling integration later",
        },
        conflict_policy={
            "write_scope_must_be_disjoint": True,
            "shared_contract_requires_reviewer": True,
            "conflict_resolution": "reviewer_decides",
        },
    )

    assert assignment["schema_version"] == 1
    assert assignment["task_id"] == "HMAMO-01"
    assert assignment["role"] == "worker"
    assert assignment["status"] == "queued"
    assert assignment["owner"]["agent_id"] == "worker-1"
    assert assignment["dependencies"]["task_ids"] == ["HMAM-11"]
    assert assignment["write_scope"]["files"] == [
        "hermes_cli/agent_task_assignment.py"
    ]
    assert assignment["allowed_tools"]["toolsets"] == ["shell", "apply_patch"]
    assert assignment["delegate_limits"]["max_parallel_workers"] == 2
    assert assignment["delegate_limits"]["interrupt_policy"] == "parent_owned"
    assert assignment["verification"]["required_before_handoff"] is True
    assert assignment["handoff_payload"]["privacy_class"] == "redacted_summary"
    assert assignment["conflict_policy"]["conflict_resolution"] == "reviewer_decides"


def test_agent_task_assignment_redacts_sensitive_values() -> None:
    assignment = build_agent_task_assignment(
        "task-ghp_1234567890",
        "Read C:\\Users\\XQQ\\secret\\file.txt",
        owner={"agent_id": "agent-token=secret"},
        dependencies={"required_artifacts": ["diff --git a/secret b/secret\n+token=secret"]},
        write_scope={
            "files": ["C:\\Users\\XQQ\\secret\\file.txt"],
            "directories": ["/home/xqq/private"],
        },
        allowed_tools={"commands": ["echo token=secret"]},
        verification={"command": "api_key=hidden"},
        handoff_payload={
            "summary": "password=hidden",
            "changed_files": ["C:\\Users\\XQQ\\secret\\file.txt"],
            "verification_result": "sk-secret123456",
            "blockers": ["credential=hidden"],
        },
    )

    rendered = json.dumps(assignment, sort_keys=True)
    assert "ghp_1234567890" not in rendered
    assert "token=secret" not in rendered
    assert "C:\\Users" not in rendered
    assert "/home/xqq" not in rendered
    assert "diff --git" not in rendered
    assert "api_key=hidden" not in rendered
    assert "password=hidden" not in rendered
    assert assignment["task_id"] == "Redacted"
    assert assignment["title"] == "Redacted"


def test_normalize_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="task_id is required"):
        normalize_agent_task_assignment({"title": "missing id"})

    with pytest.raises(ValueError, match="title is required"):
        normalize_agent_task_assignment({"task_id": "HMAMO-01"})


def test_find_agent_task_assignment_conflicts_detects_parallel_write_overlap() -> None:
    left = build_agent_task_assignment(
        "HMAMO-01",
        "Worker A",
        status="running",
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
        conflict_policy={"conflict_resolution": "reviewer_decides"},
    )
    right = build_agent_task_assignment(
        "HMAMO-02",
        "Worker B",
        status="queued",
        write_scope={
            "directories": ["hermes_cli"],
            "files": ["tests/runtime/test_agent_task_assignment.py"],
        },
    )

    conflicts = find_agent_task_assignment_conflicts([left, right])

    assert conflicts == [
        {
            "task_ids": ["HMAMO-01", "HMAMO-02"],
            "overlap": ["hermes_cli/agent_task_assignment.py"],
            "resolution": "reviewer_decides",
            "privacy_class": "redacted_summary",
        }
    ]


def test_find_agent_task_assignment_conflicts_ignores_ordered_or_readonly_work() -> None:
    first = build_agent_task_assignment(
        "HMAMO-01",
        "Worker A",
        status="running",
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
    )
    dependent = build_agent_task_assignment(
        "HMAMO-02",
        "Worker B",
        status="queued",
        dependencies={"task_ids": ["HMAMO-01"]},
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
    )
    observer = build_agent_task_assignment(
        "HMAMO-03",
        "Observer",
        role="observer",
        status="running",
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
    )
    completed = build_agent_task_assignment(
        "HMAMO-04",
        "Completed worker",
        status="completed",
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
    )

    assert (
        find_agent_task_assignment_conflicts([first, dependent, observer, completed])
        == []
    )


def test_summarize_agent_task_assignments_reports_ready_waiting_and_conflicts() -> None:
    completed = build_agent_task_assignment(
        "HMAMO-00",
        "Completed prerequisite",
        role="planner",
        status="completed",
    )
    ready = build_agent_task_assignment(
        "HMAMO-01",
        "Ready worker",
        role="worker",
        status="queued",
        dependencies={"task_ids": ["HMAMO-00"]},
        write_scope={"files": ["hermes_cli/agent_task_assignment.py"]},
    )
    waiting = build_agent_task_assignment(
        "HMAMO-02",
        "Waiting worker",
        role="worker",
        status="planned",
        dependencies={"task_ids": ["HMAMO-99"]},
    )
    blocked = build_agent_task_assignment(
        "HMAMO-03",
        "Blocked reviewer",
        role="reviewer",
        status="blocked",
    )
    conflict = build_agent_task_assignment(
        "HMAMO-04",
        "Conflicting worker",
        role="worker",
        status="running",
        write_scope={"directories": ["hermes_cli"]},
    )

    summary = summarize_agent_task_assignments(
        [completed, ready, waiting, blocked, conflict, {"title": "invalid"}]
    )

    assert summary["status"] == "conflict"
    assert summary["total_count"] == 5
    assert summary["active_count"] == 4
    assert summary["completed_count"] == 1
    assert summary["blocked_count"] == 1
    assert summary["ready_task_ids"] == ["HMAMO-01"]
    assert summary["dependency_waiting_task_ids"] == ["HMAMO-02"]
    assert summary["blocked_task_ids"] == ["HMAMO-03"]
    assert summary["role_counts"]["worker"] == 3
    assert summary["status_counts"]["queued"] == 1
    assert summary["conflicts"][0]["task_ids"] == ["HMAMO-01", "HMAMO-04"]
    assert summary["degraded_reason"] == "invalid_assignments:1"


def test_summarize_agent_task_assignments_redacts_conflict_values() -> None:
    first = build_agent_task_assignment(
        "task-token=secret",
        "Worker A",
        status="running",
        write_scope={"files": ["C:\\Users\\XQQ\\secret\\file.txt"]},
    )
    second = build_agent_task_assignment(
        "HMAMO-02",
        "Worker B",
        status="running",
        write_scope={"files": ["C:\\Users\\XQQ\\secret\\file.txt"]},
    )

    summary = summarize_agent_task_assignments([first, second])
    rendered = json.dumps(summary, sort_keys=True)

    assert "token=secret" not in rendered
    assert "C:\\Users" not in rendered
    assert summary["conflicts"][0]["overlap"] == ["Redacted"]


def test_build_agent_task_assignments_from_task_contract_maps_task_yaml_fields() -> None:
    contract = {
        "tasks": [
            {
                "id": "HMAMO-01",
                "title": "Schema helper",
                "status": "completed",
                "agent_role": "planner",
                "verify": ["pytest schema"],
            },
            {
                "id": "HMAMO-02",
                "title": "Summary helper",
                "description": "Summarize assignments",
                "status": "pending",
                "depends_on": ["HMAMO-01"],
                "write_scope": {"files": ["hermes_cli/agent_task_assignment.py"]},
                "allowed_tools": {"toolsets": ["shell"], "commands": ["pytest summary"]},
                "delegate_limits": {
                    "max_depth": 1,
                    "max_parallel_workers": 2,
                    "interrupt_policy": "cooperative",
                },
                "verify": ["pytest summary"],
                "blockers": [],
                "next_step": "Expose summary later",
            },
        ]
    }

    assignments = build_agent_task_assignments_from_task_contract(contract)
    summary = summarize_agent_task_assignments(assignments)

    assert [assignment["task_id"] for assignment in assignments] == [
        "HMAMO-01",
        "HMAMO-02",
    ]
    assert assignments[0]["role"] == "planner"
    assert assignments[0]["status"] == "completed"
    assert assignments[1]["status"] == "planned"
    assert assignments[1]["dependencies"]["task_ids"] == ["HMAMO-01"]
    assert assignments[1]["verification"]["command"] == "pytest summary"
    assert assignments[1]["handoff_payload"]["summary"] == "Summarize assignments"
    assert summary["ready_task_ids"] == ["HMAMO-02"]


def test_build_agent_task_assignments_from_task_contract_skips_invalid_and_redacts() -> None:
    contract = {
        "tasks": [
            {"title": "missing id"},
            {
                "id": "task-token=secret",
                "title": "C:\\Users\\XQQ\\secret\\file.txt",
                "status": "in_progress",
                "depends_on": ["dep-ghp_1234567890"],
                "write_scope": {"files": ["C:\\Users\\XQQ\\secret\\file.txt"]},
                "verify": ["diff --git a/secret b/secret\n+token=secret"],
                "next_step": "api_key=hidden",
            },
        ]
    }

    assignments = build_agent_task_assignments_from_task_contract(contract)
    rendered = json.dumps(assignments, sort_keys=True)

    assert len(assignments) == 1
    assert assignments[0]["task_id"] == "Redacted"
    assert assignments[0]["title"] == "Redacted"
    assert assignments[0]["status"] == "running"
    assert "token=secret" not in rendered
    assert "ghp_1234567890" not in rendered
    assert "C:\\Users" not in rendered
    assert "diff --git" not in rendered
    assert "api_key=hidden" not in rendered
