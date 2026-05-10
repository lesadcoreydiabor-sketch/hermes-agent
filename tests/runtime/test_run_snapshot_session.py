from hermes_cli.run_inspector import (
    collect_gateway_runtime_snapshot,
    collect_latest_session_snapshot,
    run_snapshot_from_gateway_runtime_status,
    run_snapshot_from_session_record,
)


def test_open_recent_session_maps_to_thinking():
    snapshot = run_snapshot_from_session_record(
        {
            "id": "s-recent",
            "source": "cli",
            "started_at": 1000.0,
            "last_active": 1200.0,
            "ended_at": None,
        },
        now=1250.0,
    ).to_dict()

    assert snapshot["run_id"] == "s-recent"
    assert snapshot["session_id"] == "s-recent"
    assert snapshot["source"] == "cli"
    assert snapshot["status"] == "thinking"
    assert snapshot["last_activity_at"] == "1970-01-01T00:20:00+00:00"
    assert snapshot["privacy_flags"] == ["safe", "local_only"]


def test_open_old_session_maps_to_waiting_input():
    snapshot = run_snapshot_from_session_record(
        {
            "id": "s-idle",
            "source": "telegram",
            "started_at": 1000.0,
            "last_active": 1100.0,
            "ended_at": None,
        },
        now=2000.0,
    ).to_dict()

    assert snapshot["source"] == "gateway"
    assert snapshot["status"] == "waiting_input"


def test_ended_session_maps_reason_to_terminal_state():
    completed = run_snapshot_from_session_record({
        "id": "s-complete",
        "source": "cli",
        "started_at": 1000.0,
        "last_active": 1100.0,
        "ended_at": 1200.0,
        "end_reason": "done",
    }).to_dict()
    failed = run_snapshot_from_session_record({
        "id": "s-failed",
        "source": "cli",
        "started_at": 1000.0,
        "last_active": 1100.0,
        "ended_at": 1200.0,
        "end_reason": "tool_failed",
    }).to_dict()
    stopped = run_snapshot_from_session_record({
        "id": "s-stopped",
        "source": "cli",
        "started_at": 1000.0,
        "last_active": 1100.0,
        "ended_at": 1200.0,
        "end_reason": "user_exit",
    }).to_dict()

    assert completed["status"] == "completed"
    assert completed["reason"] == "done"
    assert failed["status"] == "failed"
    assert stopped["status"] == "stopped"


def test_corrupt_session_state_returns_unknown_with_degraded_reason():
    snapshot = run_snapshot_from_session_record({
        "source": "cli",
        "started_at": "not-a-time",
    }).to_dict()

    assert snapshot["run_id"] == "unknown"
    assert snapshot["status"] == "unknown"
    assert snapshot["degraded_reason"] == "session_record_missing_id"


def test_session_recovery_hint_is_passed_through_safely():
    secret = "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    snapshot = run_snapshot_from_session_record({
        "id": "s-resume",
        "source": "acp",
        "status": "recovering",
        "started_at": 1000.0,
        "last_active": 1100.0,
        "ended_at": None,
        "recovery_hint": f"resume after rotating {secret}",
        "degraded_reason": "resume_pending",
    }).to_dict()

    assert snapshot["source"] == "acp"
    assert snapshot["status"] == "recovering"
    assert snapshot["degraded_reason"] == "resume_pending"
    assert "OPENAI_API_KEY=***" in snapshot["recovery_hint"]
    assert "abcdefghijklmnopqrstuvwxyz" not in snapshot["recovery_hint"]


def test_collect_latest_session_snapshot_reads_and_closes_db():
    events = []

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            events.append(("list", kwargs))
            return [{
                "id": "latest",
                "source": "cli",
                "started_at": 1000.0,
                "last_active": 1200.0,
                "ended_at": None,
            }]

        def close(self):
            events.append(("close", None))

    snapshot = collect_latest_session_snapshot(
        session_db_factory=FakeDB,
        now=1250.0,
    ).to_dict()

    assert snapshot["run_id"] == "latest"
    assert snapshot["status"] == "thinking"
    assert events == [
        ("list", {"limit": 1, "order_by_last_active": True}),
        ("close", None),
    ]


def test_collect_latest_session_snapshot_handles_db_errors():
    class BrokenDB:
        def list_sessions_rich(self, **kwargs):
            raise RuntimeError("database locked")

        def close(self):
            pass

    snapshot = collect_latest_session_snapshot(session_db_factory=BrokenDB).to_dict()

    assert snapshot["status"] == "unknown"
    assert snapshot["degraded_reason"] == "session_state_unavailable:RuntimeError"


def test_gateway_runtime_status_maps_running_and_terminal_states():
    running = run_snapshot_from_gateway_runtime_status({
        "pid": 123,
        "gateway_state": "running",
        "active_agents": 2,
        "updated_at": "2026-05-11T00:00:00+00:00",
    }).to_dict()
    stopped = run_snapshot_from_gateway_runtime_status({
        "pid": 123,
        "gateway_state": "stopped",
        "exit_reason": "planned stop",
    }).to_dict()
    failed = run_snapshot_from_gateway_runtime_status({
        "pid": 123,
        "gateway_state": "startup_failed",
        "exit_reason": "telegram conflict",
    }).to_dict()

    assert running["run_id"] == "gateway:123"
    assert running["source"] == "gateway"
    assert running["status"] == "thinking"
    assert running["last_activity_at"] == "2026-05-11T00:00:00+00:00"
    assert stopped["status"] == "stopped"
    assert stopped["reason"] == "planned stop"
    assert failed["status"] == "failed"


def test_collect_gateway_runtime_snapshot_handles_reader_errors():
    def broken_reader():
        raise OSError("cannot read status")

    snapshot = collect_gateway_runtime_snapshot(
        runtime_status_reader=broken_reader
    ).to_dict()

    assert snapshot["source"] == "gateway"
    assert snapshot["status"] == "unknown"
    assert snapshot["degraded_reason"] == "gateway_state_unavailable:OSError"
