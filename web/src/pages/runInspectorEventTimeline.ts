import type { RunInspectorEvent } from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export type RunInspectorEventStreamState =
  | "idle"
  | "loading"
  | "connected"
  | "disconnected"
  | "auth_failed"
  | "offline";

export interface RunInspectorEventDisplay {
  label: string;
  tone: Tone;
  message: string;
}

export interface RunInspectorEventSummary {
  attention: number;
  approval: number;
  cancelled: number;
  completed: number;
  failed: number;
  latest: RunInspectorEvent | null;
  total: number;
}

export const RUN_INSPECTOR_EVENT_LIMIT = 50;
export const RUN_INSPECTOR_EVENT_FILTERS = [
  "all",
  "attention",
  "approval",
  "cancelled",
  "completed",
  "failed",
  "gateway",
  "run",
  "tool",
] as const;

export type RunInspectorEventFilter = (typeof RUN_INSPECTOR_EVENT_FILTERS)[number];

const EVENT_LABELS: Record<string, string> = {
  "tool.started": "Tool started",
  "tool.progress": "Tool progress",
  "tool.completed": "Tool completed",
  "run.started": "Run started",
  "run.running": "Run running",
  "run.completed": "Run completed",
  "run.failed": "Run failed",
  "run.cancelled": "Run cancelled",
  "approval.request": "Approval requested",
  "gateway.forwarder.started": "Gateway forwarder started",
  "gateway.forwarder.completed": "Gateway forwarder completed",
  "gateway.forwarder.failed": "Gateway forwarder failed",
  "message.delta": "Message delta",
};

export function mergeRunInspectorEvents(
  current: RunInspectorEvent[],
  incoming: RunInspectorEvent[],
  limit: number = RUN_INSPECTOR_EVENT_LIMIT,
): RunInspectorEvent[] {
  const safeLimit = Math.max(1, Math.floor(limit));
  const byId = new Map<number, RunInspectorEvent>();
  for (const event of [...current, ...incoming]) {
    byId.set(event.id, event);
  }
  return [...byId.values()]
    .sort((left, right) => left.id - right.id)
    .slice(-safeLimit);
}

export function describeRunInspectorEvent(
  event: RunInspectorEvent,
): RunInspectorEventDisplay {
  const label = EVENT_LABELS[event.type] ?? event.type;
  const tone = eventTone(event);
  const message =
    event.message ??
    event.tool ??
    event.status ??
    event.run_id ??
    event.session_id ??
    "No details";
  return { label, tone, message };
}

export function describeRunInspectorEventContext(event: RunInspectorEvent): string {
  const parts = [
    event.run_id ? `run=${event.run_id}` : null,
    event.session_id ? `session=${event.session_id}` : null,
    event.tool ? `tool=${event.tool}` : null,
  ].filter(Boolean);
  return parts.join(" / ");
}

export function filterRunInspectorEvents(
  events: RunInspectorEvent[],
  filter: RunInspectorEventFilter,
): RunInspectorEvent[] {
  if (filter === "all") {
    return events;
  }

  return events.filter((event) => {
    if (filter === "attention") {
      return (
        event.type === "approval.request" ||
        event.status === "waiting" ||
        event.status === "failed" ||
        event.type.endsWith(".failed")
      );
    }
    if (filter === "approval") {
      return event.type === "approval.request" || event.status === "waiting";
    }
    if (filter === "cancelled") {
      return event.status === "cancelled" || event.type.endsWith(".cancelled");
    }
    if (filter === "completed") {
      return event.status === "completed" || event.type.endsWith(".completed");
    }
    if (filter === "failed") {
      return event.status === "failed" || event.type.endsWith(".failed");
    }
    if (filter === "gateway") {
      return event.type.startsWith("gateway.") || event.source.includes("gateway");
    }
    if (filter === "run") {
      return event.type.startsWith("run.");
    }
    if (filter === "tool") {
      return event.type.startsWith("tool.");
    }
    return true;
  });
}

export function summarizeRunInspectorEvents(
  events: RunInspectorEvent[],
): RunInspectorEventSummary {
  const ordered = [...events].sort((left, right) => left.id - right.id);
  const failed = events.filter(
    (event) => event.status === "failed" || event.type.endsWith(".failed"),
  ).length;

  return {
    attention: filterRunInspectorEvents(events, "attention").length,
    approval: filterRunInspectorEvents(events, "approval").length,
    cancelled: filterRunInspectorEvents(events, "cancelled").length,
    completed: filterRunInspectorEvents(events, "completed").length,
    failed,
    latest: ordered.length > 0 ? ordered[ordered.length - 1] : null,
    total: events.length,
  };
}

export function describeRunInspectorEventStream(
  state: RunInspectorEventStreamState,
): RunInspectorEventDisplay {
  if (state === "connected") {
    return { label: "Live events", tone: "success", message: "Connected" };
  }
  if (state === "auth_failed") {
    return { label: "Events unavailable", tone: "destructive", message: "Auth failed" };
  }
  if (state === "offline") {
    return { label: "Events offline", tone: "destructive", message: "Connection failed" };
  }
  if (state === "loading") {
    return { label: "Loading events", tone: "muted", message: "Connecting" };
  }
  if (state === "disconnected") {
    return { label: "Events disconnected", tone: "warning", message: "Using latest replay" };
  }
  return { label: "Events idle", tone: "muted", message: "No stream" };
}

export function formatRunInspectorEventTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "Unknown";
  }
  return date.toLocaleTimeString();
}

function eventTone(event: RunInspectorEvent): Tone {
  if (event.status === "failed" || event.type.endsWith(".failed")) {
    return "destructive";
  }
  if (event.status === "cancelled" || event.type.endsWith(".cancelled")) {
    return "warning";
  }
  if (
    event.status === "running" ||
    event.type === "gateway.forwarder.started" ||
    event.type === "run.started" ||
    event.type === "run.running" ||
    event.type === "tool.started" ||
    event.type === "tool.progress"
  ) {
    return "primary";
  }
  if (event.status === "completed" || event.type.endsWith(".completed")) {
    return "success";
  }
  if (event.type === "approval.request" || event.status === "waiting") {
    return "warning";
  }
  return "muted";
}
