import type { RunInspectorDesktopStatus } from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export type RunInspectorDesktopStatusState =
  | "idle"
  | "loading"
  | "ready"
  | "degraded"
  | "auth_failed"
  | "offline";

export interface DesktopShellDisplay {
  label: string;
  message: string;
  tone: Tone;
}

export function describeDesktopShellSource(status: RunInspectorDesktopStatus | null): string {
  if (!status) {
    return "Unknown";
  }
  if (status.record_present) {
    if (status.pid_status === "running") {
      return "Desktop runtime record";
    }
    if (status.pid_status === "stale") {
      return "Stale desktop runtime record";
    }
    return "Desktop runtime record present";
  }
  if (status.compatible_dashboard) {
    return "Reusable dashboard";
  }
  if (status.runtime_record_cleared) {
    return "Runtime record cleared";
  }
  return "No desktop runtime record";
}

export function describeDesktopShellNextAction(
  status: RunInspectorDesktopStatus | null,
): string | null {
  const action = status?.next_action?.trim();
  const command = status?.next_command?.trim();
  if (action && command) {
    return `${action}: ${command}`;
  }
  return action || command || null;
}

export function getDesktopShellNextCommand(
  status: RunInspectorDesktopStatus | null,
): string | null {
  const command = status?.next_command?.trim();
  return command || null;
}

export function getDesktopShellUrl(status: RunInspectorDesktopStatus | null): string | null {
  const url = status?.url?.trim();
  return url || null;
}

export function getDesktopShellReuseCommand(
  status: RunInspectorDesktopStatus | null,
): string | null {
  const command = status?.reuse_command?.trim();
  return command || null;
}

export function getDesktopShellStopCommand(
  status: RunInspectorDesktopStatus | null,
): string | null {
  const command = status?.stop_command?.trim();
  return command || null;
}

export function describeDesktopShellAttentionLevel(
  status: RunInspectorDesktopStatus | null,
): string {
  const level = status?.attention_level?.trim();
  if (!level) {
    return "Unknown";
  }
  return level.charAt(0).toUpperCase() + level.slice(1);
}

export function describeDesktopShellStatus(
  state: RunInspectorDesktopStatusState,
  status: RunInspectorDesktopStatus | null,
  error?: string | null,
): DesktopShellDisplay {
  if (state === "auth_failed") {
    return { label: "Desktop unavailable", message: "Auth failed", tone: "destructive" };
  }
  if (state === "offline") {
    return { label: "Desktop offline", message: "Connection failed", tone: "destructive" };
  }
  if (state === "degraded") {
    return {
      label: "Desktop degraded",
      message: error || "Desktop shell status unavailable",
      tone: "warning",
    };
  }
  if (state === "loading") {
    return { label: "Loading desktop", message: "Checking shell state", tone: "muted" };
  }
  if (!status) {
    return { label: "Desktop unknown", message: "No status loaded", tone: "muted" };
  }
  if (status.record_present && status.pid_status === "running" && status.health === "ok") {
    return {
      label: "Desktop shell running",
      message: status.next_action || "Shell-owned dashboard",
      tone: "success",
    };
  }
  if (status.compatible_dashboard && status.health === "ok") {
    return {
      label: "Dashboard reusable",
      message: status.next_action || "No desktop runtime record",
      tone: "primary",
    };
  }
  if (status.record_present && status.pid_status === "stale") {
    return {
      label: "Desktop record stale",
      message: status.next_action || status.pid_reason,
      tone: "warning",
    };
  }
  if (status.health !== "ok") {
    return {
      label: "Dashboard unavailable",
      message: status.next_action || status.health_reason,
      tone: "warning",
    };
  }
  return {
    label: "Desktop shell ready",
    message: status.next_action || "Dashboard reachable",
    tone: "success",
  };
}

export function describeDesktopShellHeaderSignal(
  state: RunInspectorDesktopStatusState,
  status: RunInspectorDesktopStatus | null,
  error?: string | null,
): DesktopShellDisplay {
  const display = describeDesktopShellStatus(state, status, error);

  if (display.tone === "success") {
    return { label: "Desktop OK", message: display.message, tone: display.tone };
  }
  if (display.tone === "primary") {
    return { label: "Desktop reuse", message: display.message, tone: display.tone };
  }
  if (display.tone === "warning") {
    return { label: "Desktop attention", message: display.message, tone: display.tone };
  }
  if (display.tone === "destructive") {
    return { label: "Desktop offline", message: display.message, tone: display.tone };
  }
  return { label: "Desktop unknown", message: display.message, tone: "muted" };
}
