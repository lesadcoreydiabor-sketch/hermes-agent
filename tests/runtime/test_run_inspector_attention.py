from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hermes_cli.run_inspector import MCPHealthSnapshot, RunSnapshot
from hermes_cli.run_inspector_attention import (
    ATTENTION_ROUTE,
    RunInspectorAttentionSignal,
    attention_signals_for_events,
    attention_signals_for_snapshot,
    build_attention_signals,
    dedupe_attention_signals,
    is_attention_signal_expired,
)


def test_waiting_approval_snapshot_creates_safe_attention_signal():
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    signals = attention_signals_for_snapshot(
        RunSnapshot(
            run_id="run-1",
            session_id="session-1",
            status="waiting_approval",
            reason="approval command: cat C:\\Users\\XQQ\\secret.txt",
            recovery_hint="Approve command with token=super-secret-value",
        ),
        now=now,
    )

    payloads = [signal.to_dict() for signal in signals]
    approval = next(item for item in payloads if item["kind"] == "approval_waiting")
    recovery = next(item for item in payloads if item["kind"] == "recovery_available")

    assert approval == {
        "kind": "approval_waiting",
        "severity": "warning",
        "title": "Approval waiting",
        "body": (
            "A HERMES run is waiting for approval. Open Run Inspector to review "
            "safe details."
        ),
        "route": ATTENTION_ROUTE,
        "run_id": "run-1",
        "session_id": "session-1",
        "timestamp": "2026-05-11T00:00:00+00:00",
        "dedupe_key": "approval_waiting:run-1",
        "ttl_ms": 600000,
        "privacy_class": "redacted_summary",
    }
    assert recovery["kind"] == "recovery_available"
    rendered = json.dumps(payloads, sort_keys=True)
    assert "cat C:" not in rendered
    assert "secret.txt" not in rendered
    assert "super-secret-value" not in rendered


def test_failed_run_and_degraded_mcp_create_separate_signals():
    signals = attention_signals_for_snapshot(
        RunSnapshot(
            run_id="run-2",
            status="failed",
            mcp_health=(
                MCPHealthSnapshot(name="gitnexus", status="degraded"),
                MCPHealthSnapshot(name="filesystem", status="connected"),
                MCPHealthSnapshot(name="browser", status="failed"),
            ),
        ),
        now=datetime(2026, 5, 11, 0, 1, tzinfo=timezone.utc),
    )

    payloads = [signal.to_dict() for signal in signals]

    assert [item["kind"] for item in payloads] == ["run_failed", "mcp_degraded"]
    assert payloads[0]["severity"] == "critical"
    assert payloads[1]["body"] == (
        "2 MCP servers need attention. Open Run Inspector for safe details."
    )


def test_desktop_shell_degraded_signal_from_degraded_reason():
    payloads = [
        signal.to_dict()
        for signal in attention_signals_for_snapshot(
            {
                "run_id": "desktop",
                "status": "unknown",
                "degraded_reason": "desktop_shell port_busy",
            },
            now=datetime(2026, 5, 11, 0, 2, tzinfo=timezone.utc),
        )
    ]

    assert [item["kind"] for item in payloads] == [
        "desktop_shell_degraded",
        "run_degraded",
    ]
    assert all(item["route"] == "/run-inspector" for item in payloads)


def test_events_create_signals_without_raw_approval_payload():
    events = [
        {
            "id": 1,
            "type": "approval.request",
            "source": "gateway_run",
            "timestamp": "2026-05-11T00:03:00Z",
            "run_id": "run-approval",
            "session_id": "session-approval",
            "tool": "shell",
            "status": "waiting",
            "message": (
                "Run this command: cat /home/user/private.txt "
                "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz"
            ),
            "description": "raw approval description should not appear",
            "pattern_keys": ["dangerous-command"],
        },
        {
            "id": 2,
            "type": "run.failed",
            "source": "gateway_run",
            "timestamp": "2026-05-11T00:03:01Z",
            "run_id": "run-failed",
            "message": "Traceback with token=super-secret",
        },
    ]

    payloads = [
        signal.to_dict()
        for signal in attention_signals_for_events(
            events,
            now=datetime(2026, 5, 11, 0, 4, tzinfo=timezone.utc),
        )
    ]

    assert [item["kind"] for item in payloads] == [
        "approval_waiting",
        "run_failed",
    ]
    rendered = json.dumps(payloads, sort_keys=True)
    assert "private.txt" not in rendered
    assert "sk-proj" not in rendered
    assert "raw approval description" not in rendered
    assert "dangerous-command" not in rendered
    assert "Traceback" not in rendered
    assert "super-secret" not in rendered


def test_dedupe_keeps_newest_non_expired_signal_per_key():
    old = RunInspectorAttentionSignal(
        kind="run_failed",
        severity="critical",
        title="Run failed",
        body="Old",
        run_id="run-1",
        timestamp="2026-05-11T00:00:00Z",
    )
    newer = RunInspectorAttentionSignal(
        kind="run_failed",
        severity="critical",
        title="Run failed",
        body="New",
        run_id="run-1",
        timestamp="2026-05-11T00:01:00Z",
    )
    another = RunInspectorAttentionSignal(
        kind="mcp_degraded",
        severity="warning",
        title="MCP degraded",
        body="MCP",
        run_id="run-1",
        timestamp="2026-05-11T00:01:30Z",
    )

    deduped = dedupe_attention_signals(
        [old, newer, another],
        now=datetime(2026, 5, 11, 0, 2, tzinfo=timezone.utc),
    )

    assert [signal.kind for signal in deduped] == ["run_failed", "mcp_degraded"]
    assert deduped[0].body == "New"


def test_expired_signals_are_dropped():
    now = datetime(2026, 5, 11, 0, 10, tzinfo=timezone.utc)
    expired = RunInspectorAttentionSignal(
        kind="run_failed",
        severity="critical",
        title="Run failed",
        body="Expired",
        run_id="run-old",
        timestamp=(now - timedelta(minutes=11)).isoformat(),
        ttl_ms=10 * 60 * 1000,
    )
    fresh = RunInspectorAttentionSignal(
        kind="run_failed",
        severity="critical",
        title="Run failed",
        body="Fresh",
        run_id="run-new",
        timestamp=(now - timedelta(minutes=1)).isoformat(),
        ttl_ms=10 * 60 * 1000,
    )

    assert is_attention_signal_expired(expired, now=now) is True
    assert is_attention_signal_expired(fresh, now=now) is False
    assert dedupe_attention_signals([expired, fresh], now=now) == [fresh]


def test_build_attention_signals_sanitizes_identifiers_route_and_missing_state():
    payloads = build_attention_signals(
        snapshot={
            "run_id": "C:\\Users\\XQQ\\secret-run",
            "session_id": "token=super-secret",
            "status": "failed",
        },
        events=[
            {
                "type": "gateway.forwarder.failed",
                "run_id": "run-forwarder",
                "timestamp": "not-a-date",
                "message": "C:\\Users\\XQQ\\private.log",
            },
            {"not": "a recognized event"},
        ],
        now=datetime(2026, 5, 11, 0, 11, tzinfo=timezone.utc),
    )

    assert [item["kind"] for item in payloads] == ["run_failed", "run_degraded"]
    assert payloads[0]["run_id"] == "redacted"
    assert payloads[0]["session_id"] == "redacted"
    assert all(item["route"] == ATTENTION_ROUTE for item in payloads)
    rendered = json.dumps(payloads, sort_keys=True)
    assert "secret-run" not in rendered
    assert "super-secret" not in rendered
    assert "private.log" not in rendered
