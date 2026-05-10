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
