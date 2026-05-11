import type { RunInspectorAttentionSignal } from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export type RunInspectorAttentionState =
  | "idle"
  | "loading"
  | "ready"
  | "degraded"
  | "auth_failed"
  | "offline";

export interface AttentionPreviewDisplay {
  label: string;
  message: string;
  tone: Tone;
}

export type BrowserNotificationPermission =
  | "default"
  | "denied"
  | "granted"
  | "unsupported";

export type BrowserNotificationOptInState =
  | "blocked"
  | "degraded"
  | "disabled"
  | "enabled"
  | "promptable"
  | "unsupported";

export interface BrowserNotificationOptInDisplay extends AttentionPreviewDisplay {
  state: BrowserNotificationOptInState;
}

export interface BrowserNotificationOptInInput {
  deliveredCount?: number;
  enabled: boolean;
  error?: string | null;
  permission: BrowserNotificationPermission;
}

export interface BrowserNotificationPayload {
  body: string;
  route: "/run-inspector";
  tag: string;
  title: string;
}

export interface BrowserNotificationDeliveryInput {
  deliveredExpiresAt?: number | null;
  nowMs?: number;
}

export function attentionSignalTone(
  signal: Pick<RunInspectorAttentionSignal, "severity">,
): Tone {
  if (signal.severity === "critical") {
    return "destructive";
  }
  if (signal.severity === "warning") {
    return "warning";
  }
  return "primary";
}

export function describeAttentionPreview(
  state: RunInspectorAttentionState,
  signals: RunInspectorAttentionSignal[],
  error?: string | null,
): AttentionPreviewDisplay {
  if (state === "auth_failed") {
    return { label: "Attention unavailable", message: "Auth failed", tone: "destructive" };
  }
  if (state === "offline") {
    return { label: "Attention offline", message: "Connection failed", tone: "destructive" };
  }
  if (state === "degraded") {
    return {
      label: "Attention degraded",
      message: error || "Using available safe signals",
      tone: "warning",
    };
  }
  if (state === "loading") {
    return { label: "Loading attention", message: "Checking safe signals", tone: "muted" };
  }
  if (signals.length > 0) {
    return {
      label: `${signals.length} signal${signals.length === 1 ? "" : "s"}`,
      message: "Attention needed",
      tone: highestSignalTone(signals),
    };
  }
  return { label: "No signals", message: "No current attention signals", tone: "success" };
}

export function describeBrowserNotificationOptIn({
  deliveredCount = 0,
  enabled,
  error,
  permission,
}: BrowserNotificationOptInInput): BrowserNotificationOptInDisplay {
  if (permission === "unsupported") {
    return {
      label: "Notifications unavailable",
      message: "Browser notifications are unsupported",
      state: "unsupported",
      tone: "muted",
    };
  }
  if (permission === "denied") {
    return {
      label: "Notifications blocked",
      message: "Permission denied by browser",
      state: "blocked",
      tone: "warning",
    };
  }
  if (error) {
    return {
      label: "Notifications degraded",
      message: error,
      state: "degraded",
      tone: "warning",
    };
  }
  if (enabled && permission === "granted") {
    return {
      label: "Notifications on",
      message:
        deliveredCount > 0
          ? `${deliveredCount} delivered this session`
          : "Waiting for safe attention signals",
      state: "enabled",
      tone: "success",
    };
  }
  if (permission === "granted") {
    return {
      label: "Notifications off",
      message: "Permission granted",
      state: "disabled",
      tone: "muted",
    };
  }
  return {
    label: "Notifications off",
    message: "Enable manually",
    state: enabled ? "promptable" : "disabled",
    tone: "muted",
  };
}

export function isAttentionSignalDeliverable(
  signal: Pick<RunInspectorAttentionSignal, "dedupe_key" | "timestamp" | "ttl_ms">,
  { deliveredExpiresAt = null, nowMs = Date.now() }: BrowserNotificationDeliveryInput = {},
): boolean {
  const ttlMs = Number(signal.ttl_ms);
  const timestampMs = Date.parse(signal.timestamp);
  if (!Number.isFinite(ttlMs) || ttlMs <= 0 || !Number.isFinite(timestampMs)) {
    return false;
  }
  if (timestampMs + ttlMs <= nowMs) {
    return false;
  }
  if (deliveredExpiresAt && deliveredExpiresAt > nowMs) {
    return false;
  }
  return Boolean(signal.dedupe_key);
}

export function attentionSignalExpiresAt(
  signal: Pick<RunInspectorAttentionSignal, "timestamp" | "ttl_ms">,
): number {
  const timestampMs = Date.parse(signal.timestamp);
  const ttlMs = Number(signal.ttl_ms);
  if (!Number.isFinite(timestampMs) || !Number.isFinite(ttlMs) || ttlMs <= 0) {
    return 0;
  }
  return timestampMs + ttlMs;
}

export function safeNotificationPayload(
  signal: Pick<RunInspectorAttentionSignal, "body" | "dedupe_key" | "title">,
): BrowserNotificationPayload {
  return {
    body: normalizeNotificationText(
      signal.body,
      "Open Run Inspector for safe details.",
    ),
    route: "/run-inspector",
    tag: normalizeNotificationText(signal.dedupe_key, "run-inspector-attention"),
    title: normalizeNotificationText(signal.title, "Hermes needs attention"),
  };
}

function highestSignalTone(signals: RunInspectorAttentionSignal[]): Tone {
  if (signals.some((signal) => signal.severity === "critical")) {
    return "destructive";
  }
  if (signals.some((signal) => signal.severity === "warning")) {
    return "warning";
  }
  return "primary";
}

function normalizeNotificationText(value: string | null | undefined, fallback: string): string {
  const trimmed = (value ?? "").trim();
  return trimmed || fallback;
}
