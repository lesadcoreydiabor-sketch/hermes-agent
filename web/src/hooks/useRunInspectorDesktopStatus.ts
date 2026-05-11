import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  RunInspectorDesktopStatus,
  RunInspectorDesktopStatusResponse,
} from "@/lib/api";
import { classifyRunInspectorError } from "@/hooks/runInspectorStatusPolicy";
import type { RunInspectorDesktopStatusState } from "@/pages/runInspectorDesktopStatus";

type RunInspectorDesktopStatusFetcher = (
  port?: number,
  init?: RequestInit,
) => Promise<RunInspectorDesktopStatusResponse>;

interface UseRunInspectorDesktopStatusOptions {
  enabled?: boolean;
  fetcher?: RunInspectorDesktopStatusFetcher;
  port?: number;
}

export interface UseRunInspectorDesktopStatusResult {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  refresh: () => void;
  state: RunInspectorDesktopStatusState;
  status: RunInspectorDesktopStatus | null;
}

export function useRunInspectorDesktopStatus(
  options: UseRunInspectorDesktopStatusOptions = {},
): UseRunInspectorDesktopStatusResult {
  const {
    enabled = true,
    fetcher = api.getRunInspectorDesktopStatus,
    port = 9119,
  } = options;
  const [status, setStatus] = useState<RunInspectorDesktopStatus | null>(null);
  const [state, setState] = useState<RunInspectorDesktopStatusState>("idle");
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
    setState((previous) => (status ? previous : "loading"));

    fetcher(port, { signal: controller.signal })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setStatus(response.status);
        setLastUpdatedAt(response.refreshed_at);
        setState(response.ok ? "ready" : "degraded");
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
  }, [enabled, fetcher, port, refreshVersion]);

  return useMemo(
    () => ({
      error,
      isLoading,
      lastUpdatedAt,
      refresh,
      state,
      status,
    }),
    [error, isLoading, lastUpdatedAt, refresh, state, status],
  );
}
