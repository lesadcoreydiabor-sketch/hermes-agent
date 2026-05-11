from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"


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


def test_run_inspector_desktop_status_prefers_next_action_message() -> None:
    payload = run_desktop_status_script(
        textwrap.dedent(
            """
            const base = {
              ok: true,
              record_present: false,
              runtime_record_cleared: false,
              pid: null,
              pid_status: "none",
              pid_reason: "no_record",
              host: "127.0.0.1",
              port: 9222,
              route: "/run-inspector",
              url: "http://127.0.0.1:9222/run-inspector",
              started_at: null,
              health: "ok",
              health_reason: "ok",
              compatible_dashboard: true,
              attention_level: "info",
              next_action: "Reuse compatible dashboard",
              next_command: "hermes desktop --port 9222",
              reuse_command: "hermes desktop --port 9222",
              manual_url: "http://127.0.0.1:9222/run-inspector",
              stop_command: "hermes dashboard --stop",
            };
            const reusable = desktopStatus.describeDesktopShellStatus("ready", base);
            const stale = desktopStatus.describeDesktopShellHeaderSignal("ready", {
              ...base,
              record_present: true,
              compatible_dashboard: false,
              pid: 99999,
              pid_status: "stale",
              pid_reason: "not_found",
              health: "unavailable",
              health_reason: "URLError",
              attention_level: "warning",
              next_action: "Restart desktop shell",
              next_command: "hermes desktop --port 9119",
              reuse_command: null,
              manual_url: null,
              stop_command: "hermes desktop --port 9119 --stop",
            });
            console.log(JSON.stringify({ reusable, stale }));
            """
        )
    )

    assert payload["reusable"] == {
        "label": "Dashboard reusable",
        "message": "Reuse compatible dashboard",
        "tone": "primary",
    }
    assert payload["stale"] == {
        "label": "Desktop attention",
        "message": "Restart desktop shell",
        "tone": "warning",
    }


def test_run_inspector_desktop_status_formats_next_action_row() -> None:
    payload = run_desktop_status_script(
        textwrap.dedent(
            """
            const action = desktopStatus.describeDesktopShellNextAction({
              next_action: "Reuse compatible dashboard",
              next_command: "hermes desktop --port 9222",
            });
            const command = desktopStatus.getDesktopShellNextCommand({
              next_command: " hermes desktop --port 9222 ",
            });
            const url = desktopStatus.getDesktopShellUrl({
              url: " http://127.0.0.1:9222/run-inspector ",
            });
            const reuse = desktopStatus.getDesktopShellReuseCommand({
              reuse_command: " hermes desktop --port 9222 ",
            });
            const stop = desktopStatus.getDesktopShellStopCommand({
              stop_command: " hermes desktop --port 9222 --stop ",
            });
            const commandOnly = desktopStatus.describeDesktopShellNextAction({
              next_action: null,
              next_command: "hermes desktop --status",
            });
            const attention = desktopStatus.describeDesktopShellAttentionLevel({
              attention_level: "warning",
            });
            const emptyAttention = desktopStatus.describeDesktopShellAttentionLevel({});
            const empty = desktopStatus.describeDesktopShellNextAction({});
            const noCommand = desktopStatus.getDesktopShellNextCommand({});
            const noUrl = desktopStatus.getDesktopShellUrl({});
            const noReuse = desktopStatus.getDesktopShellReuseCommand({});
            const noStop = desktopStatus.getDesktopShellStopCommand({});
            console.log(JSON.stringify({
              action,
              command,
              url,
              reuse,
              stop,
              commandOnly,
              attention,
              emptyAttention,
              empty,
              noCommand,
              noUrl,
              noReuse,
              noStop,
            }));
            """
        )
    )

    assert payload == {
        "action": "Reuse compatible dashboard: hermes desktop --port 9222",
        "command": "hermes desktop --port 9222",
        "url": "http://127.0.0.1:9222/run-inspector",
        "reuse": "hermes desktop --port 9222",
        "stop": "hermes desktop --port 9222 --stop",
        "commandOnly": "hermes desktop --status",
        "attention": "Warning",
        "emptyAttention": "Unknown",
        "empty": None,
        "noCommand": None,
        "noUrl": None,
        "noReuse": None,
        "noStop": None,
    }


def test_run_inspector_desktop_card_renders_next_action_row() -> None:
    page_source = (
        ROOT / "web" / "src" / "pages" / "RunInspectorPage.tsx"
    ).read_text(encoding="utf-8")

    assert "describeDesktopShellNextAction" in page_source
    assert "describeDesktopShellAttentionLevel" in page_source
    assert "getDesktopShellNextCommand" in page_source
    assert "getDesktopShellUrl" in page_source
    assert "getDesktopShellReuseCommand" in page_source
    assert "getDesktopShellStopCommand" in page_source
    assert 'label="Health reason"' in page_source
    assert 'formatDisplayValue(status?.health_reason, "Unknown")' in page_source
    assert 'label="Attention"' in page_source
    assert 'label="PID reason"' in page_source
    assert 'formatDisplayValue(status?.pid_reason, "Unknown")' in page_source
    assert 'ariaLabel="Copy desktop URL"' in page_source
    assert 'ariaLabel="Copy desktop reuse command"' in page_source
    assert 'ariaLabel="Copy desktop stop command"' in page_source
    assert "writeText(value)" in page_source
    assert 'label="Next"' in page_source
    assert 'formatDisplayValue(nextAction, "None")' in page_source
    assert 'ariaLabel="Copy desktop next command"' in page_source
    assert "navigator.clipboard" in page_source
    assert "api." not in page_source[
        page_source.index("function DesktopShellStatusCard") :
        page_source.index("function ActiveToolCard")
    ]
