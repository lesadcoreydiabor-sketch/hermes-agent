import type { RunInspectorResponse } from "@/lib/api";

export type RunInspectorLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "degraded"
  | "auth_failed"
  | "offline"
  | "unknown";

export const RUN_INSPECTOR_POLL_MS = 5_000;
export const RUN_INSPECTOR_TIMEOUT_MS = 5_000;
export const RUN_INSPECTOR_MAX_BACKOFF_MS = 60_000;

export function deriveRunInspectorState(
  response: RunInspectorResponse,
): RunInspectorLoadState {
  if (!response.ok) {
    return "degraded";
  }
  if (response.snapshot.degraded_reason) {
    return "degraded";
  }
  if (response.snapshot.status === "unknown") {
    return "unknown";
  }
  return "ready";
}

export function classifyRunInspectorError(error: unknown): RunInspectorLoadState {
  if (isAuthError(error)) {
    return "auth_failed";
  }
  if (isOfflineError(error)) {
    return "offline";
  }
  return "degraded";
}

export function nextRunInspectorDelayMs(
  failureCount: number,
  baseMs: number = RUN_INSPECTOR_POLL_MS,
  maxMs: number = RUN_INSPECTOR_MAX_BACKOFF_MS,
): number {
  const safeFailureCount = Math.max(0, Math.floor(failureCount));
  const safeBaseMs = Math.max(1, Math.floor(baseMs));
  const safeMaxMs = Math.max(safeBaseMs, Math.floor(maxMs));
  return Math.min(safeBaseMs * 2 ** safeFailureCount, safeMaxMs);
}

export function shouldStopRunInspectorPolling(
  state: RunInspectorLoadState,
): boolean {
  return state === "auth_failed";
}

function isAuthError(error: unknown): boolean {
  const message = errorMessage(error);
  return /^40[13]\b/.test(message) || message.includes("Unauthorized");
}

function isOfflineError(error: unknown): boolean {
  const message = errorMessage(error);
  const name =
    typeof error === "object" && error !== null && "name" in error
      ? String((error as { name?: unknown }).name ?? "")
      : "";
  return (
    name === "AbortError" ||
    message.includes("Failed to fetch") ||
    message.includes("NetworkError") ||
    message.includes("Load failed")
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return String(error ?? "");
}
