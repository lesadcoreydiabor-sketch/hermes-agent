import json
import time
from urllib.parse import urlencode

import pytest

from hermes_cli.run_inspector_events import (
    clear_run_inspector_events_for_tests,
    get_recent_run_inspector_events,
    record_run_inspector_event,
)


@pytest.fixture(autouse=True)
def _clear_events():
    clear_run_inspector_events_for_tests()
    yield
    clear_run_inspector_events_for_tests()


@pytest.fixture
def run_inspector_events_client(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    return client


def test_run_inspector_events_api_requires_session_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)

    response = client.get("/api/run-inspector/events")

    assert response.status_code == 401


def test_run_inspector_events_api_returns_recent_events(run_inspector_events_client):
    record_run_inspector_event("tool.started", tool="shell", status="running")

    response = run_inspector_events_client.get("/api/run-inspector/events?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["refreshed_at"]
    assert payload["events"][0]["type"] == "tool.started"
    assert payload["events"][0]["tool"] == "shell"


def test_run_inspector_events_ws_replays_and_streams_new_events(
    run_inspector_events_client,
):
    from hermes_cli import web_server

    record_run_inspector_event("tool.started", tool="shell")

    with run_inspector_events_client.websocket_connect(
        f"/api/run-inspector/events?token={web_server._SESSION_TOKEN}"
    ) as ws:
        replay = json.loads(ws.receive_text())
        assert replay["type"] == "replay"
        assert replay["events"][0]["type"] == "tool.started"

        record_run_inspector_event("tool.completed", tool="shell")
        streamed = json.loads(ws.receive_text())

    assert streamed["type"] == "event"
    assert streamed["event"]["type"] == "tool.completed"
    assert streamed["event"]["tool"] == "shell"


def test_pub_records_events_without_changing_broadcast_behavior(
    monkeypatch,
    run_inspector_events_client,
):
    from hermes_cli import web_server

    monkeypatch.setattr(web_server, "_DASHBOARD_EMBEDDED_CHAT_ENABLED", True)
    qs = urlencode({"token": web_server._SESSION_TOKEN, "channel": "inspector-test"})
    frame = json.dumps(
        {
            "method": "event",
            "params": {
                "type": "tool.complete",
                "payload": {
                    "tool_id": "shell",
                    "summary": "token=super-secret-value",
                },
            },
        }
    )

    with run_inspector_events_client.websocket_connect(f"/api/pub?{qs}") as pub:
        pub.send_text(frame)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            events = get_recent_run_inspector_events()
            if events:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("Run Inspector event was not recorded")

    assert events[0]["type"] == "tool.completed"
    assert events[0]["session_id"] == "inspector-test"
    assert events[0]["message"] == "Redacted"
