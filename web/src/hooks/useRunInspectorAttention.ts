import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  RunInspectorAttentionResponse,
  RunInspectorAttentionSignal,
} from "@/lib/api";
import { classifyRunInspectorError } from "@/hooks/runInspectorStatusPolicy";
import type { RunInspectorAttentionState } from "@/pages/runInspectorAttention";

type RunInspectorAttentionFetcher = (
  limit?: number,
  init?: RequestInit,
) => Promise<RunInspectorAttentionResponse>;

interface UseRunInspectorAttentionOptions {
  enabled?: boolean;
  fetcher?: RunInspectorAttentionFetcher;
  limit?: number;
}

export interface UseRunInspectorAttentionResult {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  refresh: () => void;
  signals: RunInspectorAttentionSignal[];
  state: RunInspectorAttentionState;
}

export function useRunInspectorAttention(
  options: UseRunInspectorAttentionOptions = {},
): UseRunInspectorAttentionResult {
  const {
    enabled = true,
    fetcher = api.getRunInspectorAttention,
    limit = 20,
  } = options;
  const [signals, setSignals] = useState<RunInspectorAttentionSignal[]>([]);
  const [state, setState] = useState<RunInspectorAttentionState>("idle");
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
    setState((previous) => (signals.length > 0 ? previous : "loading"));

    fetcher(limit, { signal: controller.signal })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setSignals(response.signals);
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
  }, [enabled, fetcher, limit, refreshVersion]);

  return useMemo(
    () => ({
      error,
      isLoading,
      lastUpdatedAt,
      refresh,
      signals,
      state,
    }),
    [error, isLoading, lastUpdatedAt, refresh, signals, state],
  );
}
