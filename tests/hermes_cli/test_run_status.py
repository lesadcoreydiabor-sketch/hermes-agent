import json
from argparse import Namespace

from hermes_cli import status as status_mod
from hermes_cli.run_inspector import (
    MCPHealthSnapshot,
    RunSnapshot,
    ToolHealthSnapshot,
    build_run_inspector_snapshot,
    empty_run_snapshot,
)


def test_build_run_inspector_snapshot_prefers_live_gateway_when_no_session():
    snapshot = build_run_inspector_snapshot(
        session_snapshot=empty_run_snapshot(degraded_reason="no_sessions_found"),
        gateway_snapshot=RunSnapshot(
            run_id="gateway:123",
            source="gateway",
            status="waiting_input",
            last_activity_at="2026-05-11T00:00:00+00:00",
        ),
        tool_health=(
            ToolHealthSnapshot(name="shell", toolset="terminal", status="available"),
        ),
        mcp_health=(MCPHealthSnapshot(name="gitnexus", status="connected"),),
    ).to_dict()

    assert snapshot["run_id"] == "gateway:123"
    assert snapshot["source"] == "gateway"
    assert snapshot["status"] == "waiting_input"
    assert snapshot["active_tool"] == {
        "name": None,
        "call_id": None,
        "duration_ms": None,
        "args_summary": None,
    }
    assert snapshot["tool_health"][0]["name"] == "shell"
    assert snapshot["mcp_health"][0]["name"] == "gitnexus"
    assert snapshot["privacy_flags"] == ["safe", "redacted", "local_only"]


def test_get_run_inspector_status_payload_uses_configured_mcp(monkeypatch):
    calls = []

    class FakeInspector:
        @staticmethod
        def collect_tool_and_mcp_health(**kwargs):
            calls.append(("collect", kwargs))
            return (
                (
                    ToolHealthSnapshot(
                        name="local_tool",
                        toolset="local",
                        status="available",
                    ),
                ),
                (MCPHealthSnapshot(name="gitnexus", status="unknown"),),
            )

        @staticmethod
        def build_run_inspector_snapshot(**kwargs):
            calls.append(("build", kwargs))
            return RunSnapshot(
                run_id="run-1",
                source="cli",
                status="thinking",
                tool_health=kwargs["tool_health"],
                mcp_health=kwargs["mcp_health"],
                privacy_flags=("safe", "redacted", "local_only"),
            )

    monkeypatch.setattr(
        status_mod,
        "load_config",
        lambda: {"mcp_servers": {"gitnexus": {}}},
    )

    payload = status_mod.get_run_inspector_status_payload(
        inspector_module=FakeInspector,
    )

    assert calls[0] == (
        "collect",
        {"configured_mcp_servers": {"gitnexus": {}}},
    )
    assert calls[1][0] == "build"
    assert payload["run_id"] == "run-1"
    assert payload["tool_health"][0]["name"] == "local_tool"
    assert payload["mcp_health"][0]["name"] == "gitnexus"


def test_show_status_run_inspector_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        status_mod,
        "get_run_inspector_status_payload",
        lambda: {
            "version": 1,
            "run_id": "run-json",
            "source": "cli",
            "status": "waiting_input",
            "reason": None,
            "workspace": None,
            "session_id": "run-json",
            "last_activity_at": "2026-05-11T00:00:00+00:00",
            "active_tool": {
                "name": None,
                "call_id": None,
                "duration_ms": None,
                "args_summary": None,
            },
            "tool_health": [],
            "mcp_health": [],
            "recovery_hint": None,
            "privacy_flags": ["safe", "redacted", "local_only"],
            "degraded_reason": None,
        },
    )

    status_mod.show_status(Namespace(run_inspector=True))

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["run_id"] == "run-json"
    assert payload["status"] == "waiting_input"
    assert "Hermes Agent Status" not in output


def test_run_inspector_status_handles_optional_health_errors(monkeypatch):
    class FakeInspector:
        @staticmethod
        def collect_tool_and_mcp_health(**kwargs):
            raise RuntimeError("optional health unavailable")

        @staticmethod
        def build_run_inspector_snapshot(**kwargs):
            return RunSnapshot(
                run_id="run-degraded",
                source="cli",
                status="unknown",
                degraded_reason="session_state_unknown",
                tool_health=kwargs["tool_health"],
                mcp_health=kwargs["mcp_health"],
            )

    monkeypatch.setattr(status_mod, "load_config", lambda: {})

    payload = status_mod.get_run_inspector_status_payload(
        inspector_module=FakeInspector,
    )

    assert payload["run_id"] == "run-degraded"
    assert payload["tool_health"] == []
    assert payload["mcp_health"] == []
    assert payload["degraded_reason"] == "session_state_unknown"


def test_run_inspector_status_degrades_when_snapshot_build_fails(monkeypatch):
    class FakeInspector:
        @staticmethod
        def collect_tool_and_mcp_health(**kwargs):
            return (), ()

        @staticmethod
        def build_run_inspector_snapshot(**kwargs):
            raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(status_mod, "load_config", lambda: {})

    payload = status_mod.get_run_inspector_status_payload(
        inspector_module=FakeInspector,
    )

    assert payload["status"] == "unknown"
    assert payload["degraded_reason"] == "run_inspector_build_failed:RuntimeError"
    assert payload["privacy_flags"] == ["safe"]
