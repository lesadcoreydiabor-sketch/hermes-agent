from types import SimpleNamespace

from hermes_cli.run_inspector import (
    RunSnapshot,
    collect_tool_and_mcp_health,
    summarize_mcp_servers,
    summarize_tool_registry,
)
from tools.registry import ToolRegistry


def _schema(name="tool"):
    return {
        "name": name,
        "description": "test tool",
        "parameters": {"type": "object", "properties": {}},
    }


def _handler(args, **kwargs):
    raise AssertionError("inspector must not dispatch tools")


def test_tool_registry_summary_reports_available_and_unavailable_tools():
    reg = ToolRegistry()
    reg.register(
        name="ok_tool",
        toolset="ok",
        schema=_schema("ok_tool"),
        handler=_handler,
        check_fn=lambda: True,
    )
    reg.register(
        name="disabled_tool",
        toolset="disabled",
        schema=_schema("disabled_tool"),
        handler=_handler,
        check_fn=lambda: False,
    )
    reg.register(
        name="free_tool",
        toolset="free",
        schema=_schema("free_tool"),
        handler=_handler,
    )

    payload = [item.to_dict() for item in summarize_tool_registry(reg)]

    assert payload == [
        {
            "name": "disabled_tool",
            "toolset": "disabled",
            "status": "unavailable",
            "reason": "check_returned_false",
        },
        {
            "name": "free_tool",
            "toolset": "free",
            "status": "available",
            "reason": None,
        },
        {
            "name": "ok_tool",
            "toolset": "ok",
            "status": "available",
            "reason": None,
        },
    ]


def test_tool_registry_summary_marks_raising_checks_as_failed():
    reg = ToolRegistry()

    def broken_check():
        raise RuntimeError("network down")

    reg.register(
        name="broken_tool",
        toolset="broken",
        schema=_schema("broken_tool"),
        handler=_handler,
        check_fn=broken_check,
    )

    payload = [item.to_dict() for item in summarize_tool_registry(reg)]

    assert payload == [
        {
            "name": "broken_tool",
            "toolset": "broken",
            "status": "failed",
            "reason": "check_failed:RuntimeError",
        }
    ]


def test_mcp_summary_reports_connected_failed_degraded_and_configured_unknown():
    class Ready:
        def __init__(self, value):
            self.value = value

        def is_set(self):
            return self.value

    connected = SimpleNamespace(
        session=object(),
        _error=None,
        _ready=Ready(True),
        _registered_tool_names=["mcp_gitnexus_query"],
    )
    failed = SimpleNamespace(
        session=None,
        _error=ConnectionError("closed"),
        _ready=Ready(True),
        _registered_tool_names=["mcp_broken_query"],
    )
    degraded = SimpleNamespace(
        session=None,
        _error=None,
        _ready=Ready(True),
        _registered_tool_names=["mcp_waiting_query"],
    )

    payload = [
        item.to_dict()
        for item in summarize_mcp_servers(
            {
                "broken": failed,
                "gitnexus": connected,
                "waiting": degraded,
            },
            configured_servers={"configured_only": {}, "gitnexus": {}},
        )
    ]

    assert payload == [
        {
            "name": "broken",
            "status": "failed",
            "last_error_class": "ConnectionError",
            "affected_tools": ["mcp_broken_query"],
        },
        {
            "name": "configured_only",
            "status": "unknown",
            "last_error_class": "not_connected",
            "affected_tools": [],
        },
        {
            "name": "gitnexus",
            "status": "connected",
            "last_error_class": None,
            "affected_tools": ["mcp_gitnexus_query"],
        },
        {
            "name": "waiting",
            "status": "degraded",
            "last_error_class": "session_unavailable",
            "affected_tools": ["mcp_waiting_query"],
        },
    ]


def test_collect_tool_and_mcp_health_can_populate_run_snapshot():
    reg = ToolRegistry()
    reg.register(
        name="local_tool",
        toolset="local",
        schema=_schema("local_tool"),
        handler=_handler,
    )
    tool_health, mcp_health = collect_tool_and_mcp_health(
        registry_obj=reg,
        mcp_servers={},
        configured_mcp_servers={"gitnexus": {}},
    )

    snapshot = RunSnapshot(
        run_id="run-tools",
        source="cli",
        status="thinking",
        tool_health=tool_health,
        mcp_health=mcp_health,
    ).to_dict()

    assert snapshot["tool_health"] == [
        {
            "name": "local_tool",
            "toolset": "local",
            "status": "available",
            "reason": None,
        }
    ]
    assert snapshot["mcp_health"] == [
        {
            "name": "gitnexus",
            "status": "unknown",
            "last_error_class": "not_connected",
            "affected_tools": [],
        }
    ]
