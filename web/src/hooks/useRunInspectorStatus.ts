import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { RunInspectorResponse, RunInspectorSnapshot } from "@/lib/api";
import {
  RUN_INSPECTOR_MAX_BACKOFF_MS,
  RUN_INSPECTOR_POLL_MS,
  RUN_INSPECTOR_TIMEOUT_MS,
  classifyRunInspectorError,
  deriveRunInspectorState,
  nextRunInspectorDelayMs,
  shouldStopRunInspectorPolling,
} from "@/hooks/runInspectorStatusPolicy";
import type { RunInspectorLoadState } from "@/hooks/runInspectorStatusPolicy";

type RunInspectorFetcher = (init?: RequestInit) => Promise<RunInspectorResponse>;

interface UseRunInspectorStatusOptions {
  enabled?: boolean;
  pollMs?: number;
  timeoutMs?: number;
  maxBackoffMs?: number;
  fetcher?: RunInspectorFetcher;
}

interface RunInspectorStatusState {
  state: RunInspectorLoadState;
  snapshot: RunInspectorSnapshot | null;
  response: RunInspectorResponse | null;
  error: string | null;
  lastUpdatedAt: string | null;
  failureCount: number;
  isLoading: boolean;
  isPolling: boolean;
}

export interface UseRunInspectorStatusResult extends RunInspectorStatusState {
  refresh: () => void;
}

const INITIAL_STATE: RunInspectorStatusState = {
  state: "idle",
  snapshot: null,
  response: null,
  error: null,
  lastUpdatedAt: null,
  failureCount: 0,
  isLoading: false,
  isPolling: false,
};

export function useRunInspectorStatus(
  options: UseRunInspectorStatusOptions = {},
): UseRunInspectorStatusResult {
  const {
    enabled = true,
    pollMs = RUN_INSPECTOR_POLL_MS,
    timeoutMs = RUN_INSPECTOR_TIMEOUT_MS,
    maxBackoffMs = RUN_INSPECTOR_MAX_BACKOFF_MS,
    fetcher = api.getRunInspector,
  } = options;

  const [status, setStatus] = useState<RunInspectorStatusState>(INITIAL_STATE);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const requestIdRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    setRefreshVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setStatus((previous) => ({
        ...previous,
        state: "idle",
        isLoading: false,
        isPolling: false,
      }));
      return undefined;
    }

    let cancelled = false;

    const clearScheduledLoad = () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const scheduleLoad = (delayMs: number) => {
      clearScheduledLoad();
      timerRef.current = setTimeout(load, delayMs);
    };

    const load = async () => {
      clearScheduledLoad();
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;

      if (abortRef.current !== null) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      setStatus((previous) => ({
        ...previous,
        state: previous.snapshot ? previous.state : "loading",
        error: null,
        isLoading: true,
        isPolling: true,
      }));

      try {
        const response = await fetcher({ signal: controller.signal });
        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }

        const state = deriveRunInspectorState(response);
        setStatus({
          state,
          snapshot: response.snapshot,
          response,
          error: null,
          lastUpdatedAt: response.refreshed_at,
          failureCount: 0,
          isLoading: false,
          isPolling: !shouldStopRunInspectorPolling(state),
        });

        if (!shouldStopRunInspectorPolling(state)) {
          scheduleLoad(pollMs);
        }
      } catch (error) {
        if (cancelled || requestId !== requestIdRef.current) {
          return;
        }

        const state = classifyRunInspectorError(error);
        setStatus((previous) => {
          const failureCount = previous.failureCount + 1;
          if (!shouldStopRunInspectorPolling(state)) {
            scheduleLoad(
              nextRunInspectorDelayMs(failureCount, pollMs, maxBackoffMs),
            );
          }
          return {
            ...previous,
            state,
            error: error instanceof Error ? error.message : String(error),
            failureCount,
            isLoading: false,
            isPolling: !shouldStopRunInspectorPolling(state),
          };
        });
      } finally {
        clearTimeout(timeoutId);
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    };

    load();

    return () => {
      cancelled = true;
      clearScheduledLoad();
      if (abortRef.current !== null) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, [enabled, fetcher, maxBackoffMs, pollMs, refreshVersion, timeoutMs]);

  return useMemo(
    () => ({
      ...status,
      refresh,
    }),
    [refresh, status],
  );
}
