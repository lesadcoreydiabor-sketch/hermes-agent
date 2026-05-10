import asyncio
import json

import pytest

from hermes_cli.run_inspector_events import (
    RUN_INSPECTOR_EVENT_LIMIT,
    clear_run_inspector_events_for_tests,
    get_recent_run_inspector_events,
    normalize_run_inspector_event_frame,
    record_run_inspector_event,
    record_run_inspector_event_frame,
    subscribe_run_inspector_events,
    unregister_run_inspector_event_subscriber,
)


@pytest.fixture(autouse=True)
def _clear_events():
    clear_run_inspector_events_for_tests()
    yield
    clear_run_inspector_events_for_tests()


def test_normalizes_dashboard_tool_frame_without_raw_payload():
    frame = json.dumps(
        {
            "method": "event",
            "params": {
                "type": "tool.start",
                "payload": {
                    "tool_id": "shell",
                    "name": "shell",
                    "preview": "OPENAI_API_KEY=sk-secret-1234567890",
                    "args": {"command": "cat private.txt"},
                },
            },
        }
    )

    event = record_run_inspector_event_frame(frame, session_id="chat-channel-1")

    assert event is not None
    assert event["type"] == "tool.started"
    assert event["source"] == "dashboard_chat"
    assert event["session_id"] == "chat-channel-1"
    assert event["tool"] == "shell"
    encoded = json.dumps(event, sort_keys=True)
    assert "sk-secret" not in encoded
    assert "cat private.txt" not in encoded


def test_tool_complete_error_is_redacted_and_marked_failed():
    frame = json.dumps(
        {
            "type": "tool.complete",
            "payload": {
                "tool_id": "mcp_tool",
                "error": "token=super-secret-value",
            },
        }
    )

    event = record_run_inspector_event_frame(frame)

    assert event is not None
    assert event["type"] == "tool.completed"
    assert event["status"] == "failed"
    assert event["message"] == "Redacted"


def test_recent_events_are_ordered_and_limited():
    for index in range(RUN_INSPECTOR_EVENT_LIMIT + 5):
        record_run_inspector_event("tool.progress", message=f"event-{index}")

    events = get_recent_run_inspector_events(limit=3)

    assert [event["message"] for event in events] == [
        "event-202",
        "event-203",
        "event-204",
    ]
    assert len(get_recent_run_inspector_events(limit=9999)) == RUN_INSPECTOR_EVENT_LIMIT


def test_malformed_frame_is_ignored():
    assert normalize_run_inspector_event_frame("{not-json") is None
    assert record_run_inspector_event_frame("{not-json") is None
    assert get_recent_run_inspector_events() == []


@pytest.mark.asyncio
async def test_subscriber_receives_new_events():
    queue, replay = subscribe_run_inspector_events(replay=10)
    try:
        assert replay == []
        record_run_inspector_event("run.completed", run_id="run-1")
        event = await asyncio.wait_for(queue.get(), timeout=1)
    finally:
        unregister_run_inspector_event_subscriber(queue)

    assert event["type"] == "run.completed"
    assert event["run_id"] == "run-1"
