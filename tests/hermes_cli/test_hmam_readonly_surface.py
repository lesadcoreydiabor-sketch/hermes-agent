from __future__ import annotations

import json

import pytest


@pytest.fixture()
def auth_client(monkeypatch, tmp_path, _isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_cli.web_server as web_server

    monkeypatch.setattr(web_server, "PROJECT_ROOT", tmp_path)
    client = TestClient(web_server.app)
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    return client


def test_hmam_run_inspector_routes_require_dashboard_auth():
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_cli.web_server as web_server

    client = TestClient(web_server.app)

    for path in (
        "/api/run-inspector",
        "/api/run-inspector/events",
        "/api/run-inspector/memory-workbench",
    ):
        response = client.get(path)
        assert response.status_code == 401


def test_hmam_run_inspector_surface_exposes_only_read_routes():
    import hermes_cli.web_server as web_server

    run_inspector_routes = {
        route.path: set(getattr(route, "methods", set()) or set())
        for route in web_server.app.routes
        if getattr(route, "path", "").startswith("/api/run-inspector")
    }

    assert run_inspector_routes == {
        "/api/run-inspector": {"GET"},
        "/api/run-inspector/events": {"GET"},
        "/api/run-inspector/memory-workbench": {"GET"},
    }


def test_hmam_run_inspector_snapshot_surface_is_metadata_only(auth_client):
    response = auth_client.get("/api/run-inspector")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] in {True, False}
    assert set(payload) == {"ok", "snapshot", "refreshed_at"}

    snapshot = payload["snapshot"]
    assert snapshot["privacy_flags"]
    assert "messages" not in snapshot
    assert "transcript" not in snapshot


def test_hmam_run_inspector_events_surface_is_bounded_metadata(auth_client):
    response = auth_client.get("/api/run-inspector/events?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert set(payload) == {"ok", "events", "refreshed_at"}
    assert isinstance(payload["events"], list)
    assert len(payload["events"]) <= 5


def test_hmam_memory_workbench_source_quality_contract(auth_client):
    response = auth_client.get("/api/run-inspector/memory-workbench?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"ok", "workbench", "refreshed_at"}

    workbench = payload["workbench"]
    assert workbench["privacy_class"] == "redacted_summary"
    assert workbench["source_quality"]["live_sources"] == [
        "/api/run-inspector/memory-workbench"
    ]
    assert workbench["source_quality"]["fixture_sources"] == []
    assert workbench["source_quality"]["privacy_class"] == "redacted_summary"
    assert "vault_signals" in workbench

    sources = workbench["source_quality"]["sources"]
    assert {
        source["family"]
        for source in sources
    } == {
        "action_ledger",
        "long_term_queue",
        "skills_journal",
        "memory_diagnostics",
    }
    for source in sources:
        assert source["privacy_class"] == "redacted_summary"
        assert isinstance(source["degraded_reasons"], list)
        assert isinstance(source["counts"], dict)
        assert isinstance(source["source_refs"], list)

    rendered = json.dumps(payload, sort_keys=True).lower()
    assert "raw_message" not in rendered
    assert "transcript" not in rendered
    assert "access_token" not in rendered
    assert "refresh_token" not in rendered
