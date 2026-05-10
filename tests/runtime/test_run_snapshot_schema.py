from hermes_cli.run_inspector import (
    ActiveToolSnapshot,
    MCPHealthSnapshot,
    RUN_SNAPSHOT_VERSION,
    RunSnapshot,
    ToolHealthSnapshot,
    empty_run_snapshot,
    summarize_private_payload,
)


def test_minimal_snapshot_has_required_contract_fields():
    payload = RunSnapshot(run_id="run-1").to_dict()

    assert payload == {
        "version": RUN_SNAPSHOT_VERSION,
        "run_id": "run-1",
        "source": "unknown",
        "status": "unknown",
        "reason": None,
        "workspace": None,
        "session_id": None,
        "last_activity_at": None,
        "active_tool": {
            "name": None,
            "call_id": None,
            "duration_ms": None,
            "args_summary": None,
        },
        "tool_health": [],
        "mcp_health": [],
        "recovery_hint": None,
        "privacy_flags": [],
        "degraded_reason": None,
    }


def test_unknown_snapshot_is_valid_for_missing_state():
    payload = empty_run_snapshot(
        run_id="run-2",
        source="gateway",
        degraded_reason="runtime status file missing",
    ).to_dict()

    assert payload["version"] == RUN_SNAPSHOT_VERSION
    assert payload["run_id"] == "run-2"
    assert payload["source"] == "gateway"
    assert payload["status"] == "unknown"
    assert payload["degraded_reason"] == "runtime status file missing"
    assert payload["privacy_flags"] == ["safe"]


def test_invalid_choices_normalize_to_unknown_without_raising():
    snapshot = RunSnapshot(
        run_id="run-3",
        source="daemon",
        status="blocked_forever",
        active_tool={"name": "shell", "call_id": "abc", "duration_ms": -1},
        mcp_health=[
            {"name": "gitnexus", "status": "half-open", "affected_tools": ["query"]}
        ],
        privacy_flags=["safe", "unsafe"],
    )
    payload = snapshot.to_dict()

    assert payload["source"] == "unknown"
    assert payload["status"] == "unknown"
    assert payload["active_tool"]["duration_ms"] is None
    assert payload["mcp_health"][0]["status"] == "unknown"
    assert payload["privacy_flags"] == ["safe", "unknown"]


def test_active_tool_and_mcp_health_serialize_as_safe_metadata():
    snapshot = RunSnapshot(
        run_id="run-4",
        source="cli",
        status="executing_tool",
        active_tool=ActiveToolSnapshot(
            name="gitnexus_query",
            call_id="call-123",
            duration_ms=250,
        ),
        mcp_health=(
            MCPHealthSnapshot(
                name="gitnexus",
                status="connected",
                affected_tools=("query", "context"),
            ),
        ),
        tool_health=(
            ToolHealthSnapshot(
                name="gitnexus_query",
                toolset="mcp-gitnexus",
                status="available",
            ),
        ),
        privacy_flags=("safe", "local_only"),
    )
    payload = snapshot.to_dict()

    assert payload["active_tool"] == {
        "name": "gitnexus_query",
        "call_id": "call-123",
        "duration_ms": 250,
        "args_summary": None,
    }
    assert payload["tool_health"] == [
        {
            "name": "gitnexus_query",
            "toolset": "mcp-gitnexus",
            "status": "available",
            "reason": None,
        }
    ]
    assert payload["mcp_health"] == [
        {
            "name": "gitnexus",
            "status": "connected",
            "last_error_class": None,
            "affected_tools": ["query", "context"],
        }
    ]
    assert payload["privacy_flags"] == ["safe", "local_only"]


def test_snapshot_redacts_secret_like_text_fields():
    secret = "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    payload = RunSnapshot(
        run_id="run-5",
        status="failed",
        reason=f"failed with {secret}",
        recovery_hint=f"retry after rotating {secret}",
        mcp_health=(
            MCPHealthSnapshot(
                name="gitnexus",
                status="failed",
                last_error_class=f"AuthError {secret}",
            ),
        ),
    ).to_dict()
    rendered = str(payload)

    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "OPENAI_API_KEY=***" in rendered


def test_private_payload_summary_does_not_return_raw_values():
    summary = summarize_private_payload({
        "api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "prompt": "copy this private prompt",
        "nested": {"token": "ghp_abcdefghijklmnopqrstuvwxyz123456"},
    })
    rendered = str(summary)

    assert summary == {
        "type": "object",
        "key_count": 3,
        "keys": ["api_key", "nested", "prompt"],
        "truncated": False,
    }
    assert "copy this private prompt" not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
