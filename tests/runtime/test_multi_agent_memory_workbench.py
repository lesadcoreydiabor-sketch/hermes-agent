import json

import yaml

from hermes_cli.action_ledger import append_action_ledger_entry
from hermes_cli.failure_review_candidates import (
    append_failure_review_candidates_to_long_term_queue,
    build_failure_review_candidate,
)
from hermes_cli.multi_agent_memory_workbench import (
    build_multi_agent_memory_workbench,
    empty_multi_agent_memory_workbench,
)
from hermes_cli.working_checkpoint import write_working_checkpoint_from_files


def test_multi_agent_memory_workbench_summarizes_safe_sources(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "capability": "hermes-multi-agent-memory",
                "tasks": [
                    {"id": "HMAM-06", "title": "Checkpoint", "status": "completed"},
                    {"id": "HMAM-08", "title": "Workbench", "status": "pending"},
                ],
                "progress_report": [
                    {
                        "task_id": "HMAM-07",
                        "verification_result": "passed: learning journal tests",
                        "next_step": "Implement HMAM-08",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        hermes_dir / "action_ledger.jsonl",
        [
            {
                "event_type": "task.started",
                "task_id": "HMAM-08",
                "status": "running",
                "summary": "Workbench started",
                "timestamp": "2026-05-11T00:00:00Z",
            }
        ],
    )
    _write_jsonl(
        hermes_dir / "long_term_queue.jsonl",
        [
            {
                "category": "missing_test",
                "state": "candidate",
                "title": "Add workbench regression",
                "evidence": ["HMAM-08 needs coverage"],
            }
        ],
    )
    _write_jsonl(
        hermes_dir / "skills_journal.jsonl",
        [
            {
                "skill_name": "product-manager",
                "source_evidence": ["accepted queue item"],
                "accepted_change": "Use agent-ready issue slices",
                "eval_coverage": "test_learning_journal.py",
                "rollback_note": "Remove journal record before changing skill",
            }
        ],
    )

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[
            {
                "id": 1,
                "type": "agent.child.running",
                "source": "multi_agent",
                "run_id": "work-1",
                "session_id": "parent-1",
                "tool": "worker",
                "status": "running",
                "message": "child running",
                "timestamp": "2026-05-11T00:01:00Z",
            }
        ],
        memory_diagnostics={
            "providers": [
                {
                    "name": "builtin",
                    "kind": "builtin",
                    "availability": "available",
                    "initialized": True,
                    "tool_names": ["builtin_recall"],
                    "last_lifecycle": {
                        "event": "prefetch",
                        "status": "ok",
                        "timestamp": "2026-05-11T00:00:00Z",
                    },
                }
            ],
            "degraded_reason": None,
        },
        generated_at="2026-05-11T00:02:00Z",
    )

    assert workbench["status"] == "active"
    assert workbench["generated_at"] == "2026-05-11T00:02:00Z"
    assert workbench["active_work"][0]["work_id"] == "work-1"
    assert workbench["memory"]["status"] == "available"
    assert workbench["memory"]["registered_tools"] == ["builtin_recall"]
    assert workbench["agent_assignments"]["summary"]["ready_task_ids"] == ["HMAM-08"]
    assert workbench["agent_assignments"]["summary"]["completed_count"] == 1
    assert workbench["checkpoint"]["current_task_id"] == "HMAM-08"
    assert workbench["action_ledger"]["entries"][0]["task_id"] == "HMAM-08"
    assert workbench["long_term_queue"]["unresolved_count"] == 1
    assert workbench["skills_journal"]["entries"][0]["skill_name"] == "product-manager"
    assert workbench["privacy_class"] == "redacted_summary"


def test_multi_agent_memory_workbench_reads_runtime_persisted_files(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    task_path = hermes_dir / "task.yaml"
    ledger_path = hermes_dir / "action_ledger.jsonl"
    queue_path = hermes_dir / "long_term_queue.jsonl"
    checkpoint_path = hermes_dir / "working_checkpoint.json"
    task_path.write_text(
        yaml.safe_dump(
            {
                "capability": "hermes-multi-agent-memory",
                "tasks": [
                    {"id": "HMAMR-06", "title": "Workbench runtime files", "status": "running"}
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    append_action_ledger_entry(
        {
            "event_type": "agent.child.running",
            "task_id": "HMAMR-06",
            "work_id": "work-1",
            "agent_id": "child-1",
            "status": "running",
            "summary": "token=super-secret C:\\Users\\XQQ\\secret.txt",
        },
        ledger_path=ledger_path,
    )
    candidate = build_failure_review_candidate(
        "repeated_runtime_error",
        task_id="HMAMR-06",
        tool_name="delegate_task",
        error_type="SubagentFailed",
        what_happened="delegate child failed safely",
        dedupe_key="delegate_task:SubagentFailed:HMAMR-06",
    )
    append_failure_review_candidates_to_long_term_queue([candidate], queue_path=queue_path)
    write_working_checkpoint_from_files(
        task_yaml_path=task_path,
        ledger_path=ledger_path,
        checkpoint_path=checkpoint_path,
        generated_at="2026-05-11T00:00:00Z",
    )

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:01:00Z",
    )

    assert checkpoint_path.exists()
    assert workbench["checkpoint"]["current_task_id"] == "HMAMR-06"
    assert workbench["action_ledger"]["entries"][0]["work_id"] == "work-1"
    assert workbench["action_ledger"]["recovery_gates"]["status"] == "monitoring"
    assert workbench["action_ledger"]["recovery_gates"]["monitoring_count"] == 1
    assert workbench["action_ledger"]["recovery_gates"]["monitoring_task_ids"] == [
        "HMAMR-06"
    ]
    assert workbench["long_term_queue"]["unresolved_count"] == 1
    assert workbench["long_term_queue"]["entries"][0]["category"] == "recurring_failure"
    rendered = json.dumps(workbench, sort_keys=True)
    assert "super-secret" not in rendered
    assert "C:\\Users" not in rendered


def test_multi_agent_memory_workbench_summarizes_delegate_recovery_gates(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    ledger_path = hermes_dir / "action_ledger.jsonl"
    append_action_ledger_entry(
        {
            "event_type": "agent.child.completed",
            "task_id": "HMAMO-14",
            "run_id": "child-complete",
            "status": "completed",
            "summary": "delegate child completed",
            "verification": "delegate child completed",
            "next_step": "Review delegate child handoff summary.",
        },
        ledger_path=ledger_path,
    )
    append_action_ledger_entry(
        {
            "event_type": "agent.child.failed",
            "task_id": "HMAMO-15",
            "run_id": "child-failed",
            "status": "failed",
            "summary": "failed token=super-secret C:\\Users\\XQQ\\secret.txt",
            "blockers": ["token=super-secret C:\\Users\\XQQ\\secret.txt"],
            "next_step": "Review delegate failure and decide retry, reassignment, or handoff.",
        },
        ledger_path=ledger_path,
    )
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:01:00Z",
    )

    gates = workbench["action_ledger"]["recovery_gates"]
    assert gates["status"] == "blocked"
    assert gates["completed_count"] == 1
    assert gates["blocked_count"] == 1
    assert gates["monitoring_count"] == 0
    assert gates["verification_task_ids"] == ["HMAMO-14"]
    assert gates["blocked_task_ids"] == ["HMAMO-15"]
    assert gates["next_steps"] == [
        "Review delegate child handoff summary.",
        "Review delegate failure and decide retry, reassignment, or handoff.",
    ]
    assert gates["blockers"] == ["Redacted"]
    rendered = json.dumps(workbench, sort_keys=True)
    assert "super-secret" not in rendered
    assert "C:\\Users" not in rendered


def test_multi_agent_memory_workbench_derives_recovery_gates_from_events(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[
            {
                "id": 1,
                "type": "agent.child.running",
                "source": "multi_agent",
                "run_id": "child-running",
                "session_id": "HMAMO-18",
                "status": "running",
                "message": "child running",
                "timestamp": "2026-05-11T00:00:00Z",
            },
            {
                "id": 2,
                "type": "agent.child.failed",
                "source": "multi_agent",
                "run_id": "child-failed",
                "session_id": "HMAMO-18",
                "status": "failed",
                "message": "failed token=super-secret C:\\Users\\XQQ\\secret.txt",
                "timestamp": "2026-05-11T00:01:00Z",
            },
        ],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:02:00Z",
    )

    assert workbench["action_ledger"]["degraded_reason"] == "action_ledger_missing"
    gates = workbench["action_ledger"]["recovery_gates"]
    assert gates["status"] == "blocked"
    assert gates["blocked_count"] == 1
    assert gates["monitoring_count"] == 1
    assert gates["blocked_task_ids"] == ["HMAMO-18"]
    assert gates["monitoring_task_ids"] == ["HMAMO-18"]
    assert gates["next_steps"] == [
        "Monitor delegate child lifecycle.",
        "Review delegate failure and decide retry, reassignment, or handoff.",
    ]
    assert gates["blockers"] == ["Redacted"]
    rendered = json.dumps(workbench, sort_keys=True)
    assert "super-secret" not in rendered
    assert "C:\\Users" not in rendered


def test_multi_agent_memory_workbench_uses_latest_recovery_gate_state(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    ledger_path = hermes_dir / "action_ledger.jsonl"
    append_action_ledger_entry(
        {
            "event_type": "agent.child.spawned",
            "task_id": "HMAMO-19",
            "run_id": "child-1",
            "agent_id": "child-1",
            "status": "queued",
            "next_step": "Monitor delegate child lifecycle.",
        },
        ledger_path=ledger_path,
    )
    append_action_ledger_entry(
        {
            "event_type": "agent.child.running",
            "task_id": "HMAMO-19",
            "run_id": "child-1",
            "agent_id": "child-1",
            "status": "running",
            "next_step": "Monitor delegate child lifecycle.",
        },
        ledger_path=ledger_path,
    )
    append_action_ledger_entry(
        {
            "event_type": "agent.child.completed",
            "task_id": "HMAMO-19",
            "run_id": "child-1",
            "agent_id": "child-1",
            "status": "completed",
            "verification": "delegate child completed",
            "next_step": "Review delegate child handoff summary.",
        },
        ledger_path=ledger_path,
    )
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[
            {
                "id": 1,
                "type": "agent.child.running",
                "source": "multi_agent",
                "run_id": "child-2",
                "session_id": "HMAMO-19",
                "status": "running",
                "timestamp": "2026-05-11T00:00:00Z",
            },
            {
                "id": 2,
                "type": "agent.child.failed",
                "source": "multi_agent",
                "run_id": "child-2",
                "session_id": "HMAMO-19",
                "status": "failed",
                "message": "delegate child failed",
                "timestamp": "2026-05-11T00:01:00Z",
            },
        ],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:02:00Z",
    )

    gates = workbench["action_ledger"]["recovery_gates"]
    assert gates["status"] == "blocked"
    assert gates["completed_count"] == 1
    assert gates["blocked_count"] == 1
    assert gates["monitoring_count"] == 0
    assert gates["verification_task_ids"] == ["HMAMO-19"]
    assert gates["blocked_task_ids"] == ["HMAMO-19"]
    assert gates["monitoring_task_ids"] == []
    assert gates["next_steps"] == [
        "Review delegate child handoff summary.",
        "Review delegate failure and decide retry, reassignment, or handoff.",
    ]


def test_multi_agent_memory_workbench_reports_runtime_persistence_flags(
    tmp_path,
    monkeypatch,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    (hermes_dir / "action_ledger.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "working_checkpoint.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HERMES_DELEGATE_ACTION_LEDGER", "1")
    monkeypatch.setenv("HERMES_DELEGATE_WORKING_CHECKPOINT", "true")
    monkeypatch.setenv("HERMES_DELEGATE_FAILURE_QUEUE", "token=secret")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:01:00Z",
    )

    runtime = workbench["runtime_persistence"]
    flags = {flag["name"]: flag for flag in runtime["flags"]}
    assert runtime["status"] == "enabled"
    assert runtime["enabled_count"] == 2
    assert flags["action_ledger"] == {
        "name": "action_ledger",
        "env_var": "HERMES_DELEGATE_ACTION_LEDGER",
        "enabled": True,
        "path": ".hermes/action_ledger.jsonl",
        "exists": True,
        "privacy_class": "redacted_summary",
    }
    assert flags["working_checkpoint"]["enabled"] is True
    assert flags["working_checkpoint"]["exists"] is True
    assert flags["failure_queue"]["enabled"] is False
    assert flags["failure_queue"]["exists"] is False
    rendered = json.dumps(runtime, sort_keys=True)
    assert "token=secret" not in rendered


def test_multi_agent_memory_workbench_summarizes_agent_assignments(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "capability": "hermes-multi-agent-memory",
                "tasks": [
                    {
                        "id": "HMAMO-01",
                        "title": "Schema helper",
                        "status": "completed",
                        "agent_role": "planner",
                    },
                    {
                        "id": "HMAMO-02",
                        "title": "Summary helper",
                        "status": "pending",
                        "depends_on": ["HMAMO-01"],
                        "write_scope": {
                            "files": ["hermes_cli/agent_task_assignment.py"]
                        },
                        "verify": ["pytest assignment summary"],
                    },
                    {
                        "id": "HMAMO-03",
                        "title": "Conflicting helper",
                        "status": "running",
                        "write_scope": {"directories": ["hermes_cli"]},
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (hermes_dir / "action_ledger.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:01:00Z",
    )

    assignments = workbench["agent_assignments"]
    summary = assignments["summary"]
    plan = assignments["parallel_plan"]
    handoff = assignments["handoff_protocol"]
    assert summary["status"] == "conflict"
    assert summary["total_count"] == 3
    assert summary["ready_task_ids"] == ["HMAMO-02"]
    assert summary["conflicts"][0]["task_ids"] == ["HMAMO-02", "HMAMO-03"]
    assert plan["batches"][0]["task_ids"] == ["HMAMO-02"]
    assert plan["active_task_ids"] == ["HMAMO-03"]
    assert plan["conflict_task_ids"] == ["HMAMO-02", "HMAMO-03"]
    assert handoff["status"] == "needs_verification"
    assert handoff["handoff_task_ids"] == ["HMAMO-01"]
    assert handoff["verification_missing_task_ids"] == ["HMAMO-01"]
    assert assignments["assignments"][1]["verification"]["command"] == (
        "pytest assignment summary"
    )
    assert assignments["privacy_class"] == "redacted_summary"


def test_multi_agent_memory_workbench_redacts_agent_assignment_payloads(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "capability": "hermes-multi-agent-memory",
                "tasks": [
                    {
                        "id": "task-ghp_1234567890",
                        "title": "C:\\Users\\XQQ\\secret\\file.txt",
                        "status": "in_progress",
                        "write_scope": {"files": ["C:\\Users\\XQQ\\secret\\file.txt"]},
                        "verify": ["diff --git a/secret b/secret\n+token=secret"],
                        "next_step": "api_key=hidden",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:01:00Z",
    )

    rendered = json.dumps(workbench["agent_assignments"], sort_keys=True)
    assert "ghp_1234567890" not in rendered
    assert "C:\\Users" not in rendered
    assert "diff --git" not in rendered
    assert "token=secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert workbench["agent_assignments"]["parallel_plan"]["privacy_class"] == (
        "redacted_summary"
    )


def test_multi_agent_memory_workbench_degrades_when_sources_are_missing(tmp_path) -> None:
    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        generated_at="2026-05-11T00:00:00Z",
    )

    assert workbench["status"] == "degraded"
    assert "task_contract_missing" in workbench["degraded_reason"]
    assert "action_ledger_missing" in workbench["degraded_reason"]
    assert workbench["checkpoint"]["pending_tasks"] == []
    assert "task_contract_missing" in workbench["agent_assignments"]["degraded_reason"]
    assert (
        "task_contract_missing"
        in workbench["agent_assignments"]["parallel_plan"]["degraded_reason"]
    )
    assert (
        "task_contract_missing"
        in workbench["agent_assignments"]["handoff_protocol"]["degraded_reason"]
    )


def test_multi_agent_memory_workbench_degrades_assignment_plan_on_bad_task_contract(
    tmp_path,
) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        "tasks:\n  - id: HMAMO-10\n    title: [unterminated\n",
        encoding="utf-8",
    )
    (hermes_dir / "action_ledger.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:00:00Z",
    )

    assignments = workbench["agent_assignments"]
    assert assignments["assignments"] == []
    assert assignments["degraded_reason"] == "task_contract_parse_error"
    assert assignments["parallel_plan"]["degraded_reason"] == (
        "task_contract_parse_error"
    )
    assert assignments["handoff_protocol"]["degraded_reason"] == (
        "task_contract_parse_error"
    )
    rendered = json.dumps(assignments, sort_keys=True)
    assert "unterminated" not in rendered


def test_multi_agent_memory_workbench_empty_state_with_empty_safe_sources(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump({"capability": "hermes-multi-agent-memory"}, sort_keys=False),
        encoding="utf-8",
    )
    (hermes_dir / "action_ledger.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "long_term_queue.jsonl").write_text("", encoding="utf-8")
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:00:00Z",
    )

    assert workbench["status"] == "empty"
    assert workbench["status_reason"] == "No multi-agent memory work recorded"
    assert workbench["degraded_reason"] is None


def test_multi_agent_memory_workbench_marks_failed_active_work() -> None:
    workbench = build_multi_agent_memory_workbench(
        ".",
        events=[
            {
                "id": 1,
                "type": "agent.child.failed",
                "source": "multi_agent",
                "run_id": "work-failed",
                "status": "failed",
                "message": "safe failure",
                "timestamp": "2026-05-11T00:00:00Z",
            }
        ],
        memory_diagnostics={"providers": [], "degraded_reason": None},
        generated_at="2026-05-11T00:00:00Z",
    )

    assert workbench["status"] == "failed"
    assert workbench["active_work"][0]["status"] == "failed"


def test_multi_agent_memory_workbench_redacts_sensitive_values(tmp_path) -> None:
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    (hermes_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "capability": "token=secret",
                "tasks": [
                    {
                        "id": "HMAM-ghp_1234567890",
                        "title": "C:\\Users\\XQQ\\secret\\file.txt",
                        "status": "pending",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        hermes_dir / "action_ledger.jsonl",
        [
            {
                "event_type": "task.started",
                "task_id": "task-token=secret",
                "status": "running",
                "summary": "api_key=hidden",
            }
        ],
    )
    _write_jsonl(
        hermes_dir / "long_term_queue.jsonl",
        [
            {
                "category": "missing_test",
                "state": "candidate",
                "title": "diff --git a/secret b/secret\n+sk-secret123456",
            }
        ],
    )
    (hermes_dir / "skills_journal.jsonl").write_text("", encoding="utf-8")

    workbench = build_multi_agent_memory_workbench(
        tmp_path,
        events=[
            {
                "id": 1,
                "type": "agent.child.running",
                "source": "multi_agent",
                "run_id": "work-ghp_1234567890",
                "status": "running",
                "message": "password=hidden",
            }
        ],
        memory_diagnostics={
            "providers": [
                {
                    "name": "provider-token=secret",
                    "availability": "available",
                    "tool_names": ["tool-ghp_1234567890"],
                }
            ]
        },
        generated_at="2026-05-11T00:00:00Z",
    )

    rendered = json.dumps(workbench, sort_keys=True)
    assert "C:\\Users" not in rendered
    assert "token=secret" not in rendered
    assert "api_key=hidden" not in rendered
    assert "diff --git" not in rendered
    assert "sk-secret123456" not in rendered
    assert "ghp_1234567890" not in rendered
    assert "password=hidden" not in rendered
    assert "Redacted" in rendered


def test_empty_multi_agent_memory_workbench_is_safe_unavailable_payload() -> None:
    workbench = empty_multi_agent_memory_workbench(
        generated_at="2026-05-11T00:00:00Z",
        degraded_reason="token=secret",
    )

    assert workbench["status"] == "unavailable"
    assert workbench["degraded_reason"] == "Redacted"
    assert workbench["memory"]["status"] == "unavailable"
    assert workbench["agent_assignments"]["parallel_plan"]["status"] == "empty"
    assert workbench["agent_assignments"]["handoff_protocol"]["status"] == "empty"
    assert (
        workbench["agent_assignments"]["handoff_protocol"]["degraded_reason"]
        == "Redacted"
    )


def _write_jsonl(path, entries) -> None:
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
        encoding="utf-8",
    )
