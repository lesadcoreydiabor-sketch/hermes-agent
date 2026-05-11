from __future__ import annotations

import json
from unittest.mock import patch

from hermes_cli.desktop_shell_status import (
    build_desktop_status_payload,
    desktop_operator_next_action,
)


def test_desktop_operator_next_action_classifies_safe_actions() -> None:
    assert desktop_operator_next_action(
        record_present=True,
        pid_status="running",
        health_ok=True,
        compatible_dashboard=False,
        port=9119,
    ) == ("Open Run Inspector", None, "ok")
    assert desktop_operator_next_action(
        record_present=False,
        pid_status="none",
        health_ok=True,
        compatible_dashboard=True,
        port=9222,
    ) == ("Reuse compatible dashboard", "hermes desktop --port 9222", "info")
    assert desktop_operator_next_action(
        record_present=True,
        pid_status="stale",
        health_ok=False,
        compatible_dashboard=False,
        port=9333,
    ) == ("Restart desktop shell", "hermes desktop --port 9333", "warning")
    assert desktop_operator_next_action(
        record_present=False,
        pid_status="none",
        health_ok=False,
        compatible_dashboard=False,
        port=9444,
    ) == ("Start desktop shell", "hermes desktop --port 9444", "info")


def test_desktop_status_payload_exposes_reuse_next_action() -> None:
    with patch(
        "hermes_cli.desktop_shell_status.read_desktop_runtime_record",
        return_value=None,
    ), patch(
        "hermes_cli.desktop_shell_status.probe_dashboard_status",
        return_value=(True, "ok"),
    ):
        payload = build_desktop_status_payload(port=9222)

    assert payload["attention_level"] == "info"
    assert payload["next_action"] == "Reuse compatible dashboard"
    assert payload["next_command"] == "hermes desktop --port 9222"
    assert payload["reuse_command"] == "hermes desktop --port 9222"
    assert "token=" not in json.dumps(payload)


def test_desktop_status_payload_exposes_stale_next_action() -> None:
    with patch(
        "hermes_cli.desktop_shell_status.read_desktop_runtime_record",
        return_value={
            "pid": 99999,
            "host": "127.0.0.1",
            "port": 9119,
            "route": "/run-inspector",
        },
    ), patch(
        "hermes_cli.desktop_shell_status.probe_dashboard_status",
        return_value=(False, "URLError"),
    ):
        payload = build_desktop_status_payload(
            pid_status_fn=lambda _record: (99999, False, "not_found"),
            port=9119,
        )

    assert payload["attention_level"] == "warning"
    assert payload["next_action"] == "Restart desktop shell"
    assert payload["next_command"] == "hermes desktop --port 9119"
    assert payload["stop_command"] == "hermes desktop --port 9119 --stop"
    assert "token=" not in json.dumps(payload)
