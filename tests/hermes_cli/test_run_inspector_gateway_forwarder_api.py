import pytest

from hermes_cli.run_inspector_gateway_forwarder import (
    clear_gateway_run_event_forwarders_for_tests,
)


@pytest.fixture(autouse=True)
def _clear_forwarders():
    clear_gateway_run_event_forwarders_for_tests()
    yield
    clear_gateway_run_event_forwarders_for_tests()


@pytest.fixture
def run_inspector_gateway_client(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    return client


def test_gateway_forwarder_api_requires_session_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)

    response = client.post("/api/run-inspector/gateway-runs/run_1/follow")

    assert response.status_code == 401


def test_gateway_runs_api_requires_session_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli import web_server

    client = TestClient(web_server.app)

    response = client.get("/api/run-inspector/gateway-runs")

    assert response.status_code == 401


def test_gateway_forwarder_api_requires_config(
    monkeypatch,
    run_inspector_gateway_client,
):
    for name in (
        "HERMES_RUN_INSPECTOR_GATEWAY_URL",
        "HERMES_RUN_INSPECTOR_GATEWAY_KEY",
        "GATEWAY_HEALTH_URL",
        "API_SERVER_ENABLED",
        "API_SERVER_KEY",
        "API_SERVER_HOST",
        "API_SERVER_PORT",
    ):
        monkeypatch.delenv(name, raising=False)

    response = run_inspector_gateway_client.post(
        "/api/run-inspector/gateway-runs/run_1/follow"
    )

    assert response.status_code == 409
    assert "not configured" in response.json()["detail"]


def test_gateway_runs_api_requires_config(
    monkeypatch,
    run_inspector_gateway_client,
):
    for name in (
        "HERMES_RUN_INSPECTOR_GATEWAY_URL",
        "HERMES_RUN_INSPECTOR_GATEWAY_KEY",
        "GATEWAY_HEALTH_URL",
        "API_SERVER_ENABLED",
        "API_SERVER_KEY",
        "API_SERVER_HOST",
        "API_SERVER_PORT",
    ):
        monkeypatch.delenv(name, raising=False)

    response = run_inspector_gateway_client.get("/api/run-inspector/gateway-runs")

    assert response.status_code == 409
    assert "not configured" in response.json()["detail"]


def test_gateway_forwarder_api_starts_background_forwarder(
    monkeypatch,
    run_inspector_gateway_client,
):
    from hermes_cli import web_server

    calls = []

    def fake_start(run_id, **kwargs):
        calls.append((run_id, kwargs))
        return {
            "run_id": run_id,
            "state": "running",
            "gateway_url": "http://127.0.0.1:8642",
            "events_forwarded": 0,
            "last_error": None,
            "already_running": False,
        }

    monkeypatch.setattr(web_server, "resolve_gateway_event_base_url", lambda: "http://127.0.0.1:8642")
    monkeypatch.setattr(web_server, "resolve_gateway_event_api_key", lambda: "sk-secret")
    monkeypatch.setattr(web_server, "start_gateway_run_event_forwarder", fake_start)

    response = run_inspector_gateway_client.post(
        "/api/run-inspector/gateway-runs/run_abc/follow"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["forwarder"]["state"] == "running"
    assert calls == [
        (
            "run_abc",
            {
                "base_url": "http://127.0.0.1:8642",
                "api_key": "sk-secret",
                "timeout": web_server._gateway_event_forwarder_timeout(),
            },
        )
    ]


def test_gateway_runs_api_returns_safe_summaries(
    monkeypatch,
    run_inspector_gateway_client,
):
    from hermes_cli import web_server

    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return [
            {
                "run_id": "run_1",
                "status": "running",
                "created_at": 1.0,
                "updated_at": 2.0,
                "session_id": "session-1",
                "model": "hermes",
                "last_event": "run.running",
                "has_error": False,
            }
        ]

    monkeypatch.setattr(web_server, "resolve_gateway_event_base_url", lambda: "http://127.0.0.1:8642")
    monkeypatch.setattr(web_server, "resolve_gateway_event_api_key", lambda: "sk-secret")
    monkeypatch.setattr(web_server, "fetch_gateway_run_summaries", fake_fetch)

    response = run_inspector_gateway_client.get(
        "/api/run-inspector/gateway-runs?limit=7"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["runs"][0]["run_id"] == "run_1"
    assert calls == [
        {
            "base_url": "http://127.0.0.1:8642",
            "api_key": "sk-secret",
            "limit": 7,
            "timeout": web_server._gateway_event_forwarder_timeout(),
        }
    ]


def test_gateway_forwarder_status_api_returns_null_when_not_following(
    run_inspector_gateway_client,
):
    response = run_inspector_gateway_client.get(
        "/api/run-inspector/gateway-runs/run_missing/follow"
    )

    assert response.status_code == 200
    assert response.json()["forwarder"] is None
