from hermes_cli.multi_agent_work_events import (
    build_multi_agent_work_event,
    multi_agent_event_to_run_inspector_kwargs,
    normalize_multi_agent_event_type,
)


def test_normalizes_known_multi_agent_event_types() -> None:
    assert normalize_multi_agent_event_type("parent_started") == "agent.parent.started"
    assert normalize_multi_agent_event_type("child_spawned") == "agent.child.spawned"
    assert normalize_multi_agent_event_type("child.running") == "agent.child.running"
    assert normalize_multi_agent_event_type("completed") == "agent.child.completed"
    assert normalize_multi_agent_event_type("failed") == "agent.child.failed"
    assert normalize_multi_agent_event_type("interrupted") == "agent.child.interrupted"
    assert normalize_multi_agent_event_type("timeout") == "agent.child.timeout"
    assert normalize_multi_agent_event_type("unknown event") == "agent.unknown"


def test_build_multi_agent_work_event_redacts_sensitive_values() -> None:
    event = build_multi_agent_work_event(
        "child_spawned",
        work_id="child-token=super-secret",
        parent_work_id="parent-1",
        agent_id="agent-ghp_1234567890",
        parent_agent_id="parent-agent",
        role="worker",
        title="Inspect C:\\Users\\XQQ\\secret\\project",
        message="api_key=abc123 should not leak",
        depth=2,
        timestamp="2026-05-11T00:00:00Z",
    )

    assert event == {
        "agent_id": "Redacted",
        "depth": 2,
        "message": "Redacted",
        "parent_agent_id": "parent-agent",
        "parent_work_id": "parent-1",
        "privacy_class": "redacted_summary",
        "role": "worker",
        "source": "multi_agent",
        "status": "queued",
        "timestamp": "2026-05-11T00:00:00Z",
        "title": "Redacted",
        "type": "agent.child.spawned",
        "work_id": "Redacted",
    }


def test_build_multi_agent_work_event_truncates_and_bounds_fields() -> None:
    event = build_multi_agent_work_event(
        "child_completed",
        work_id="work-" + "x" * 140,
        role="worker-" + "r" * 100,
        title="completed " + "t" * 240,
        message="done " + "m" * 240,
        depth=999,
        source="source!" * 40,
    )

    assert event["type"] == "agent.child.completed"
    assert event["status"] == "completed"
    assert event["depth"] == 10
    assert event["work_id"].endswith("...")
    assert len(event["work_id"]) <= 96
    assert event["role"].endswith("...")
    assert len(event["role"]) <= 64
    assert event["title"].endswith("...")
    assert len(event["title"]) <= 160
    assert event["message"].endswith("...")
    assert len(event["message"]) <= 160
    assert event["source"].endswith("...")
    assert len(event["source"]) <= 64


def test_build_multi_agent_work_event_accepts_explicit_safe_status() -> None:
    event = build_multi_agent_work_event(
        "agent.child.running",
        status="waiting_for_approval",
    )

    assert event["status"] == "waiting_for_approval"


def test_multi_agent_event_maps_to_run_inspector_kwargs_safely() -> None:
    event = build_multi_agent_work_event(
        "child_failed",
        work_id="child-1",
        parent_work_id="parent-1",
        role="debugger",
        title="failed safely",
        message="token=secret",
        timestamp="2026-05-11T00:00:00Z",
    )

    kwargs = multi_agent_event_to_run_inspector_kwargs(event)

    assert kwargs == {
        "event_type": "agent.child.failed",
        "message": "Redacted",
        "run_id": "child-1",
        "session_id": "parent-1",
        "source": "multi_agent",
        "status": "failed",
        "timestamp": "2026-05-11T00:00:00Z",
        "tool": "debugger",
    }
