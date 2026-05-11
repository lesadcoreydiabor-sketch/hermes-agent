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

function highestSignalTone(signals: RunInspectorAttentionSignal[]): Tone {
  if (signals.some((signal) => signal.severity === "critical")) {
    return "destructive";
  }
  if (signals.some((signal) => signal.severity === "warning")) {
    return "warning";
  }
  return "primary";
}
