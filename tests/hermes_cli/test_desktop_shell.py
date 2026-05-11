"""Tests for the first ``hermes desktop`` dashboard shell."""

from __future__ import annotations

import argparse
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli.main import (
    _desktop_dashboard_url,
    _find_stale_dashboard_pids,
    cmd_desktop,
)


def _ns(**kw):
    defaults = dict(port=9119, no_open=False, status=False)
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
        "hermes_cli.main._find_stale_dashboard_pids",
        return_value=[12345],
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
    assert "1 Hermes dashboard/desktop process(es) running" in out
    assert "PID 12345" in out
    assert "Hermes desktop route: http://127.0.0.1:9119/run-inspector" in out


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
    ) as mock_open, patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
            "hermes_cli.web_server": fake_ws,
        },
    ):
        cmd_desktop(_ns(port=9333))

    mock_open.assert_called_once_with("http://127.0.0.1:9333/run-inspector")
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
    ) as mock_open, patch.dict(
        sys.modules,
        {
            "fastapi": MagicMock(),
            "uvicorn": MagicMock(),
            "hermes_cli.web_server": fake_ws,
        },
    ):
        cmd_desktop(_ns(no_open=True))

    mock_open.assert_not_called()


def test_desktop_busy_non_dashboard_port_is_degraded(capsys):
    with patch(
        "hermes_cli.main._probe_dashboard_status",
        return_value=(False, "http_404"),
    ), patch(
        "hermes_cli.main._port_accepts_connections",
        return_value=True,
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
    assert "Port 9555 is already in use" in out
    assert "hermes desktop --port <free-port>" in out


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
