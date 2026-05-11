"""Tests for the first ``hermes desktop`` dashboard shell."""

from __future__ import annotations

import argparse
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli.main import (
    _desktop_dashboard_url,
    _desktop_runtime_record,
    _find_free_desktop_port,
    _find_stale_dashboard_pids,
    _open_browser_url,
    cmd_desktop,
)


def _ns(**kw):
    defaults = dict(port=9119, no_open=False, status=False, stop=False)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _ps_line(pid: int, cmd: str) -> str:
    return f"{pid:>7} {cmd}"


def test_desktop_url_defaults_to_run_inspector():
    assert (
        _desktop_dashboard_url("127.0.0.1", 9119)
        == "http://127.0.0.1:9119/run-inspector"
    )
    assert (
        _desktop_dashboard_url("127.0.0.1", 9119, "run-inspector")
        == "http://127.0.0.1:9119/run-inspector"
    )


def test_desktop_status_reports_route_without_dashboard_deps(capsys):
    orig_import = __import__

    def fake_import(name, *a, **kw):
        if name == "fastapi":
            raise ImportError("fastapi missing")
        return orig_import(name, *a, **kw)

    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value={
            "pid": 12345,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
            "url": "http://127.0.0.1:9119/run-inspector",
            "started_at": "2026-05-11T00:00:00Z",
        },
    ), patch(
        "hermes_cli.main._desktop_runtime_pid_status",
        return_value=(12345, True, "running"),
    ), patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(True, "ok"),
    ), patch(
        "builtins.__import__",
        side_effect=fake_import,
    ), pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(status=True))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "Hermes desktop shell" in out
    assert "PID: 12345 (running)" in out
    assert "URL: http://127.0.0.1:9119/run-inspector" in out
    assert "Health: ok" in out


def test_desktop_status_clears_stale_runtime_record(capsys):
    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value={
            "pid": 99999,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
        },
    ), patch(
        "hermes_cli.main._desktop_runtime_pid_status",
        return_value=(99999, False, "not_found"),
    ), patch(
        "hermes_cli.main._remove_desktop_runtime_record"
    ) as mock_remove, patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(status=True))

    assert exc.value.code == 0
    mock_remove.assert_called_once()
    out = capsys.readouterr().out
    assert "PID: 99999 (stale (not_found))" in out
    assert "Runtime record was stale and has been cleared" in out


def test_desktop_reuses_existing_dashboard_and_opens_run_inspector(capsys):
    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(True, "ok"),
    ), patch("hermes_cli.main._open_browser_url") as mock_open, pytest.raises(
        SystemExit
    ) as exc:
        cmd_desktop(_ns(port=9222))

    assert exc.value.code == 0
    mock_open.assert_called_once_with(
        "http://127.0.0.1:9222/run-inspector",
        delay=0,
    )
    assert (
        "Hermes desktop reusing dashboard: http://127.0.0.1:9222/run-inspector"
        in capsys.readouterr().out
    )


def test_desktop_reuse_respects_no_open():
    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(True, "ok"),
    ), patch("hermes_cli.main._open_browser_url") as mock_open, pytest.raises(
        SystemExit
    ):
        cmd_desktop(_ns(no_open=True))

    mock_open.assert_not_called()


def test_desktop_browser_open_false_prints_manual_fallback(capsys):
    url = "http://127.0.0.1:9119/run-inspector"
    with patch("webbrowser.open", return_value=False):
        assert _open_browser_url(url, delay=0) is False

    out = capsys.readouterr().out
    assert "Hermes desktop browser open failed: browser_open_failed" in out
    assert f"Open manually: {url}" in out
    assert "token=" not in out


def test_desktop_browser_open_exception_prints_detail(capsys):
    url = "http://127.0.0.1:9119/run-inspector"
    with patch("webbrowser.open", side_effect=RuntimeError("no browser")):
        assert _open_browser_url(url, delay=0) is False

    out = capsys.readouterr().out
    assert "Hermes desktop browser open failed: browser_open_failed" in out
    assert f"Open manually: {url}" in out
    assert "RuntimeError: no browser" in out


def test_desktop_start_uses_loopback_dashboard_and_run_inspector(monkeypatch):
    monkeypatch.setenv("HERMES_WEB_DIST", "prebuilt")

    start_calls = []

    def fake_start_server(**kwargs):
        start_calls.append(kwargs)

    fake_ws = MagicMock()
    fake_ws.start_server = fake_start_server

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=False,
    ), patch(
        "hermes_cli.main._open_browser_url"
    ) as mock_open, patch(
        "hermes_cli.main._write_desktop_runtime_record"
    ) as mock_write, patch(
        "hermes_cli.main._clear_desktop_runtime_if_owned"
    ) as mock_clear, patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
            "hermes_cli.web_server": fake_ws,
        },
    ):
        cmd_desktop(_ns(port=9333))

    mock_open.assert_called_once_with("http://127.0.0.1:9333/run-inspector")
    assert mock_write.call_count == 1
    record = mock_write.call_args.args[0]
    assert record["pid"] == os.getpid()
    assert record["host"] == "127.0.0.1"
    assert record["port"] == 9333
    assert record["route"] == "/run-inspector"
    assert record["url"] == "http://127.0.0.1:9333/run-inspector"
    mock_clear.assert_called_once_with(os.getpid())
    assert start_calls == [
        {
            "host": "127.0.0.1",
            "port": 9333,
            "open_browser": False,
            "allow_public": False,
            "embedded_chat": False,
        }
    ]


def test_desktop_start_respects_no_open(monkeypatch):
    monkeypatch.setenv("HERMES_WEB_DIST", "prebuilt")

    fake_ws = MagicMock()
    fake_ws.start_server = lambda **_kwargs: None

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=False,
    ), patch(
        "hermes_cli.main._open_browser_url"
    ) as mock_open, patch(
        "hermes_cli.main._write_desktop_runtime_record"
    ), patch(
        "hermes_cli.main._clear_desktop_runtime_if_owned"
    ), patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
            "hermes_cli.web_server": fake_ws,
        },
    ):
        cmd_desktop(_ns(no_open=True))

    mock_open.assert_not_called()


def test_desktop_runtime_record_is_safe_and_local():
    record = _desktop_runtime_record(host="127.0.0.1", port=9444)
    assert record["version"] == 1
    assert record["pid"] == os.getpid()
    assert record["host"] == "127.0.0.1"
    assert record["url"] == "http://127.0.0.1:9444/run-inspector"
    assert "token" not in record["url"].lower()
    assert record["command"] == "hermes desktop"


def test_desktop_busy_non_dashboard_port_is_degraded(capsys):
    def fake_port_probe(_host, port, **_kwargs):
        return port == 9555

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "http_404"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        side_effect=fake_port_probe,
    ), patch(
        "hermes_cli.main._build_web_ui"
    ) as mock_build, patch(
        "hermes_cli.main._open_browser_url"
    ) as mock_open, pytest.raises(
        SystemExit
    ) as exc:
        cmd_desktop(_ns(port=9555))

    assert exc.value.code == 1
    mock_build.assert_not_called()
    mock_open.assert_not_called()
    out = capsys.readouterr().out
    assert "Hermes desktop startup failed: port_busy" in out
    assert "Port 9555 is already in use" in out
    assert "hermes desktop --port 9556" in out
    assert "Inspect: hermes dashboard --status" in out


def test_desktop_free_port_suggestion_skips_occupied_ports():
    def fake_port_probe(_host, port, **_kwargs):
        return port in {9556, 9557}

    with patch(
        "hermes_cli.main._port_accepts_connections",
        side_effect=fake_port_probe,
    ):
        assert _find_free_desktop_port("127.0.0.1", 9555, attempts=5) == 9558


def test_desktop_dependency_missing_is_classified(capsys):
    orig_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "fastapi":
            raise ImportError("fastapi missing")
        return orig_import(name, *args, **kwargs)

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=False,
    ), patch(
        "hermes_cli.main._build_web_ui"
    ) as mock_build, patch(
        "hermes_cli.main._open_browser_url"
    ) as mock_open, patch(
        "builtins.__import__",
        side_effect=fake_import,
    ), pytest.raises(
        SystemExit
    ) as exc:
        cmd_desktop(_ns(port=9666))

    assert exc.value.code == 1
    mock_build.assert_not_called()
    mock_open.assert_not_called()
    out = capsys.readouterr().out
    assert "Hermes desktop startup failed: dependency_missing" in out
    assert "Web UI dependencies not installed" in out
    assert "fastapi missing" in out


def test_desktop_frontend_build_failure_is_classified(monkeypatch, capsys):
    monkeypatch.delenv("HERMES_WEB_DIST", raising=False)

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=False,
    ), patch(
        "hermes_cli.main._build_web_ui",
        return_value=False,
    ), patch(
        "hermes_cli.main._open_browser_url"
    ) as mock_open, patch(
        "hermes_cli.main._write_desktop_runtime_record"
    ) as mock_write, patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
        },
    ), pytest.raises(
        SystemExit
    ) as exc:
        cmd_desktop(_ns(port=9667))

    assert exc.value.code == 1
    mock_open.assert_not_called()
    mock_write.assert_not_called()
    out = capsys.readouterr().out
    assert "Hermes desktop startup failed: frontend_build_failed" in out
    assert "npm install && npm run build" in out


def test_desktop_server_start_failure_is_classified(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_WEB_DIST", "prebuilt")

    def fake_start_server(**_kwargs):
        raise RuntimeError("bind failed")

    fake_ws = MagicMock()
    fake_ws.start_server = fake_start_server

    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "URLError"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=False,
    ), patch(
        "hermes_cli.main._open_browser_url"
    ), patch(
        "hermes_cli.main._write_desktop_runtime_record"
    ) as mock_write, patch(
        "hermes_cli.main._clear_desktop_runtime_if_owned"
    ) as mock_clear, patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
            "hermes_cli.web_server": fake_ws,
        },
    ), pytest.raises(
        SystemExit
    ) as exc:
        cmd_desktop(_ns(port=9668))

    assert exc.value.code == 1
    mock_write.assert_called_once()
    mock_clear.assert_called_once_with(os.getpid())
    out = capsys.readouterr().out
    assert "Hermes desktop startup failed: server_start_failed" in out
    assert "RuntimeError: bind failed" in out
    assert "hermes desktop --port 9669" in out


def test_desktop_stop_without_runtime_record_is_noop(capsys):
    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value=None,
    ), patch(
        "hermes_cli.main._terminate_desktop_pid"
    ) as mock_terminate, pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(stop=True))

    assert exc.value.code == 0
    mock_terminate.assert_not_called()
    assert "No Hermes desktop shell runtime recorded" in capsys.readouterr().out


def test_desktop_stop_clears_stale_runtime_without_killing(capsys):
    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value={
            "pid": 99999,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
        },
    ), patch(
        "hermes_cli.main._desktop_runtime_pid_status",
        return_value=(99999, False, "not_found"),
    ), patch(
        "hermes_cli.main._remove_desktop_runtime_record"
    ) as mock_remove, patch(
        "hermes_cli.main._terminate_desktop_pid"
    ) as mock_terminate, pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(stop=True))

    assert exc.value.code == 0
    mock_remove.assert_called_once()
    mock_terminate.assert_not_called()
    assert "was stale (not_found) and has been cleared" in capsys.readouterr().out


def test_desktop_stop_only_targets_verified_runtime_pid(capsys):
    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value={
            "pid": 12345,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
        },
    ), patch(
        "hermes_cli.main._desktop_runtime_pid_status",
        return_value=(12345, True, "running"),
    ), patch(
        "hermes_cli.main._terminate_desktop_pid",
        return_value=(True, "stopped"),
    ) as mock_terminate, patch(
        "hermes_cli.main._remove_desktop_runtime_record"
    ) as mock_remove, pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(stop=True))

    assert exc.value.code == 0
    mock_terminate.assert_called_once_with(12345)
    mock_remove.assert_called_once()
    assert "Stopped Hermes desktop shell PID 12345" in capsys.readouterr().out


def test_desktop_stop_keeps_record_when_termination_fails(capsys):
    with patch(
        "hermes_cli.main._read_desktop_runtime_record",
        return_value={
            "pid": 12345,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
        },
    ), patch(
        "hermes_cli.main._desktop_runtime_pid_status",
        return_value=(12345, True, "running"),
    ), patch(
        "hermes_cli.main._terminate_desktop_pid",
        return_value=(False, "access denied"),
    ), patch(
        "hermes_cli.main._remove_desktop_runtime_record"
    ) as mock_remove, pytest.raises(SystemExit) as exc:
        cmd_desktop(_ns(stop=True))

    assert exc.value.code == 1
    mock_remove.assert_not_called()
    out = capsys.readouterr().out
    assert "Failed to stop Hermes desktop shell PID 12345" in out
    assert "runtime record was kept" in out


def test_posix_process_scan_includes_hermes_desktop(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\n".join(
                [
                    _ps_line(os.getpid(), "python3 -m hermes_cli.main desktop"),
                    _ps_line(12345, "hermes desktop --port 9119"),
                    _ps_line(12346, "python3 -m hermes_cli.main dashboard"),
                ]
            )
            + "\n",
            stderr="",
        )
        assert sorted(_find_stale_dashboard_pids()) == [12345, 12346]


def test_windows_process_scan_includes_hermes_desktop(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "CommandLine=python -m hermes_cli.main desktop --port 9119\n"
                "ProcessId=12345\n"
                "CommandLine=python -m hermes_cli.main dashboard --port 9120\n"
                "ProcessId=12346\n"
                f"CommandLine=python -m hermes_cli.main desktop --port 9333\n"
                f"ProcessId={os.getpid()}\n"
            ),
            stderr="",
        )
        assert sorted(_find_stale_dashboard_pids()) == [12345, 12346]
