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

export interface GatewayRunDetailState {
  createdAt: string | null;
  eventCount: number;
  hasError: boolean;
  known: boolean;
  lastEvent: string | null;
  lastEventAt: string | null;
  lastMessage: string | null;
  model: string | null;
  runId: string;
  sessionId: string | null;
  source: "event_stream" | "manual" | "recent_runs";
  status: string;
  tone: Tone;
  updatedAt: string | null;
}

interface GatewayRunSelectionCandidate {
  runId: string;
  score: number;
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

export function findLatestPendingApprovalRunId({
  events,
  recentRuns,
  selectedRunId,
}: {
  events: RunInspectorEvent[];
  recentRuns: RunInspectorGatewayRun[];
  selectedRunId: string;
}): string | null {
  const currentRunId = selectedRunId.trim();
  if (
    currentRunId &&
    describeGatewayRunControlState({
      events,
      recentRuns,
      runId: currentRunId,
    }).approvalPending
  ) {
    return null;
  }

  const candidates = new Map<string, GatewayRunSelectionCandidate>();
  const addCandidate = (runId: string, score: number) => {
    const current = candidates.get(runId);
    if (!current || score > current.score) {
      candidates.set(runId, { runId, score });
    }
  };

  recentRuns.forEach((run, index) => {
    const runId = normalizeRunId(run.run_id);
    if (!runId) {
      return;
    }
    const controlState = describeGatewayRunControlState({
      events,
      recentRuns,
      runId,
    });
    if (controlState.approvalPending) {
      addCandidate(runId, scoreRunSummary(run, index));
    }
  });

  events.forEach((event) => {
    if (!APPROVAL_PENDING_EVENTS.has(normalize(event.type) ?? "")) {
      return;
    }
    const runId = normalizeRunId(event.run_id) ?? normalizeRunId(event.session_id);
    if (!runId) {
      return;
    }
    const controlState = describeGatewayRunControlState({
      events,
      recentRuns,
      runId,
    });
    if (controlState.approvalPending) {
      addCandidate(runId, scoreEvent(event));
    }
  });

  return [...candidates.values()].sort((left, right) => right.score - left.score)[0]
    ?.runId ?? null;
}

export function describeGatewayRunDetail({
  events,
  recentRuns,
  runId,
}: {
  events: RunInspectorEvent[];
  recentRuns: RunInspectorGatewayRun[];
  runId: string;
}): GatewayRunDetailState | null {
  const selectedRunId = runId.trim();
  if (!selectedRunId) {
    return null;
  }

  const run = recentRuns.find((item) => item.run_id === selectedRunId) ?? null;
  const identifiers = new Set(
    [selectedRunId, run?.session_id].filter((value): value is string => Boolean(value)),
  );
  const matchingEvents = events.filter(
    (event) =>
      (event.run_id !== null && identifiers.has(event.run_id)) ||
      (event.session_id !== null && identifiers.has(event.session_id)),
  );
  const latestEvent = matchingEvents.at(-1) ?? null;
  const status =
    run?.status ?? latestEvent?.status ?? (latestEvent ? latestEvent.type : "unknown");
  const source = run ? "recent_runs" : latestEvent ? "event_stream" : "manual";

  return {
    createdAt: secondsToIso(run?.created_at ?? null),
    eventCount: matchingEvents.length,
    hasError: run?.has_error ?? statusIndicatesError(status),
    known: run !== null || latestEvent !== null,
    lastEvent: latestEvent?.type ?? run?.last_event ?? null,
    lastEventAt: latestEvent?.timestamp ?? null,
    lastMessage: latestEvent?.message ?? null,
    model: run?.model ?? null,
    runId: selectedRunId,
    sessionId: run?.session_id ?? latestEvent?.session_id ?? null,
    source,
    status,
    tone: detailTone(status, run?.has_error ?? false),
    updatedAt: secondsToIso(run?.updated_at ?? null),
  };
}

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

function normalizeRunId(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function scoreRunSummary(run: RunInspectorGatewayRun, index: number): number {
  const seconds = run.updated_at ?? run.created_at ?? 0;
  return seconds * 1000 - index / 1000;
}

function scoreEvent(event: RunInspectorEvent): number {
  const parsed = Date.parse(event.timestamp);
  if (Number.isFinite(parsed)) {
    return parsed + event.id / 1000000;
  }
  return event.id;
}

function secondsToIso(value: number | null): string | null {
  if (value === null || !Number.isFinite(value)) {
    return null;
  }
  return new Date(value * 1000).toISOString();
}

function statusIndicatesError(status: string): boolean {
  return normalize(status) === "failed";
}

function detailTone(status: string, hasError: boolean): Tone {
  const normalized = normalize(status);
  if (hasError || normalized === "failed" || normalized === "cancelled") {
    return "destructive";
  }
  if (normalized === "completed") {
    return "success";
  }
  if (normalized === "waiting" || normalized === "waiting_for_approval") {
    return "warning";
  }
  if (
    normalized === "queued" ||
    normalized === "running" ||
    normalized === "run.started" ||
    normalized === "run.running"
  ) {
    return "primary";
  }
  return "muted";
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}
