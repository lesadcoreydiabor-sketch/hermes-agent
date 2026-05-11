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
    return { label: "Desktop shell running", message: "Shell-owned dashboard", tone: "success" };
  }
  if (status.compatible_dashboard && status.health === "ok") {
    return { label: "Dashboard reusable", message: "No desktop runtime record", tone: "primary" };
  }
  if (status.record_present && status.pid_status === "stale") {
    return { label: "Desktop record stale", message: status.pid_reason, tone: "warning" };
  }
  if (status.health !== "ok") {
    return { label: "Dashboard unavailable", message: status.health_reason, tone: "warning" };
  }
  return { label: "Desktop shell ready", message: "Dashboard reachable", tone: "success" };
}
