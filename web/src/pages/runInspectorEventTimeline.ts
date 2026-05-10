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

export const RUN_INSPECTOR_EVENT_LIMIT = 50;

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
  if (
    event.status === "running" ||
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
