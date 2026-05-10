import type {
  RunInspectorEvent,
  RunInspectorGatewayRun,
} from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export interface GatewayRunControlState {
  approvalDetail: GatewayApprovalDetail | null;
  approvalHighlighted: boolean;
  approvalPending: boolean;
  message: string;
  stopAvailable: boolean;
  stopHighlighted: boolean;
  tone: Tone;
}

export interface GatewayApprovalDetail {
  message: string | null;
  status: string | null;
  timestamp: string;
  tool: string | null;
}

const ACTIVE_STATUSES = new Set([
  "queued",
  "running",
  "waiting",
  "waiting_for_approval",
]);
const TERMINAL_STATUSES = new Set([
  "cancelled",
  "canceled",
  "completed",
  "failed",
  "stopped",
]);
const APPROVAL_PENDING_EVENTS = new Set(["approval.request"]);
const APPROVAL_CLEARING_EVENTS = new Set([
  "approval.responded",
  "run.cancelled",
  "run.completed",
  "run.failed",
  "run.running",
  "run.stopping",
]);

export function describeGatewayRunControlState({
  events,
  recentRuns,
  runId,
}: {
  events: RunInspectorEvent[];
  recentRuns: RunInspectorGatewayRun[];
  runId: string;
}): GatewayRunControlState {
  const selectedRunId = runId.trim();
  if (!selectedRunId) {
    return {
      approvalDetail: null,
      approvalHighlighted: false,
      approvalPending: false,
      message: "No run selected",
      stopAvailable: false,
      stopHighlighted: false,
      tone: "muted",
    };
  }

  const run = recentRuns.find((item) => item.run_id === selectedRunId) ?? null;
  const latestEvent = latestEventForRun(events, selectedRunId);
  const latestApprovalEvent = latestEventForRun(events, selectedRunId, (event) =>
    APPROVAL_PENDING_EVENTS.has(normalize(event.type) ?? ""),
  );
  const latestClearingEvent = latestEventForRun(events, selectedRunId, (event) =>
    APPROVAL_CLEARING_EVENTS.has(normalize(event.type) ?? ""),
  );
  const status = normalize(run?.status) ?? normalize(latestEvent?.status);
  const lastEvent = normalize(run?.last_event) ?? normalize(latestEvent?.type);
  const latestType = normalize(latestEvent?.type);
  const approvalCleared =
    latestClearingEvent !== null &&
    (latestApprovalEvent === null || latestClearingEvent.id > latestApprovalEvent.id);
  const approvalPending =
    !approvalCleared &&
    (status === "waiting_for_approval" ||
      status === "waiting" ||
      lastEvent === "approval.request" ||
      latestApprovalEvent !== null);
  const terminal = status ? TERMINAL_STATUSES.has(status) : false;
  const active =
    approvalPending ||
    (status ? ACTIVE_STATUSES.has(status) : false) ||
    latestType === "run.started" ||
    latestType === "run.running";

  if (approvalPending) {
    return {
      approvalDetail: approvalDetailFromEvent(latestApprovalEvent),
      approvalHighlighted: true,
      approvalPending: true,
      message: "Approval pending",
      stopAvailable: true,
      stopHighlighted: false,
      tone: "warning",
    };
  }
  if (terminal && status) {
    return {
      approvalDetail: null,
      approvalHighlighted: false,
      approvalPending: false,
      message: formatStatus(status),
      stopAvailable: false,
      stopHighlighted: false,
      tone: status === "completed" ? "success" : "destructive",
    };
  }
  if (active) {
    return {
      approvalDetail: null,
      approvalHighlighted: false,
      approvalPending: false,
      message: formatStatus(status ?? latestType ?? "running"),
      stopAvailable: true,
      stopHighlighted: true,
      tone: "primary",
    };
  }
  return {
    approvalDetail: null,
    approvalHighlighted: false,
    approvalPending: false,
    message: status ? formatStatus(status) : "Run selected",
    stopAvailable: true,
    stopHighlighted: false,
    tone: "muted",
  };
}

function latestEventForRun(
  events: RunInspectorEvent[],
  runId: string,
  predicate: (event: RunInspectorEvent) => boolean = () => true,
): RunInspectorEvent | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if ((event.run_id === runId || event.session_id === runId) && predicate(event)) {
      return event;
    }
  }
  return null;
}

function approvalDetailFromEvent(
  event: RunInspectorEvent | null,
): GatewayApprovalDetail | null {
  if (!event) {
    return null;
  }
  return {
    message: event.message,
    status: event.status,
    timestamp: event.timestamp,
    tool: event.tool,
  };
}

function normalize(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim().toLowerCase();
  return text || null;
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}
