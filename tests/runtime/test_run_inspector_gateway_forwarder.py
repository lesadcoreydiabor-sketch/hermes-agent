import json

import pytest

from hermes_cli.run_inspector_events import (
    clear_run_inspector_events_for_tests,
    get_recent_run_inspector_events,
)
from hermes_cli.run_inspector_gateway_forwarder import (
    _iter_sse_data,
    clear_gateway_run_event_forwarders_for_tests,
    forward_gateway_run_events,
    resolve_gateway_event_api_key,
    resolve_gateway_event_base_url,
)


@pytest.fixture(autouse=True)
def _clear_state():
    clear_run_inspector_events_for_tests()
    clear_gateway_run_event_forwarders_for_tests()
    yield
    clear_gateway_run_event_forwarders_for_tests()
    clear_run_inspector_events_for_tests()


class _FakeSseResponse:
    status = 200

    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        lines = []
        for event in self._events:
            lines.append(f"data: {json.dumps(event)}\n".encode())
            lines.append(b"\n")
        return iter(lines)


def test_resolves_gateway_event_base_url_from_explicit_health_and_api_env():
    assert (
        resolve_gateway_event_base_url(
            {"HERMES_RUN_INSPECTOR_GATEWAY_URL": "http://127.0.0.1:8642/health"}
        )
        == "http://127.0.0.1:8642"
    )
    assert (
        resolve_gateway_event_base_url(
            {
                "API_SERVER_ENABLED": "true",
                "API_SERVER_HOST": "0.0.0.0",
                "API_SERVER_PORT": "9000",
            }
        )
        == "http://127.0.0.1:9000"
    )
    assert resolve_gateway_event_base_url({}) is None


def test_resolves_gateway_event_key_without_exposing_request_body_secret():
    assert (
        resolve_gateway_event_api_key(
            {
                "API_SERVER_KEY": "sk-api",
                "HERMES_RUN_INSPECTOR_GATEWAY_KEY": "sk-forwarder",
            }
        )
        == "sk-forwarder"
    )
    assert resolve_gateway_event_api_key({"API_SERVER_KEY": "sk-api"}) == "sk-api"


def test_iter_sse_data_joins_multiline_frames_and_ignores_comments():
    frames = list(
        _iter_sse_data(
            [
                b": keepalive\n",
                b"data: {\"event\":\"tool.started\",\n",
                b"data: \"run_id\":\"run_1\"}\n",
                b"\n",
            ]
        )
    )

    assert frames == ['{"event":"tool.started",\n"run_id":"run_1"}']


def test_forward_gateway_run_events_records_privacy_safe_events():
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _FakeSseResponse(
            [
                {
                    "event": "tool.started",
                    "run_id": "run_123",
                    "tool": "shell",
                    "preview": "token=super-secret-value",
                },
                {
                    "event": "run.completed",
                    "run_id": "run_123",
                    "output": "final answer should not be mirrored",
                },
            ]
        )

    count = forward_gateway_run_events(
        "run_123",
        base_url="http://127.0.0.1:8642",
        api_key="sk-secret",
        timeout=2,
        urlopen=fake_urlopen,
    )

    assert count == 2
    request, timeout = requests[0]
    assert request.full_url == "http://127.0.0.1:8642/v1/runs/run_123/events"
    assert request.get_header("Authorization") == "Bearer sk-secret"
    assert timeout == 2

    events = get_recent_run_inspector_events(limit=10)
    assert [event["type"] for event in events] == ["tool.started", "run.completed"]
    assert events[0]["source"] == "gateway_run"
    assert events[0]["tool"] == "shell"
    assert events[0]["message"] is None
    assert events[1]["message"] is None
