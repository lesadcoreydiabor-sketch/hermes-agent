import type {
  RunInspectorHealthStatus,
  RunInspectorMcpStatus,
  RunInspectorResponse,
  RunInspectorSnapshot,
  RunInspectorStatus,
} from "@/lib/api";
import type { RunInspectorLoadState } from "@/hooks/runInspectorStatusPolicy";

export type Tone = "success" | "warning" | "destructive" | "muted" | "primary";

export interface StateDisplay {
  label: string;
  tone: Tone;
}

export type SidebarRunInspectorSignalState =
  | "running"
  | "waiting"
  | "failed"
  | "degraded"
  | "unknown"
  | "unavailable";

export interface SidebarRunInspectorSignal {
  state: SidebarRunInspectorSignalState;
  label: string;
  tone: Tone;
  title: string;
}

const SNAPSHOT_STATE: Record<RunInspectorStatus, StateDisplay> = {
  starting: { label: "Starting", tone: "warning" },
  thinking: { label: "Thinking", tone: "primary" },
  executing_tool: { label: "Executing tool", tone: "primary" },
  waiting_input: { label: "Waiting input", tone: "warning" },
  waiting_approval: { label: "Waiting approval", tone: "warning" },
  rate_limited: { label: "Rate limited", tone: "warning" },
  recovering: { label: "Recovering", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "destructive" },
  stopped: { label: "Stopped", tone: "muted" },
  unknown: { label: "Unknown", tone: "muted" },
};

const LOAD_STATE: Record<RunInspectorLoadState, StateDisplay> = {
  idle: { label: "Idle", tone: "muted" },
  loading: { label: "Loading", tone: "muted" },
  ready: { label: "Ready", tone: "success" },
  degraded: { label: "Degraded", tone: "warning" },
  auth_failed: { label: "Auth failed", tone: "destructive" },
  offline: { label: "Offline", tone: "destructive" },
  unknown: { label: "Unknown", tone: "muted" },
};

const MAX_DISPLAY_VALUE_LENGTH = 160;
const SECRET_LIKE_PATTERN =
  /\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s;]+|\b(?:sk|gh[pousr])-[A-Za-z0-9_-]{8,}/i;

export const TONE_CLASSES: Record<Tone, string> = {
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
  muted: "text-muted-foreground",
  primary: "text-primary",
};

export function describeRunInspectorState(
  state: RunInspectorLoadState,
  snapshot: RunInspectorSnapshot | null,
): StateDisplay {
  if (state === "auth_failed" || state === "offline" || state === "loading") {
    return LOAD_STATE[state];
  }
  if (state === "degraded") {
    return {
      label: snapshot ? SNAPSHOT_STATE[snapshot.status].label : LOAD_STATE.degraded.label,
      tone: "warning",
    };
  }
  if (snapshot) {
    return SNAPSHOT_STATE[snapshot.status];
  }
  return LOAD_STATE[state];
}

export function responseHealthLabel(response: RunInspectorResponse | null): string {
  if (response === null) {
    return "No snapshot";
  }
  return response.ok ? "Snapshot OK" : "Snapshot degraded";
}

export function deriveSidebarRunInspectorSignal(
  state: RunInspectorLoadState,
  snapshot: Pick<RunInspectorSnapshot, "status" | "degraded_reason"> | null,
): SidebarRunInspectorSignal {
  if (state === "auth_failed" || state === "offline") {
    return {
      state: "unavailable",
      label: "Unavailable",
      tone: "destructive",
      title: "Run Inspector unavailable",
    };
  }

  if (state === "degraded" || snapshot?.degraded_reason) {
    return {
      state: "degraded",
      label: "Degraded",
      tone: "warning",
      title: snapshot?.degraded_reason ?? "Run Inspector degraded",
    };
  }

  if (!snapshot || state === "loading" || state === "idle") {
    return {
      state: "unknown",
      label: "Unknown",
      tone: "muted",
      title: "Run Inspector state unknown",
    };
  }

  if (snapshot.status === "failed") {
    return {
      state: "failed",
      label: "Failed",
      tone: "destructive",
      title: "Run failed",
    };
  }

  if (
    snapshot.status === "waiting_input" ||
    snapshot.status === "waiting_approval" ||
    snapshot.status === "rate_limited"
  ) {
    return {
      state: "waiting",
      label: "Waiting",
      tone: "warning",
      title: SNAPSHOT_STATE[snapshot.status].label,
    };
  }

  if (
    snapshot.status === "starting" ||
    snapshot.status === "thinking" ||
    snapshot.status === "executing_tool" ||
    snapshot.status === "recovering"
  ) {
    return {
      state: "running",
      label: "Running",
      tone: "primary",
      title: SNAPSHOT_STATE[snapshot.status].label,
    };
  }

  return {
    state: "unknown",
    label: snapshot.status === "completed" || snapshot.status === "stopped" ? "Idle" : "Unknown",
    tone: "muted",
    title: SNAPSHOT_STATE[snapshot.status].label,
  };
}

export function countToolHealth(
  items: { status: RunInspectorHealthStatus }[],
): Record<RunInspectorHealthStatus, number> {
  return countStatuses(items, ["available", "unavailable", "running", "failed", "unknown"]);
}

export function countMcpHealth(
  items: { status: RunInspectorMcpStatus }[],
): Record<RunInspectorMcpStatus, number> {
  return countStatuses(items, ["connected", "degraded", "failed", "unknown"]);
}

export function formatArgsSummary(summary: Record<string, unknown> | null): string {
  if (!summary) {
    return "No argument summary";
  }

  const type = stringValue(summary.type, "payload");
  const parts = [type];

  if (typeof summary.key_count === "number") {
    parts.push(`${summary.key_count} keys`);
  } else if (typeof summary.item_count === "number") {
    parts.push(`${summary.item_count} items`);
  } else if (typeof summary.char_count === "number") {
    parts.push(`${summary.char_count} chars`);
  }

  if (Array.isArray(summary.keys) && summary.keys.length > 0) {
    parts.push(`keys: ${summary.keys.slice(0, 6).map(String).join(", ")}`);
  }

  if (summary.truncated === true) {
    parts.push("truncated");
  }

  return parts.join(" - ");
}

export function formatDisplayValue(
  value: string | null | undefined,
  fallback: string = "Unknown",
): string {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    return fallback;
  }
  if (SECRET_LIKE_PATTERN.test(text)) {
    return "Redacted";
  }
  if (text.length > MAX_DISPLAY_VALUE_LENGTH) {
    return `${text.slice(0, MAX_DISPLAY_VALUE_LENGTH - 3)}...`;
  }
  return text;
}

export function formatDurationMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "Unknown";
  }
  if (value < 1000) {
    return `${value} ms`;
  }
  return `${(value / 1000).toFixed(1)} s`;
}

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function countStatuses<T extends string>(
  items: { status: T }[],
  statuses: readonly T[],
): Record<T, number> {
  const result = Object.fromEntries(statuses.map((status) => [status, 0])) as Record<T, number>;
  for (const item of items) {
    if (item.status in result) {
      result[item.status] += 1;
    }
  }
  return result;
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}
