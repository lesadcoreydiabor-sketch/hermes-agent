import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  RunInspectorMemoryWorkbench,
  RunInspectorMemoryWorkbenchResponse,
} from "@/lib/api";
import { classifyRunInspectorError } from "@/hooks/runInspectorStatusPolicy";
import type { RunInspectorMemoryWorkbenchState } from "@/pages/runInspectorMemoryWorkbench";

type RunInspectorMemoryWorkbenchFetcher = (
  limit?: number,
  init?: RequestInit,
) => Promise<RunInspectorMemoryWorkbenchResponse>;

interface UseRunInspectorMemoryWorkbenchOptions {
  enabled?: boolean;
  fetcher?: RunInspectorMemoryWorkbenchFetcher;
  limit?: number;
}

export interface UseRunInspectorMemoryWorkbenchResult {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  refresh: () => void;
  state: RunInspectorMemoryWorkbenchState;
  workbench: RunInspectorMemoryWorkbench | null;
}

export function useRunInspectorMemoryWorkbench(
  options: UseRunInspectorMemoryWorkbenchOptions = {},
): UseRunInspectorMemoryWorkbenchResult {
  const {
    enabled = true,
    fetcher = api.getRunInspectorMemoryWorkbench,
    limit = 12,
  } = options;
  const [workbench, setWorkbench] = useState<RunInspectorMemoryWorkbench | null>(null);
  const [state, setState] = useState<RunInspectorMemoryWorkbenchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    setRefreshVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState("idle");
      setIsLoading(false);
      return undefined;
    }

    let cancelled = false;
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setIsLoading(true);
    setError(null);
    setState((previous) => (workbench ? previous : "loading"));

    fetcher(limit, { signal: controller.signal })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setWorkbench(response.workbench);
        setLastUpdatedAt(response.refreshed_at);
        setState(response.ok && response.workbench.status !== "degraded" ? "ready" : "degraded");
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
        const classified = classifyRunInspectorError(err);
        setState(classified === "auth_failed" || classified === "offline" ? classified : "degraded");
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    };
  }, [enabled, fetcher, limit, refreshVersion]);

  return useMemo(
    () => ({
      error,
      isLoading,
      lastUpdatedAt,
      refresh,
      state,
      workbench,
    }),
    [error, isLoading, lastUpdatedAt, refresh, state, workbench],
  );
}
