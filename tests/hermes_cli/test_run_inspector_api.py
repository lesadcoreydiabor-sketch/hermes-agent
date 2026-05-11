import json

import pytest


@pytest.fixture
def run_inspector_client(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    return client


def test_run_inspector_api_requires_session_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)

    response = client.get("/api/run-inspector")

    assert response.status_code == 401


def test_run_inspector_api_returns_snapshot_envelope(monkeypatch, run_inspector_client):
    from hermes_cli import web_server

    monkeypatch.setattr(
        web_server,
        "get_run_inspector_status_payload",
        lambda: {
            "version": 1,
            "run_id": "run-123",
            "source": "cli",
            "status": "thinking",
            "reason": None,
            "workspace": "C:/workspace/project",
            "session_id": "session-123",
            "last_activity_at": "2026-05-11T01:00:00+00:00",
            "active_tool": {
                "name": "mcp_tool",
                "call_id": "call-123",
                "duration_ms": 42,
                "args_summary": {"type": "object", "key_count": 1},
            },
            "tool_health": [
                {"name": "shell", "toolset": "terminal", "status": "available"},
            ],
            "mcp_health": [
                {"name": "gitnexus", "status": "connected"},
            ],
            "recovery_hint": None,
            "privacy_flags": ["safe", "redacted", "local_only"],
            "degraded_reason": None,
        },
    )

    response = run_inspector_client.get("/api/run-inspector")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["refreshed_at"]
    assert payload["snapshot"]["run_id"] == "run-123"
    assert payload["snapshot"]["source"] == "cli"
    assert payload["snapshot"]["status"] == "thinking"
    assert payload["snapshot"]["active_tool"]["name"] == "mcp_tool"
    assert payload["snapshot"]["tool_health"][0]["name"] == "shell"
    assert payload["snapshot"]["mcp_health"][0]["name"] == "gitnexus"


def test_run_inspector_api_degrades_when_payload_builder_fails(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    def fail():
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(web_server, "get_run_inspector_status_payload", fail)

    response = run_inspector_client.get("/api/run-inspector")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["snapshot"]["status"] == "unknown"
    assert payload["snapshot"]["degraded_reason"] == "run_inspector_api_failed:RuntimeError"
    assert payload["snapshot"]["privacy_flags"] == ["safe"]


def test_run_inspector_api_normalizes_and_redacts_payload(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    monkeypatch.setattr(
        web_server,
        "get_run_inspector_status_payload",
        lambda: {
            "version": 1,
            "run_id": "run-secret",
            "source": "cli",
            "status": "executing_tool",
            "reason": "OPENAI_API_KEY=sk-secret-1234567890",
            "active_tool": {
                "name": "shell",
                "call_id": "call-secret",
                "duration_ms": 10,
                "args": {
                    "command": "echo $OPENAI_API_KEY",
                    "token": "sk-secret-1234567890",
                },
            },
            "privacy_flags": ["safe", "redacted", "local_only"],
        },
    )

    response = run_inspector_client.get("/api/run-inspector")

    assert response.status_code == 200
    snapshot = response.json()["snapshot"]
    encoded = json.dumps(snapshot, sort_keys=True)
    assert "sk-secret-1234567890" not in encoded
    assert snapshot["active_tool"]["args_summary"]["privacy"] == "redacted"
    assert snapshot["active_tool"]["args_summary"]["key_count"] == 2
    assert snapshot["active_tool"]["args_summary"]["value_types"] == {
        "command": "string",
        "token": "string",
    }


def test_run_inspector_attention_api_returns_safe_signals(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server
    from hermes_cli.run_inspector_events import (
        clear_run_inspector_events_for_tests,
        record_run_inspector_event,
    )

    clear_run_inspector_events_for_tests()
    monkeypatch.setattr(
        web_server,
        "get_run_inspector_status_payload",
        lambda: {
            "version": 1,
            "run_id": "run-attention",
            "source": "gateway",
            "status": "waiting_approval",
            "reason": "approval command: cat C:/Users/XQQ/private.txt",
            "session_id": "session-attention",
            "recovery_hint": "approve after checking token=super-secret",
            "mcp_health": [
                {"name": "gitnexus", "status": "degraded"},
            ],
            "privacy_flags": ["safe", "redacted", "local_only"],
        },
    )
    record_run_inspector_event(
        "run.failed",
        source="gateway_run",
        run_id="run-event",
        message="Traceback with OPENAI_API_KEY=sk-secret-1234567890",
    )

    try:
        response = run_inspector_client.get("/api/run-inspector/attention?limit=10")
    finally:
        clear_run_inspector_events_for_tests()

    assert response.status_code == 200
    payload = response.json()
    kinds = {item["kind"] for item in payload["signals"]}
    assert payload["ok"] is True
    assert {
        "approval_waiting",
        "recovery_available",
        "mcp_degraded",
        "run_failed",
    }.issubset(kinds)
    assert all(item["route"] == "/run-inspector" for item in payload["signals"])
    encoded = json.dumps(payload, sort_keys=True)
    assert "private.txt" not in encoded
    assert "super-secret" not in encoded
    assert "sk-secret" not in encoded
    assert "Traceback" not in encoded


def test_run_inspector_attention_api_degrades_when_snapshot_builder_fails(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    def fail():
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(web_server, "get_run_inspector_status_payload", fail)

    response = run_inspector_client.get("/api/run-inspector/attention")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["signals"][0]["kind"] == "run_degraded"


def test_run_inspector_desktop_status_api_returns_safe_status(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    monkeypatch.setattr(
        web_server,
        "build_desktop_status_payload",
        lambda **kwargs: {
            "ok": True,
            "record_present": False,
            "runtime_record_cleared": False,
            "pid": None,
            "pid_status": "none",
            "pid_reason": "no_record",
            "host": "127.0.0.1",
            "port": kwargs["port"],
            "route": "/run-inspector",
            "url": "http://127.0.0.1:9222/run-inspector",
            "started_at": None,
            "health": "ok",
            "health_reason": "ok",
            "compatible_dashboard": True,
            "reuse_command": "hermes desktop --port 9222",
            "manual_url": "http://127.0.0.1:9222/run-inspector",
            "stop_command": "hermes dashboard --stop",
        },
    )

    response = run_inspector_client.get("/api/run-inspector/desktop-status?port=9222")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["refreshed_at"]
    assert payload["status"]["compatible_dashboard"] is True
    assert payload["status"]["port"] == 9222
    assert payload["status"]["manual_url"] == "http://127.0.0.1:9222/run-inspector"
    assert "token=" not in json.dumps(payload)


def test_run_inspector_desktop_status_api_rejects_invalid_port(
    run_inspector_client,
):
    response = run_inspector_client.get("/api/run-inspector/desktop-status?port=70000")

    assert response.status_code == 400


def test_run_inspector_memory_workbench_api_returns_safe_readonly_summary(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    monkeypatch.setattr(
        web_server,
        "get_recent_run_inspector_events",
        lambda limit=12: [
            {
                "id": 1,
                "type": "agent.child.running",
                "source": "multi_agent",
                "run_id": "work-1",
                "status": "running",
                "message": "safe child running",
            }
        ],
    )
    monkeypatch.setattr(
        web_server,
        "build_multi_agent_memory_workbench",
        lambda *args, **kwargs: {
            "schema_version": 1,
            "generated_at": "2026-05-11T00:00:00Z",
            "status": "active",
            "status_reason": "Current task HMAM-08",
            "active_work": [
                {
                    "work_id": "work-1",
                    "status": "running",
                    "summary": "safe child running",
                }
            ],
            "memory": {
                "status": "unavailable",
                "provider_count": 0,
                "providers": [],
                "registered_tools": [],
                "degraded_reason": "memory_diagnostics_unavailable",
                "privacy_class": "redacted_summary",
            },
            "runtime_persistence": {
                "status": "enabled",
                "enabled_count": 1,
                "flags": [
                    {
                        "name": "action_ledger",
                        "env_var": "HERMES_DELEGATE_ACTION_LEDGER",
                        "enabled": True,
                        "path": ".hermes/action_ledger.jsonl",
                        "exists": True,
                        "privacy_class": "redacted_summary",
                    },
                    {
                        "name": "working_checkpoint",
                        "env_var": "HERMES_DELEGATE_WORKING_CHECKPOINT",
                        "enabled": False,
                        "path": ".hermes/working_checkpoint.json",
                        "exists": False,
                        "privacy_class": "redacted_summary",
                    },
                ],
                "degraded_reason": None,
                "privacy_class": "redacted_summary",
            },
            "agent_assignments": {
                "summary": {
                    "schema_version": 1,
                    "status": "active",
                    "total_count": 1,
                    "active_count": 1,
                    "completed_count": 0,
                    "failed_count": 0,
                    "blocked_count": 0,
                    "ready_task_ids": ["HMAM-08"],
                    "dependency_waiting_task_ids": [],
                    "blocked_task_ids": [],
                    "role_counts": {
                        "observer": 0,
                        "orchestrator": 0,
                        "planner": 0,
                        "reviewer": 0,
                        "worker": 1,
                    },
                    "status_counts": {
                        "blocked": 0,
                        "completed": 0,
                        "failed": 0,
                        "planned": 1,
                        "queued": 0,
                        "review": 0,
                        "running": 0,
                    },
                    "conflicts": [],
                    "degraded_reason": None,
                    "privacy_class": "redacted_summary",
                },
                "assignments": [
                    {
                        "schema_version": 1,
                        "task_id": "HMAM-08",
                        "title": "Workbench",
                        "role": "worker",
                        "status": "planned",
                        "owner": {
                            "agent_id": None,
                            "parent_agent_id": None,
                            "human_owner": None,
                        },
                        "dependencies": {"task_ids": [], "required_artifacts": []},
                        "write_scope": {
                            "files": [],
                            "directories": [],
                            "forbidden_paths": [],
                            "shared_contracts": [],
                        },
                        "allowed_tools": {
                            "toolsets": [],
                            "commands": [],
                            "disallowed": [],
                        },
                        "delegate_limits": {
                            "max_depth": None,
                            "max_parallel_workers": None,
                            "interrupt_policy": "cooperative",
                        },
                        "verification": {
                            "command": "",
                            "expected_signal": "",
                            "required_before_handoff": True,
                        },
                        "handoff_payload": {
                            "summary": "",
                            "changed_files": [],
                            "verification_result": None,
                            "blockers": [],
                            "next_step": "",
                            "privacy_class": "redacted_summary",
                        },
                        "conflict_policy": {
                            "write_scope_must_be_disjoint": True,
                            "shared_contract_requires_reviewer": True,
                            "conflict_resolution": "pause_and_handoff",
                        },
                        "privacy_class": "redacted_summary",
                    }
                ],
                "degraded_reason": None,
                "privacy_class": "redacted_summary",
            },
            "checkpoint": {
                "current_task_id": "HMAM-08",
                "next_step": "Continue HMAM-08",
                "pending_tasks": [],
                "completed_tasks": [],
                "blocked_tasks": [],
            },
            "action_ledger": {"entries": [], "degraded_reason": None},
            "long_term_queue": {
                "entries": [],
                "unresolved_count": 0,
                "degraded_reason": None,
            },
            "skills_journal": {"entries": [], "degraded_reason": None},
            "degraded_reason": None,
            "privacy_class": "redacted_summary",
        },
    )

    response = run_inspector_client.get("/api/run-inspector/memory-workbench?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["refreshed_at"]
    assert payload["workbench"]["status"] == "active"
    assert payload["workbench"]["active_work"][0]["work_id"] == "work-1"
    assert payload["workbench"]["checkpoint"]["current_task_id"] == "HMAM-08"
    runtime = payload["workbench"]["runtime_persistence"]
    assert runtime["status"] == "enabled"
    assert runtime["enabled_count"] == 1
    assert runtime["flags"][0]["env_var"] == "HERMES_DELEGATE_ACTION_LEDGER"
    assert runtime["flags"][0]["path"] == ".hermes/action_ledger.jsonl"
    assignments = payload["workbench"]["agent_assignments"]
    assert assignments["summary"]["ready_task_ids"] == ["HMAM-08"]
    assert assignments["assignments"][0]["task_id"] == "HMAM-08"
    assert "token=" not in json.dumps(payload)


def test_run_inspector_memory_workbench_api_degrades_when_builder_fails(
    monkeypatch,
    run_inspector_client,
):
    from hermes_cli import web_server

    def fail(*args, **kwargs):
        raise RuntimeError("token=secret")

    monkeypatch.setenv("HERMES_DELEGATE_ACTION_LEDGER", "token=secret")
    monkeypatch.setattr(web_server, "build_multi_agent_memory_workbench", fail)

    response = run_inspector_client.get("/api/run-inspector/memory-workbench")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["workbench"]["status"] == "unavailable"
    assert payload["workbench"]["degraded_reason"] == "memory_workbench_api_failed:RuntimeError"
    assert "runtime_persistence" in payload["workbench"]
    assert "agent_assignments" in payload["workbench"]
    assert "token=secret" not in json.dumps(payload)
