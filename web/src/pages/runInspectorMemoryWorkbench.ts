import type { RunInspectorMemoryWorkbench } from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export type RunInspectorMemoryWorkbenchState =
  | "idle"
  | "loading"
  | "ready"
  | "degraded"
  | "auth_failed"
  | "offline";

export interface MemoryWorkbenchDisplay {
  label: string;
  message: string;
  tone: Tone;
}

export function describeMemoryWorkbenchState(
  state: RunInspectorMemoryWorkbenchState,
  workbench: RunInspectorMemoryWorkbench | null,
  error?: string | null,
): MemoryWorkbenchDisplay {
  if (state === "auth_failed") {
    return { label: "Memory unavailable", message: "Auth failed", tone: "destructive" };
  }
  if (state === "offline") {
    return { label: "Memory offline", message: "Connection failed", tone: "destructive" };
  }
  if (state === "loading") {
    return { label: "Loading memory", message: "Reading safe work summaries", tone: "muted" };
  }
  if (state === "degraded" && !workbench) {
    return {
      label: "Memory degraded",
      message: error || "Workbench unavailable",
      tone: "warning",
    };
  }
  if (!workbench) {
    return { label: "Memory unknown", message: "No workbench loaded", tone: "muted" };
  }
  if (workbench.status === "failed") {
    return {
      label: "Memory attention",
      message: workbench.status_reason,
      tone: "destructive",
    };
  }
  if (workbench.status === "active") {
    return { label: "Memory active", message: workbench.status_reason, tone: "primary" };
  }
  if (workbench.status === "degraded") {
    return {
      label: "Memory degraded",
      message: workbench.degraded_reason || workbench.status_reason,
      tone: "warning",
    };
  }
  if (workbench.status === "unavailable") {
    return {
      label: "Memory unavailable",
      message: workbench.degraded_reason || workbench.status_reason,
      tone: "warning",
    };
  }
  return { label: "Memory quiet", message: workbench.status_reason, tone: "muted" };
}

export function memoryProviderTone(status: string): Tone {
  if (status === "available") return "success";
  if (status === "degraded") return "warning";
  if (status === "unavailable") return "muted";
  return "muted";
}

export function describeRuntimePersistenceState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const runtime = workbench?.runtime_persistence ?? null;
  if (!runtime) {
    return {
      label: "Persistence unknown",
      message: "No runtime persistence status",
      tone: "muted",
    };
  }
  if (runtime.degraded_reason) {
    return {
      label: "Persistence degraded",
      message: runtime.degraded_reason,
      tone: "warning",
    };
  }
  if (runtime.enabled_count > 0) {
    return {
      label: "Persistence opt-in",
      message: `${runtime.enabled_count} local writes enabled`,
      tone: "success",
    };
  }
  return {
    label: "Persistence off",
    message: "No delegate persistence writes",
    tone: "muted",
  };
}
