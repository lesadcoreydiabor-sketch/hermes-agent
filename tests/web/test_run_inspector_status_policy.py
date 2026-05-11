import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"


def run_policy_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/hooks/runInspectorStatusPolicy.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorStatusPolicy.js" }});
const policy = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_view_model_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorViewModel.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorViewModel.js" }});
const viewModel = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_event_timeline_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorEventTimeline.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorEventTimeline.js" }});
const timeline = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_attention_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorAttention.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorAttention.js" }});
const attention = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_desktop_status_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorDesktopStatus.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorDesktopStatus.js" }});
const desktopStatus = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_memory_workbench_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorMemoryWorkbench.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorMemoryWorkbench.js" }});
const workbench = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_gateway_controls_script(script: str) -> dict:
    node_script = f"""
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const source = fs.readFileSync("src/pages/runInspectorGatewayControls.ts", "utf8");
const output = ts.transpileModule(source, {{
  compilerOptions: {{
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  }},
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const sandbox = {{ module: moduleRef, exports: moduleRef.exports, require, console }};
vm.runInNewContext(output, sandbox, {{ filename: "runInspectorGatewayControls.js" }});
const controls = moduleRef.exports;
{script}
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=WEB_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_run_inspector_policy_derives_loaded_states():
    payload = run_policy_script(
        textwrap.dedent(
            """
            const baseSnapshot = {
              version: 1,
              run_id: "run-1",
              source: "cli",
              status: "thinking",
              reason: null,
              workspace: null,
              session_id: null,
              last_activity_at: null,
              active_tool: {
                name: null,
                call_id: null,
                duration_ms: null,
                args_summary: null,
              },
              tool_health: [],
              mcp_health: [],
              recovery_hint: null,
              privacy_flags: ["safe"],
              degraded_reason: null,
            };
            const states = {
              ready: policy.deriveRunInspectorState({
                ok: true,
                snapshot: baseSnapshot,
                refreshed_at: "2026-05-11T00:00:00Z",
              }),
              unknown: policy.deriveRunInspectorState({
                ok: true,
                snapshot: { ...baseSnapshot, status: "unknown" },
                refreshed_at: "2026-05-11T00:00:00Z",
              }),
              degraded: policy.deriveRunInspectorState({
                ok: false,
                snapshot: { ...baseSnapshot, degraded_reason: "collector_failed" },
                refreshed_at: "2026-05-11T00:00:00Z",
              }),
            };
            console.log(JSON.stringify(states));
            """
        )
    )

    assert payload == {
        "ready": "ready",
        "unknown": "unknown",
        "degraded": "degraded",
    }


def test_run_inspector_policy_classifies_errors_and_stops_auth_polling():
    payload = run_policy_script(
        textwrap.dedent(
            """
            const states = {
              unauthorized: policy.classifyRunInspectorError(
                new Error("401: Unauthorized"),
              ),
              forbidden: policy.classifyRunInspectorError("403: Forbidden"),
              aborted: policy.classifyRunInspectorError({ name: "AbortError" }),
              network: policy.classifyRunInspectorError(
                new Error("Failed to fetch"),
              ),
              unexpected: policy.classifyRunInspectorError(
                new Error("collector failed"),
              ),
              stopAuth: policy.shouldStopRunInspectorPolling("auth_failed"),
              stopOffline: policy.shouldStopRunInspectorPolling("offline"),
            };
            console.log(JSON.stringify(states));
            """
        )
    )

    assert payload == {
        "unauthorized": "auth_failed",
        "forbidden": "auth_failed",
        "aborted": "offline",
        "network": "offline",
        "unexpected": "degraded",
        "stopAuth": True,
        "stopOffline": False,
    }


def test_run_inspector_policy_backs_off_with_cap():
    payload = run_policy_script(
        textwrap.dedent(
            """
            const delays = [
              policy.nextRunInspectorDelayMs(0, 5000, 60000),
              policy.nextRunInspectorDelayMs(1, 5000, 60000),
              policy.nextRunInspectorDelayMs(2, 5000, 60000),
              policy.nextRunInspectorDelayMs(4, 5000, 60000),
            ];
            console.log(JSON.stringify({ delays }));
            """
        )
    )

    assert payload == {"delays": [5000, 10000, 20000, 60000]}


def test_run_inspector_view_model_formats_safe_argument_summary():
    payload = run_view_model_script(
        textwrap.dedent(
            """
            const summary = viewModel.formatArgsSummary({
              type: "object",
              key_count: 8,
              keys: ["command", "token", "path", "mode", "cwd", "timeout", "extra"],
              value_types: {
                command: "string",
                token: "string",
              },
              privacy: "redacted",
              truncated: true,
            });
            console.log(JSON.stringify({ summary }));
            """
        )
    )

    assert payload == {
        "summary": "object - 8 keys - keys: command, token, path, mode, cwd, timeout - truncated",
    }


def test_run_inspector_view_model_redacts_and_truncates_display_values():
    payload = run_view_model_script(
        textwrap.dedent(
            """
            const longValue = "workspace-" + "x".repeat(240);
            const values = {
              fallback: viewModel.formatDisplayValue("", "None"),
              normal: viewModel.formatDisplayValue("safe workspace"),
              token: viewModel.formatDisplayValue("token=super-secret-value"),
              apiKey: viewModel.formatDisplayValue("api_key:abc123456789"),
              openaiKey: viewModel.formatDisplayValue("sk-proj-abcdef1234567890"),
              longValue: viewModel.formatDisplayValue(longValue),
            };
            console.log(JSON.stringify(values));
            """
        )
    )

    assert payload["fallback"] == "None"
    assert payload["normal"] == "safe workspace"
    assert payload["token"] == "Redacted"
    assert payload["apiKey"] == "Redacted"
    assert payload["openaiKey"] == "Redacted"
    assert payload["longValue"].endswith("...")
    assert len(payload["longValue"]) <= 160


def test_run_inspector_view_model_counts_health_and_describes_state():
    payload = run_view_model_script(
        textwrap.dedent(
            """
            const toolCounts = viewModel.countToolHealth([
              { status: "available" },
              { status: "available" },
              { status: "failed" },
              { status: "unknown" },
            ]);
            const mcpCounts = viewModel.countMcpHealth([
              { status: "connected" },
              { status: "degraded" },
              { status: "failed" },
            ]);
            const state = viewModel.describeRunInspectorState("degraded", {
              status: "executing_tool",
            });
            console.log(JSON.stringify({ toolCounts, mcpCounts, state }));
            """
        )
    )

    assert payload["toolCounts"] == {
        "available": 2,
        "unavailable": 0,
        "running": 0,
        "failed": 1,
        "unknown": 1,
    }
    assert payload["mcpCounts"] == {
        "connected": 1,
        "degraded": 1,
        "failed": 1,
        "unknown": 0,
    }
    assert payload["state"] == {"label": "Executing tool", "tone": "warning"}


def test_run_inspector_view_model_maps_sidebar_signal_states():
    payload = run_view_model_script(
        textwrap.dedent(
            """
            const signals = {
              running: viewModel.deriveSidebarRunInspectorSignal("ready", {
                status: "executing_tool",
                degraded_reason: null,
              }),
              waiting: viewModel.deriveSidebarRunInspectorSignal("ready", {
                status: "waiting_approval",
                degraded_reason: null,
              }),
              failed: viewModel.deriveSidebarRunInspectorSignal("ready", {
                status: "failed",
                degraded_reason: null,
              }),
              degraded: viewModel.deriveSidebarRunInspectorSignal("degraded", {
                status: "thinking",
                degraded_reason: "mcp_unavailable",
              }),
              unavailable: viewModel.deriveSidebarRunInspectorSignal("auth_failed", null),
              unknown: viewModel.deriveSidebarRunInspectorSignal("loading", null),
            };
            console.log(JSON.stringify(signals));
            """
        )
    )

    assert payload["running"]["state"] == "running"
    assert payload["running"]["label"] == "Running"
    assert payload["waiting"]["state"] == "waiting"
    assert payload["failed"]["tone"] == "destructive"
    assert payload["degraded"] == {
        "state": "degraded",
        "label": "Degraded",
        "tone": "warning",
        "title": "mcp_unavailable",
    }
    assert payload["unavailable"]["state"] == "unavailable"
    assert payload["unknown"]["state"] == "unknown"


def test_sessions_and_chat_expose_run_inspector_entry_points() -> None:
    sessions_page = (
        ROOT / "web" / "src" / "pages" / "SessionsPage.tsx"
    ).read_text(encoding="utf-8")
    chat_page = (
        ROOT / "web" / "src" / "pages" / "ChatPage.tsx"
    ).read_text(encoding="utf-8")

    assert 'to="/run-inspector"' in sessions_page
    assert 'to="/run-inspector"' in chat_page
    assert "Open Run Inspector diagnostics" in sessions_page
    assert "Open Run Inspector diagnostics" in chat_page


def test_run_inspector_hook_has_timeout_refresh_and_auth_stop_guards() -> None:
    hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorStatus.ts"
    ).read_text(encoding="utf-8")

    assert "new AbortController()" in hook_source
    assert "setTimeout(() => controller.abort(), timeoutMs)" in hook_source
    assert "setRefreshVersion((value) => value + 1)" in hook_source
    assert "shouldStopRunInspectorPolling(state)" in hook_source
    assert "nextRunInspectorDelayMs(failureCount, pollMs, maxBackoffMs)" in hook_source


def test_run_inspector_page_uses_safe_display_and_overflow_guards() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")

    assert "formatDisplayValue(message" in page_source
    assert "formatDisplayValue(snapshot?.workspace" in page_source
    assert "formatDisplayValue(tool?.name" in page_source
    assert "formatDisplayValue(mcpDetail(item))" in page_source
    assert "break-all" in page_source
    assert "break-words" in page_source
    assert "truncate" in page_source
    assert "min-w-0" in page_source


def test_run_inspector_page_exposes_gateway_follow_without_gateway_secret() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")
    api_source = (ROOT / "web" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert "Gateway Run Follow" in page_source
    assert "api.launchGatewayRun" in page_source
    assert "api.stopGatewayRun" in page_source
    assert "api.respondGatewayRunApproval" in page_source
    assert "api.getGatewayRuns" in page_source
    assert "api.followGatewayRunEvents" in page_source
    assert "api.getGatewayRunEventForwarder" in page_source
    assert "describeGatewayRunDetail" in page_source
    assert "describeGatewayRunList" in page_source
    assert "describeGatewayRunControlState" in page_source
    assert "findLatestPendingApprovalRunId" in page_source
    assert "gatewayRunFilter" in page_source
    assert "gatewayRunSelectionMode" in page_source
    assert "pendingApprovalRunId" in page_source
    assert "handleGatewayRunIdChange" in page_source
    assert "controlState.approvalPending" in page_source
    assert "controlState.approvalDetail" in page_source
    assert "controlState.stopHighlighted" in page_source
    assert 'aria-label="Gateway launch input"' in page_source
    assert 'aria-label="Gateway run id"' in page_source
    assert "Runs" in page_source
    assert "Allow" in page_source
    assert "Deny" in page_source
    assert "Stop" in page_source
    assert "Selected Run" in page_source
    assert "Needs action" in page_source
    assert "Done" in page_source
    assert "Last Detail" in page_source
    assert "Pending request" in page_source
    assert "HERMES_RUN_INSPECTOR_GATEWAY_KEY" not in page_source
    assert "HERMES_RUN_INSPECTOR_GATEWAY_KEY" not in api_source


def test_run_inspector_frontend_slice_avoids_unix_shell_assumptions() -> None:
    paths = [
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx",
        ROOT / "web" / "src" / "pages" / "runInspectorViewModel.ts",
        ROOT / "web" / "src" / "hooks" / "useRunInspectorStatus.ts",
        ROOT / "web" / "src" / "hooks" / "runInspectorStatusPolicy.ts",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "/bin/bash" not in combined
    assert "bash -n" not in combined


def test_run_inspector_event_timeline_merges_dedupes_and_caps():
    payload = run_event_timeline_script(
        textwrap.dedent(
            """
            const base = [
              { id: 1, type: "tool.started", source: "dashboard_chat", timestamp: "2026-05-11T00:00:00Z", run_id: null, session_id: null, tool: "shell", status: "running", message: null },
              { id: 2, type: "tool.progress", source: "dashboard_chat", timestamp: "2026-05-11T00:00:01Z", run_id: null, session_id: null, tool: "shell", status: "running", message: "working" },
            ];
            const incoming = [
              { id: 2, type: "tool.progress", source: "dashboard_chat", timestamp: "2026-05-11T00:00:01Z", run_id: null, session_id: null, tool: "shell", status: "running", message: "updated" },
              { id: 3, type: "tool.completed", source: "dashboard_chat", timestamp: "2026-05-11T00:00:02Z", run_id: null, session_id: null, tool: "shell", status: "completed", message: "done" },
            ];
            const events = timeline.mergeRunInspectorEvents(base, incoming, 2);
            console.log(JSON.stringify({ events }));
            """
        )
    )

    assert [event["id"] for event in payload["events"]] == [2, 3]
    assert payload["events"][0]["message"] == "updated"


def test_run_inspector_event_timeline_describes_event_and_stream_states():
    payload = run_event_timeline_script(
        textwrap.dedent(
            """
            const failed = timeline.describeRunInspectorEvent({
              id: 1,
              type: "tool.completed",
              source: "dashboard_chat",
              timestamp: "2026-05-11T00:00:00Z",
              run_id: null,
              session_id: null,
              tool: "shell",
              status: "failed",
              message: "Redacted",
            });
            const connected = timeline.describeRunInspectorEventStream("connected");
            const auth = timeline.describeRunInspectorEventStream("auth_failed");
            const forwarder = timeline.describeRunInspectorEvent({
              id: 2,
              type: "gateway.forwarder.started",
              source: "run_inspector",
              timestamp: "2026-05-11T00:00:00Z",
              run_id: "run_1",
              session_id: null,
              tool: null,
              status: "running",
              message: null,
            });
            const unknownType = timeline.describeRunInspectorEvent({
              id: 22,
              type: "approval.responded",
              source: "gateway_run",
              timestamp: "2026-05-11T00:00:00Z",
              run_id: "run_1",
              session_id: null,
              tool: null,
              status: "running",
              message: null,
            });
            const context = timeline.describeRunInspectorEventContext({
              id: 3,
              type: "approval.request",
              source: "gateway_run",
              timestamp: "2026-05-11T00:00:00Z",
              run_id: "run_1",
              session_id: "session_1",
              tool: "shell",
              status: "waiting",
              message: null,
            });
            const emptyContext = timeline.describeRunInspectorEventContext({
              id: 4,
              type: "run.completed",
              source: "gateway_run",
              timestamp: "2026-05-11T00:00:00Z",
              run_id: null,
              session_id: null,
              tool: null,
              status: "completed",
              message: null,
            });
            const events = [
              { id: 5, type: "tool.progress", source: "dashboard_chat", timestamp: "2026-05-11T00:00:00Z", run_id: null, session_id: null, tool: "shell", status: "running", message: "working" },
              { id: 6, type: "approval.request", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_wait", session_id: null, tool: null, status: "waiting", message: null },
              { id: 7, type: "run.failed", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_fail", session_id: null, tool: null, status: "failed", message: null },
              { id: 8, type: "gateway.forwarder.started", source: "run_inspector", timestamp: "2026-05-11T00:00:00Z", run_id: "run_forward", session_id: null, tool: null, status: "running", message: null },
              { id: 9, type: "run.cancelled", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_cancel", session_id: null, tool: null, status: "cancelled", message: null },
              { id: 10, type: "run.completed", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_done", session_id: null, tool: null, status: "completed", message: null },
            ];
            const filters = {
              all: timeline.filterRunInspectorEvents(events, "all").map((event) => event.id),
              active: timeline.filterRunInspectorEvents(events, "active").map((event) => event.id),
              attention: timeline.filterRunInspectorEvents(events, "attention").map((event) => event.id),
              approval: timeline.filterRunInspectorEvents(events, "approval").map((event) => event.id),
              cancelled: timeline.filterRunInspectorEvents(events, "cancelled").map((event) => event.id),
              completed: timeline.filterRunInspectorEvents(events, "completed").map((event) => event.id),
              failed: timeline.filterRunInspectorEvents(events, "failed").map((event) => event.id),
              terminal: timeline.filterRunInspectorEvents(events, "terminal").map((event) => event.id),
              gateway: timeline.filterRunInspectorEvents(events, "gateway").map((event) => event.id),
              run: timeline.filterRunInspectorEvents(events, "run").map((event) => event.id),
              tool: timeline.filterRunInspectorEvents(events, "tool").map((event) => event.id),
            };
            const summary = timeline.summarizeRunInspectorEvents(events);
            const emptyStates = {
              allEmpty: timeline.describeRunInspectorEventEmptyState(0, "all"),
              terminalEmpty: timeline.describeRunInspectorEventEmptyState(events.length, "terminal"),
            };
            const labels = {
              all: timeline.runInspectorEventFilterLabel("all"),
              attention: timeline.runInspectorEventFilterLabel("attention"),
              terminal: timeline.runInspectorEventFilterLabel("terminal"),
            };
            console.log(JSON.stringify({ failed, connected, auth, forwarder, unknownType, context, emptyContext, filters, summary, emptyStates, labels }));
            """
        )
    )

    assert payload["failed"] == {
        "label": "Tool completed",
        "tone": "destructive",
        "message": "Redacted",
    }
    assert payload["connected"]["tone"] == "success"
    assert payload["auth"]["tone"] == "destructive"
    assert payload["forwarder"] == {
        "label": "Gateway forwarder started",
        "tone": "primary",
        "message": "running",
    }
    assert payload["unknownType"] == {
        "label": "Approval responded",
        "tone": "primary",
        "message": "running",
    }
    assert payload["context"] == "run=run_1 / session=session_1 / tool=shell"
    assert payload["emptyContext"] == ""
    assert payload["filters"] == {
        "all": [5, 6, 7, 8, 9, 10],
        "active": [5, 8],
        "attention": [6, 7],
        "approval": [6],
        "cancelled": [9],
        "completed": [10],
        "failed": [7],
        "terminal": [7, 9, 10],
        "gateway": [6, 7, 8, 9, 10],
        "run": [7, 9, 10],
        "tool": [5],
    }
    assert payload["summary"] == {
        "active": 2,
        "attention": 2,
        "approval": 1,
        "cancelled": 1,
        "completed": 1,
        "failed": 1,
        "latest": {
            "id": 10,
            "type": "run.completed",
            "source": "gateway_run",
            "timestamp": "2026-05-11T00:00:00Z",
            "run_id": "run_done",
            "session_id": None,
            "tool": None,
            "status": "completed",
            "message": None,
        },
        "terminal": 3,
        "total": 6,
    }
    assert payload["emptyStates"] == {
        "allEmpty": "No recent events",
        "terminalEmpty": "No done events",
    }
    assert payload["labels"] == {
        "all": "All",
        "attention": "Needs action",
        "terminal": "Done",
    }


def test_run_inspector_attention_preview_describes_states_and_tones():
    payload = run_attention_script(
        textwrap.dedent(
            """
            const criticalSignal = {
              kind: "run_failed",
              severity: "critical",
              title: "Run failed",
              body: "Safe failure summary",
              route: "/run-inspector",
              run_id: "run_1",
              session_id: null,
              timestamp: "2026-05-11T00:00:00Z",
              dedupe_key: "run_failed:run_1",
              ttl_ms: 600000,
              privacy_class: "redacted_summary",
            };
            const warningSignal = {
              ...criticalSignal,
              kind: "approval_waiting",
              severity: "warning",
              title: "Approval waiting",
              dedupe_key: "approval_waiting:run_1",
            };
            const states = {
              empty: attention.describeAttentionPreview("ready", []),
              critical: attention.describeAttentionPreview("ready", [warningSignal, criticalSignal]),
              degraded: attention.describeAttentionPreview("degraded", [], "attention_api_failed"),
              auth: attention.describeAttentionPreview("auth_failed", []),
              toneCritical: attention.attentionSignalTone(criticalSignal),
              toneWarning: attention.attentionSignalTone(warningSignal),
            };
            console.log(JSON.stringify(states));
            """
        )
    )

    assert payload["empty"] == {
        "label": "No signals",
        "message": "No current attention signals",
        "tone": "success",
    }
    assert payload["critical"] == {
        "label": "2 signals",
        "message": "Attention needed",
        "tone": "destructive",
    }
    assert payload["degraded"] == {
        "label": "Attention degraded",
        "message": "attention_api_failed",
        "tone": "warning",
    }
    assert payload["auth"]["tone"] == "destructive"
    assert payload["toneCritical"] == "destructive"
    assert payload["toneWarning"] == "warning"


def test_run_inspector_browser_notification_policy_requires_opt_in_and_dedupes():
    payload = run_attention_script(
        textwrap.dedent(
            """
            const signal = {
              kind: "run_failed",
              severity: "critical",
              title: "Run failed",
              body: "Safe failure summary",
              route: "/run-inspector?token=secret",
              run_id: "run_1",
              session_id: null,
              timestamp: "2026-05-11T00:00:00Z",
              dedupe_key: "run_failed:run_1",
              ttl_ms: 600000,
              privacy_class: "redacted_summary",
            };
            const nowMs = Date.parse("2026-05-11T00:01:00Z");
            const states = {
              disabled: attention.describeBrowserNotificationOptIn({
                enabled: false,
                permission: "default",
              }),
              enabled: attention.describeBrowserNotificationOptIn({
                deliveredCount: 2,
                enabled: true,
                permission: "granted",
              }),
              denied: attention.describeBrowserNotificationOptIn({
                enabled: false,
                permission: "denied",
              }),
              unsupported: attention.describeBrowserNotificationOptIn({
                enabled: false,
                permission: "unsupported",
              }),
              degraded: attention.describeBrowserNotificationOptIn({
                enabled: true,
                error: "delivery_failed",
                permission: "granted",
              }),
            };
            const deliverable = {
              fresh: attention.isAttentionSignalDeliverable(signal, { nowMs }),
              duplicate: attention.isAttentionSignalDeliverable(signal, {
                deliveredExpiresAt: nowMs + 1000,
                nowMs,
              }),
              expired: attention.isAttentionSignalDeliverable(signal, {
                nowMs: Date.parse("2026-05-11T00:20:00Z"),
              }),
              expiresAt: attention.attentionSignalExpiresAt(signal),
            };
            const safePayload = attention.safeNotificationPayload(signal);
            console.log(JSON.stringify({ states, deliverable, safePayload }));
            """
        )
    )

    assert payload["states"]["disabled"] == {
        "label": "Notifications off",
        "message": "Enable manually",
        "state": "disabled",
        "tone": "muted",
    }
    assert payload["states"]["enabled"] == {
        "label": "Notifications on",
        "message": "2 delivered this session",
        "state": "enabled",
        "tone": "success",
    }
    assert payload["states"]["denied"]["state"] == "blocked"
    assert payload["states"]["unsupported"]["state"] == "unsupported"
    assert payload["states"]["degraded"]["state"] == "degraded"
    assert payload["deliverable"] == {
        "fresh": True,
        "duplicate": False,
        "expired": False,
        "expiresAt": 1778458200000,
    }
    assert payload["safePayload"] == {
        "body": "Safe failure summary",
        "route": "/run-inspector",
        "tag": "run_failed:run_1",
        "title": "Run failed",
    }


def test_run_inspector_desktop_shell_status_describes_states():
    payload = run_desktop_status_script(
        textwrap.dedent(
            """
            const baseStatus = {
              ok: true,
              record_present: true,
              runtime_record_cleared: false,
              pid: 12345,
              pid_status: "running",
              pid_reason: "running",
              host: "127.0.0.1",
              port: 9119,
              route: "/run-inspector",
              url: "http://127.0.0.1:9119/run-inspector",
              started_at: "2026-05-11T00:00:00Z",
              health: "ok",
              health_reason: "ok",
              compatible_dashboard: false,
              reuse_command: null,
              manual_url: null,
              stop_command: "hermes desktop --port 9119 --stop",
            };
            const states = {
              running: desktopStatus.describeDesktopShellStatus("ready", baseStatus),
              headerRunning: desktopStatus.describeDesktopShellHeaderSignal("ready", baseStatus),
              compatible: desktopStatus.describeDesktopShellStatus("ready", {
                ...baseStatus,
                record_present: false,
                pid: null,
                pid_status: "none",
                pid_reason: "no_record",
                compatible_dashboard: true,
                reuse_command: "hermes desktop --port 9119",
                manual_url: "http://127.0.0.1:9119/run-inspector",
                stop_command: "hermes dashboard --stop",
              }),
              headerCompatible: desktopStatus.describeDesktopShellHeaderSignal("ready", {
                ...baseStatus,
                record_present: false,
                pid: null,
                pid_status: "none",
                pid_reason: "no_record",
                compatible_dashboard: true,
                reuse_command: "hermes desktop --port 9119",
                manual_url: "http://127.0.0.1:9119/run-inspector",
                stop_command: "hermes dashboard --stop",
              }),
              stale: desktopStatus.describeDesktopShellStatus("ready", {
                ...baseStatus,
                pid_status: "stale",
                pid_reason: "not_found",
              }),
              headerStale: desktopStatus.describeDesktopShellHeaderSignal("ready", {
                ...baseStatus,
                pid_status: "stale",
                pid_reason: "not_found",
              }),
              offline: desktopStatus.describeDesktopShellStatus("offline", null),
              headerOffline: desktopStatus.describeDesktopShellHeaderSignal("offline", null),
            };
            console.log(JSON.stringify(states));
            """
        )
    )

    assert payload["running"] == {
        "label": "Desktop shell running",
        "message": "Shell-owned dashboard",
        "tone": "success",
    }
    assert payload["headerRunning"] == {
        "label": "Desktop OK",
        "message": "Shell-owned dashboard",
        "tone": "success",
    }
    assert payload["compatible"] == {
        "label": "Dashboard reusable",
        "message": "No desktop runtime record",
        "tone": "primary",
    }
    assert payload["headerCompatible"] == {
        "label": "Desktop reuse",
        "message": "No desktop runtime record",
        "tone": "primary",
    }
    assert payload["stale"] == {
        "label": "Desktop record stale",
        "message": "not_found",
        "tone": "warning",
    }
    assert payload["headerStale"] == {
        "label": "Desktop attention",
        "message": "not_found",
        "tone": "warning",
    }
    assert payload["offline"]["tone"] == "destructive"
    assert payload["headerOffline"]["label"] == "Desktop offline"
    assert payload["headerOffline"]["tone"] == "destructive"


def test_run_inspector_gateway_controls_follow_run_state_and_events():
    payload = run_gateway_controls_script(
        textwrap.dedent(
            """
            const baseRun = {
              run_id: "run_1",
              status: "running",
              created_at: 1,
              updated_at: 2,
              session_id: null,
              model: null,
              last_event: "run.running",
              has_error: false,
            };
            const running = controls.describeGatewayRunControlState({
              runId: "run_1",
              recentRuns: [baseRun],
              events: [],
            });
            const approvalPending = controls.describeGatewayRunControlState({
              runId: "run_1",
              recentRuns: [{ ...baseRun, status: "waiting_for_approval", last_event: "approval.request" }],
              events: [
                { id: 1, type: "approval.request", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_1", session_id: null, tool: "shell", status: "waiting", message: "approval requested" },
              ],
            });
            const approvalCleared = controls.describeGatewayRunControlState({
              runId: "run_1",
              recentRuns: [{ ...baseRun, status: "waiting_for_approval", last_event: "approval.request" }],
              events: [
                { id: 1, type: "approval.request", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_1", session_id: null, tool: null, status: "waiting", message: null },
                { id: 2, type: "approval.responded", source: "gateway_run", timestamp: "2026-05-11T00:00:01Z", run_id: "run_1", session_id: null, tool: null, status: "running", message: null },
              ],
            });
            const completed = controls.describeGatewayRunControlState({
              runId: "run_1",
              recentRuns: [{ ...baseRun, status: "completed", last_event: "run.completed" }],
              events: [],
            });
            console.log(JSON.stringify({ running, approvalPending, approvalCleared, completed }));
            """
        )
    )

    assert payload["running"]["stopHighlighted"] is True
    assert payload["running"]["approvalPending"] is False
    assert payload["approvalPending"]["approvalHighlighted"] is True
    assert payload["approvalPending"]["approvalPending"] is True
    assert payload["approvalPending"]["approvalDetail"] == {
        "message": "approval requested",
        "status": "waiting",
        "timestamp": "2026-05-11T00:00:00Z",
        "tool": "shell",
    }
    assert payload["approvalCleared"]["approvalPending"] is False
    assert payload["approvalCleared"]["approvalDetail"] is None
    assert payload["completed"]["stopAvailable"] is False


def test_run_inspector_gateway_controls_auto_selects_pending_approval():
    payload = run_gateway_controls_script(
        textwrap.dedent(
            """
            const event = (id, type, runId, timestamp = `2026-05-11T00:00:0${id}Z`) => ({
              id,
              type,
              source: "gateway_run",
              timestamp,
              run_id: runId,
              session_id: null,
              tool: "shell",
              status: type === "approval.responded" ? "running" : "waiting",
              message: null,
            });
            const recentRun = (run_id, status, updated_at) => ({
              run_id,
              status,
              created_at: updated_at - 10,
              updated_at,
              session_id: null,
              model: null,
              last_event: status === "waiting_for_approval" ? "approval.request" : "run.running",
              has_error: false,
            });
            const latestFromEvents = controls.findLatestPendingApprovalRunId({
              selectedRunId: "",
              recentRuns: [],
              events: [
                event(1, "approval.request", "run_1"),
                event(2, "approval.request", "run_2"),
              ],
            });
            const clearedLatest = controls.findLatestPendingApprovalRunId({
              selectedRunId: "",
              recentRuns: [],
              events: [
                event(1, "approval.request", "run_1"),
                event(2, "approval.request", "run_2"),
                event(3, "approval.responded", "run_2"),
              ],
            });
            const keepSelectedPending = controls.findLatestPendingApprovalRunId({
              selectedRunId: "run_1",
              recentRuns: [],
              events: [
                event(1, "approval.request", "run_1"),
                event(2, "approval.request", "run_2"),
              ],
            });
            const latestFromRecentRuns = controls.findLatestPendingApprovalRunId({
              selectedRunId: "",
              recentRuns: [
                recentRun("run_old", "waiting_for_approval", 100),
                recentRun("run_recent", "waiting_for_approval", 200),
              ],
              events: [],
            });
            console.log(JSON.stringify({
              latestFromEvents,
              clearedLatest,
              keepSelectedPending,
              latestFromRecentRuns,
            }));
            """
        )
    )

    assert payload["latestFromEvents"] == "run_2"
    assert payload["clearedLatest"] == "run_1"
    assert payload["keepSelectedPending"] is None
    assert payload["latestFromRecentRuns"] == "run_recent"


def test_run_inspector_gateway_controls_describes_selected_run_detail():
    payload = run_gateway_controls_script(
        textwrap.dedent(
            """
            const run = {
              run_id: "run_1",
              status: "running",
              created_at: 100,
              updated_at: 200,
              session_id: "session_1",
              model: "hermes-model",
              last_event: "run.running",
              has_error: false,
            };
            const detail = controls.describeGatewayRunDetail({
              runId: "run_1",
              recentRuns: [run],
              events: [
                { id: 1, type: "run.started", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_1", session_id: "session_1", tool: null, status: "running", message: "started" },
                { id: 2, type: "tool.completed", source: "gateway_run", timestamp: "2026-05-11T00:00:01Z", run_id: "run_1", session_id: "session_1", tool: "shell", status: "running", message: "safe summary" },
              ],
            });
            const manual = controls.describeGatewayRunDetail({
              runId: "manual_run",
              recentRuns: [],
              events: [],
            });
            const failed = controls.describeGatewayRunDetail({
              runId: "run_failed",
              recentRuns: [{ ...run, run_id: "run_failed", status: "failed", has_error: true }],
              events: [],
            });
            console.log(JSON.stringify({ detail, manual, failed }));
            """
        )
    )

    assert payload["detail"] == {
        "createdAt": "1970-01-01T00:01:40.000Z",
        "eventCount": 2,
        "hasError": False,
        "known": True,
        "lastEvent": "tool.completed",
        "lastEventAt": "2026-05-11T00:00:01Z",
        "lastMessage": "safe summary",
        "model": "hermes-model",
        "runId": "run_1",
        "sessionId": "session_1",
        "source": "recent_runs",
        "status": "running",
        "tone": "primary",
        "updatedAt": "1970-01-01T00:03:20.000Z",
    }
    assert payload["manual"]["known"] is False
    assert payload["manual"]["source"] == "manual"
    assert payload["manual"]["status"] == "unknown"
    assert payload["manual"]["tone"] == "muted"
    assert payload["failed"]["tone"] == "destructive"
    assert payload["failed"]["hasError"] is True


def test_run_inspector_gateway_controls_filters_recent_run_list():
    payload = run_gateway_controls_script(
        textwrap.dedent(
            """
            const run = (run_id, status, updated_at, extra = {}) => ({
              run_id,
              status,
              created_at: updated_at - 10,
              updated_at,
              session_id: null,
              model: null,
              last_event: status === "waiting_for_approval" ? "approval.request" : `run.${status}`,
              has_error: status === "failed",
              ...extra,
            });
            const recentRuns = [
              run("run_wait", "waiting_for_approval", 300),
              run("run_active", "running", 200),
              run("run_done", "completed", 100),
              run("run_failed", "failed", 400),
            ];
            const events = [
              { id: 1, type: "approval.request", source: "gateway_run", timestamp: "2026-05-11T00:00:00Z", run_id: "run_wait", session_id: null, tool: "shell", status: "waiting", message: null },
            ];
            const all = controls.describeGatewayRunList({ events, recentRuns, filter: "all" });
            const attention = controls.describeGatewayRunList({ events, recentRuns, filter: "attention" });
            const active = controls.describeGatewayRunList({ events, recentRuns, filter: "active" });
            const terminal = controls.describeGatewayRunList({ events, recentRuns, filter: "terminal" });
            const emptyAttention = controls.describeGatewayRunList({
              events: [],
              recentRuns: [run("run_active_only", "running", 10)],
              filter: "attention",
            });
            console.log(JSON.stringify({
              allIds: all.items.map((item) => item.run.run_id),
              attentionIds: attention.items.map((item) => item.run.run_id),
              activeIds: active.items.map((item) => item.run.run_id),
              terminalIds: terminal.items.map((item) => item.run.run_id),
              counts: all.counts,
              firstTone: all.items[0].tone,
              emptyLabel: emptyAttention.emptyLabel,
              emptyLength: emptyAttention.items.length,
            }));
            """
        )
    )

    assert payload["counts"] == {
        "active": 2,
        "all": 4,
        "attention": 2,
        "terminal": 2,
    }
    assert payload["allIds"] == [
        "run_failed",
        "run_wait",
        "run_active",
        "run_done",
    ]
    assert payload["attentionIds"] == ["run_failed", "run_wait"]
    assert payload["activeIds"] == ["run_wait", "run_active"]
    assert payload["terminalIds"] == ["run_failed", "run_done"]
    assert payload["firstTone"] == "destructive"
    assert payload["emptyLabel"] == "No runs need attention"
    assert payload["emptyLength"] == 0


def test_run_inspector_events_hook_uses_tokened_websocket_and_auth_stop() -> None:
    hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorEvents.ts"
    ).read_text(encoding="utf-8")
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")

    assert "new WebSocket(" in hook_source
    assert "__HERMES_SESSION_TOKEN__" in hook_source
    assert "/api/run-inspector/events?token=" in hook_source
    assert 'event.code === 4401' in hook_source
    assert "<EventTimelineCard" in page_source


def test_run_inspector_attention_preview_uses_safe_api_without_notifications() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")
    hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorAttention.ts"
    ).read_text(encoding="utf-8")
    api_source = (ROOT / "web" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert "useRunInspectorAttention" in page_source
    assert "<AttentionPreviewCard" in page_source
    assert "Attention Preview" in page_source
    assert "api.getRunInspectorAttention" in hook_source
    assert "/api/run-inspector/attention?limit=" in api_source
    assert "Notification.requestPermission" not in page_source
    assert "Notification.requestPermission" not in hook_source
    assert "new Notification" not in page_source
    assert "new Notification" not in hook_source


def test_run_inspector_browser_notifications_are_explicit_opt_in() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")
    attention_hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorAttention.ts"
    ).read_text(encoding="utf-8")
    browser_hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorBrowserNotifications.ts"
    ).read_text(encoding="utf-8")

    assert "useRunInspectorBrowserNotifications" in page_source
    assert "BrowserNotificationOptInRow" in page_source
    assert "Notification.requestPermission" not in page_source
    assert "Notification.requestPermission" not in attention_hook_source
    assert "requestPermission()" in browser_hook_source
    assert "new window.Notification(payload.title" in browser_hook_source
    assert "window.location.assign(payload.route)" in browser_hook_source
    assert "token=" not in browser_hook_source


def test_run_inspector_desktop_status_uses_safe_readonly_api() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")
    hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorDesktopStatus.ts"
    ).read_text(encoding="utf-8")
    api_source = (ROOT / "web" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert "useRunInspectorDesktopStatus" in page_source
    assert "Desktop Shell" in page_source
    assert "describeDesktopShellHeaderSignal" in page_source
    assert "Desktop OK" in (
        ROOT / "web" / "src" / "pages" / "runInspectorDesktopStatus.ts"
    ).read_text(encoding="utf-8")
    assert "api.getRunInspectorDesktopStatus" in hook_source
    assert "/api/run-inspector/desktop-status?port=" in api_source
    assert "fetcher = api.getRunInspectorDesktopStatus" in hook_source
    assert "stopDesktop" not in page_source
    assert "startDesktop" not in page_source


def test_run_inspector_memory_workbench_describes_all_states() -> None:
    payload = run_memory_workbench_script(
        textwrap.dedent(
            """
            const base = {
              schema_version: 1,
              generated_at: "2026-05-11T00:00:00Z",
              status: "empty",
              status_reason: "No multi-agent memory work recorded",
              active_work: [],
              memory: {
                status: "unavailable",
                provider_count: 0,
                providers: [],
                registered_tools: [],
                degraded_reason: null,
                privacy_class: "redacted_summary",
              },
              runtime_persistence: {
                status: "disabled",
                enabled_count: 0,
                flags: [],
                degraded_reason: null,
                privacy_class: "redacted_summary",
              },
              agent_assignments: {
                summary: {
                  schema_version: 1,
                  status: "empty",
                  total_count: 0,
                  active_count: 0,
                  completed_count: 0,
                  failed_count: 0,
                  blocked_count: 0,
                  ready_task_ids: [],
                  dependency_waiting_task_ids: [],
                  blocked_task_ids: [],
                  role_counts: {},
                  status_counts: {},
                  conflicts: [],
                  degraded_reason: null,
                  privacy_class: "redacted_summary",
                },
                parallel_plan: {
                  schema_version: 1,
                  status: "empty",
                  max_parallel_workers: 16,
                  batches: [],
                  blocked_task_ids: [],
                  active_task_ids: [],
                  waiting_task_ids: [],
                  conflict_task_ids: [],
                  conflicts: [],
                  degraded_reason: null,
                  privacy_class: "redacted_summary",
                },
                handoff_protocol: {
                  schema_version: 1,
                  status: "empty",
                  handoff_task_ids: [],
                  ready_task_ids: [],
                  blocked_task_ids: [],
                  verification_missing_task_ids: [],
                  reviewer_required_task_ids: [],
                  human_decision_task_ids: [],
                  conflict_task_ids: [],
                  policy_counts: {},
                  degraded_reason: null,
                  privacy_class: "redacted_summary",
                },
                assignments: [],
                degraded_reason: null,
                privacy_class: "redacted_summary",
              },
              checkpoint: {
                current_task_id: null,
                completed_tasks: [],
                pending_tasks: [],
                blocked_tasks: [],
                next_step: "No next step recorded.",
              },
              action_ledger: {
                entries: [],
                recovery_gates: {
                  status: "empty",
                  completed_count: 0,
                  blocked_count: 0,
                  monitoring_count: 0,
                  verification_task_ids: [],
                  blocked_task_ids: [],
                  monitoring_task_ids: [],
                  next_steps: [],
                  blockers: [],
                  source_counts: {},
                  event_type_counts: {},
                  status_counts: {},
                  latest_event_type: null,
                  latest_status: null,
                  latest_timestamp: null,
                  latest_source: null,
                  degraded_reason: null,
                  privacy_class: "redacted_summary",
                },
                degraded_reason: null,
              },
              long_term_queue: { entries: [], unresolved_count: 0, degraded_reason: null },
              learning_review: {
                status: "empty",
                ready_count: 0,
                blocked_count: 0,
                requests: [],
                degraded_reason: null,
                privacy_class: "redacted_summary",
              },
              failure_review_export: {
                schema_version: 1,
                preview_id: "failure-review-export-preview",
                timestamp: "2026-05-11T00:00:00Z",
                title: "Failure review summary preview",
                state: "preview_only",
                requires_review: true,
                output_kind: "failure_review_summary",
                entry_count: 0,
                category_counts: {},
                state_counts: {},
                entries: [],
                summary_lines: [],
                blocked_effects: [],
                status: "empty",
                degraded_reason: null,
                privacy_class: "redacted_summary",
              },
              skills_journal: { entries: [], degraded_reason: null },
              degraded_reason: null,
              privacy_class: "redacted_summary",
            };
            const states = {
              empty: workbench.describeMemoryWorkbenchState("ready", base).label,
              active: workbench.describeMemoryWorkbenchState("ready", {
                ...base,
                status: "active",
                status_reason: "Current task HMAM-08",
              }).label,
              failedTone: workbench.describeMemoryWorkbenchState("ready", {
                ...base,
                status: "failed",
                status_reason: "Blocked work",
              }).tone,
              degradedTone: workbench.describeMemoryWorkbenchState("degraded", {
                ...base,
                status: "degraded",
                degraded_reason: "action_ledger_missing",
              }).tone,
              unavailable: workbench.describeMemoryWorkbenchState("ready", {
                ...base,
                status: "unavailable",
                degraded_reason: "workbench_unavailable",
              }).label,
              persistenceOff: workbench.describeRuntimePersistenceState(base).label,
              persistenceOn: workbench.describeRuntimePersistenceState({
                ...base,
                runtime_persistence: {
                  ...base.runtime_persistence,
                  status: "enabled",
                  enabled_count: 2,
                },
              }).message,
              assignmentsQuiet: workbench.describeAgentAssignmentState(base).label,
              assignmentsActive: workbench.describeAgentAssignmentState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  summary: {
                    ...base.agent_assignments.summary,
                    status: "active",
                    total_count: 2,
                    active_count: 1,
                    ready_task_ids: ["HMAMO-02"],
                  },
                },
              }).message,
              assignmentsConflict: workbench.describeAgentAssignmentState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  summary: {
                    ...base.agent_assignments.summary,
                    status: "conflict",
                    total_count: 2,
                    active_count: 2,
                    conflicts: [{
                      task_ids: ["HMAMO-01", "HMAMO-02"],
                      overlap: ["hermes_cli/agent_task_assignment.py"],
                      resolution: "reviewer_decides",
                      privacy_class: "redacted_summary",
                    }],
                  },
                },
              }).tone,
              assignmentsMissing: workbench.describeAgentAssignmentState(null).tone,
              planQuiet: workbench.describeParallelAssignmentPlanState(base).label,
              planReady: workbench.describeParallelAssignmentPlanState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  parallel_plan: {
                    ...base.agent_assignments.parallel_plan,
                    status: "ready",
                    batches: [
                      {
                        index: 1,
                        task_ids: ["HMAMO-01", "HMAMO-02"],
                        roles: { worker: 2 },
                        privacy_class: "redacted_summary",
                      },
                    ],
                  },
                },
              }).message,
              planSequenced: workbench.describeParallelAssignmentPlanState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  parallel_plan: {
                    ...base.agent_assignments.parallel_plan,
                    status: "sequenced_conflicts",
                    conflict_task_ids: ["HMAMO-01", "HMAMO-02"],
                  },
                },
              }).tone,
              planDegraded: workbench.describeParallelAssignmentPlanState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  parallel_plan: {
                    ...base.agent_assignments.parallel_plan,
                    degraded_reason: "task_contract_parse_error",
                  },
                },
              }).label,
              handoffQuiet: workbench.describeHandoffProtocolState(base).label,
              handoffReady: workbench.describeHandoffProtocolState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  handoff_protocol: {
                    ...base.agent_assignments.handoff_protocol,
                    status: "ready",
                    ready_task_ids: ["HMAMO-13"],
                  },
                },
              }).message,
              handoffVerify: workbench.describeHandoffProtocolState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  handoff_protocol: {
                    ...base.agent_assignments.handoff_protocol,
                    status: "needs_verification",
                    verification_missing_task_ids: ["HMAMO-13"],
                  },
                },
              }).tone,
              handoffBlocked: workbench.describeHandoffProtocolState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  handoff_protocol: {
                    ...base.agent_assignments.handoff_protocol,
                    status: "blocked",
                    blocked_task_ids: ["HMAMO-13"],
                    human_decision_task_ids: ["HMAMO-14"],
                  },
                },
              }).message,
              handoffDegraded: workbench.describeHandoffProtocolState({
                ...base,
                agent_assignments: {
                  ...base.agent_assignments,
                  handoff_protocol: {
                    ...base.agent_assignments.handoff_protocol,
                    degraded_reason: "task_contract_parse_error",
                  },
                },
              }).label,
              recoveryQuiet: workbench.describeDelegateRecoveryGateState(base).label,
              recoveryBlocked: workbench.describeDelegateRecoveryGateState({
                ...base,
                action_ledger: {
                  ...base.action_ledger,
                  recovery_gates: {
                    ...base.action_ledger.recovery_gates,
                    status: "blocked",
                    completed_count: 1,
                    blocked_count: 2,
                  },
                },
              }).message,
              recoveryActive: workbench.describeDelegateRecoveryGateState({
                ...base,
                action_ledger: {
                  ...base.action_ledger,
                  recovery_gates: {
                    ...base.action_ledger.recovery_gates,
                    status: "monitoring",
                    monitoring_count: 3,
                  },
                },
              }).tone,
              reviewQuiet: workbench.describeLearningReviewState(base).label,
              reviewReady: workbench.describeLearningReviewState({
                ...base,
                learning_review: {
                  ...base.learning_review,
                  status: "ready",
                  ready_count: 2,
                  blocked_count: 0,
                },
              }).message,
              reviewBlocked: workbench.describeLearningReviewState({
                ...base,
                learning_review: {
                  ...base.learning_review,
                  status: "blocked",
                  ready_count: 1,
                  blocked_count: 3,
                },
              }).message,
              exportQuiet: workbench.describeFailureReviewExportPreviewState(base).label,
              exportReady: workbench.describeFailureReviewExportPreviewState({
                ...base,
                failure_review_export: {
                  ...base.failure_review_export,
                  status: "ready",
                  entry_count: 2,
                },
              }).message,
              exportDegraded: workbench.describeFailureReviewExportPreviewState({
                ...base,
                failure_review_export: {
                  ...base.failure_review_export,
                  degraded_reason: "long_term_queue_missing",
                },
              }).label,
              exportMissing: workbench.describeFailureReviewExportPreviewState(null).tone,
              reviewMissing: workbench.describeLearningReviewState(null).tone,
              recoveryMissing: workbench.describeDelegateRecoveryGateState(null).tone,
              handoffMissing: workbench.describeHandoffProtocolState(null).tone,
              planMissing: workbench.describeParallelAssignmentPlanState(null).tone,
              persistenceMissing: workbench.describeRuntimePersistenceState(null).tone,
              offlineTone: workbench.describeMemoryWorkbenchState("offline", null).tone,
              providerTone: workbench.memoryProviderTone("available"),
            };
            console.log(JSON.stringify(states));
            """
        )
    )

    assert payload["empty"] == "Memory quiet"
    assert payload["active"] == "Memory active"
    assert payload["failedTone"] == "destructive"
    assert payload["degradedTone"] == "warning"
    assert payload["unavailable"] == "Memory unavailable"
    assert payload["persistenceOff"] == "Persistence off"
    assert payload["persistenceOn"] == "2 local writes enabled"
    assert payload["assignmentsQuiet"] == "Assignments quiet"
    assert payload["assignmentsActive"] == "1 ready / 1 active"
    assert payload["assignmentsConflict"] == "destructive"
    assert payload["assignmentsMissing"] == "muted"
    assert payload["planQuiet"] == "Plan quiet"
    assert payload["planReady"] == "2 tasks / 1 batches"
    assert payload["planSequenced"] == "warning"
    assert payload["planDegraded"] == "Plan degraded"
    assert payload["handoffQuiet"] == "Handoff quiet"
    assert payload["handoffReady"] == "1 ready"
    assert payload["handoffVerify"] == "warning"
    assert payload["handoffBlocked"] == "1 blocked / 1 human"
    assert payload["handoffDegraded"] == "Handoff degraded"
    assert payload["recoveryQuiet"] == "Recovery quiet"
    assert payload["recoveryBlocked"] == "2 blocked / 1 completed"
    assert payload["recoveryActive"] == "primary"
    assert payload["reviewQuiet"] == "Review quiet"
    assert payload["reviewReady"] == "2 pending review"
    assert payload["reviewBlocked"] == "3 blocked / 1 ready"
    assert payload["exportQuiet"] == "Export quiet"
    assert payload["exportReady"] == "2 preview entries"
    assert payload["exportDegraded"] == "Export degraded"
    assert payload["exportMissing"] == "muted"
    assert payload["reviewMissing"] == "muted"
    assert payload["recoveryMissing"] == "muted"
    assert payload["handoffMissing"] == "muted"
    assert payload["planMissing"] == "muted"
    assert payload["persistenceMissing"] == "muted"
    assert payload["offlineTone"] == "destructive"
    assert payload["providerTone"] == "success"


def test_run_inspector_memory_workbench_uses_readonly_api() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")
    hook_source = (
        ROOT / "web" / "src" / "hooks" / "useRunInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    api_source = (ROOT / "web" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert "useRunInspectorMemoryWorkbench" in page_source
    assert "<MultiAgentMemoryWorkbenchCard" in page_source
    assert "Multi-Agent Memory" in page_source
    assert "describeRuntimePersistenceState" in page_source
    assert "describeAgentAssignmentState" in page_source
    assert "describeHandoffProtocolState" in page_source
    assert "describeParallelAssignmentPlanState" in page_source
    assert "describeDelegateRecoveryGateState" in page_source
    assert "describeLearningReviewState" in page_source
    assert "describeFailureReviewExportPreviewState" in page_source
    assert 'label="Persistence"' in page_source
    assert 'label="Assignments"' in page_source
    assert 'label="Recovery"' in page_source
    assert 'label="Review"' in page_source
    assert 'label="Export"' in page_source
    assert 'label="Sources"' in page_source
    assert 'label="Types"' in page_source
    assert 'label="Statuses"' in page_source
    assert 'label="Latest"' in page_source
    assert 'label="Handoff"' in page_source
    assert 'label="Plan"' in page_source
    assert "parallelPlan?.batches.length" in page_source
    assert "api.getRunInspectorMemoryWorkbench" in hook_source
    assert "runtime_persistence" in api_source
    assert "agent_assignments" in api_source
    assert "handoff_protocol" in api_source
    assert "parallel_plan" in api_source
    assert "recovery_gates" in api_source
    assert "source_counts" in api_source
    assert "event_type_counts" in api_source
    assert "status_counts" in api_source
    assert "latest_event_type" in api_source
    assert "learning_review" in api_source
    assert "missing_requirements" in api_source
    assert "requested_effect" in api_source
    assert "failure_review_export" in api_source
    assert "failure_review_export_handoff" in api_source
    assert "summary_lines" in api_source
    assert "blocked_effects" in api_source
    assert "entry_count" in api_source
    assert "allowed_decisions" in api_source
    assert "required_decision_fields" in api_source
    assert "describeRuntimePersistenceState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeAgentAssignmentState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeHandoffProtocolState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeParallelAssignmentPlanState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeDelegateRecoveryGateState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeLearningReviewState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "describeFailureReviewExportPreviewState" in (
        ROOT / "web" / "src" / "pages" / "runInspectorMemoryWorkbench.ts"
    ).read_text(encoding="utf-8")
    assert "/api/run-inspector/memory-workbench?limit=" in api_source
    assert "fetcher = api.getRunInspectorMemoryWorkbench" in hook_source
    assert "method:" not in hook_source
    assert "spawn" not in hook_source.lower()
    assert "write memory" not in page_source.lower()
