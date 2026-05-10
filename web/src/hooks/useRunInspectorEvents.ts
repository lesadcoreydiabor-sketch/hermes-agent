import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HERMES_BASE_PATH, api } from "@/lib/api";
import type { RunInspectorEvent, RunInspectorEventsResponse } from "@/lib/api";
import {
  RUN_INSPECTOR_EVENT_LIMIT,
  mergeRunInspectorEvents,
  type RunInspectorEventStreamState,
} from "@/pages/runInspectorEventTimeline";

type RunInspectorEventsFetcher = (
  limit?: number,
  init?: RequestInit,
) => Promise<RunInspectorEventsResponse>;

interface UseRunInspectorEventsOptions {
  enabled?: boolean;
  limit?: number;
  fetcher?: RunInspectorEventsFetcher;
}

export interface UseRunInspectorEventsResult {
  events: RunInspectorEvent[];
  error: string | null;
  lastUpdatedAt: string | null;
  refresh: () => void;
  state: RunInspectorEventStreamState;
}

export function useRunInspectorEvents(
  options: UseRunInspectorEventsOptions = {},
): UseRunInspectorEventsResult {
  const {
    enabled = true,
    limit = RUN_INSPECTOR_EVENT_LIMIT,
    fetcher = api.getRunInspectorEvents,
  } = options;
  const [events, setEvents] = useState<RunInspectorEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [state, setState] = useState<RunInspectorEventStreamState>("idle");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  const refresh = useCallback(() => {
    setRefreshVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState("idle");
      return undefined;
    }

    let cancelled = false;
    let unmounting = false;
    setState("loading");
    setError(null);

    fetcher(limit)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setEvents((previous) =>
          mergeRunInspectorEvents(previous, response.events, limit),
        );
        setLastUpdatedAt(response.refreshed_at);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setState(classifyEventStreamError(err));
        }
      });

    const token = window.__HERMES_SESSION_TOKEN__;
    if (!token) {
      setState("auth_failed");
      setError("Session token not available");
      return () => {
        cancelled = true;
      };
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const base = HERMES_BASE_PATH ? `${HERMES_BASE_PATH}` : "";
    const ws = new WebSocket(
      `${proto}//${window.location.host}${base}/api/run-inspector/events?token=${encodeURIComponent(token)}`,
    );
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      if (!cancelled) {
        setState("connected");
        setError(null);
      }
    });

    ws.addEventListener("message", (event) => {
      if (cancelled) {
        return;
      }
      let frame: unknown;
      try {
        frame = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (!frame || typeof frame !== "object") {
        return;
      }
      const typed = frame as {
        event?: RunInspectorEvent;
        events?: RunInspectorEvent[];
        timestamp?: string;
        type?: string;
      };
      if (typed.type === "replay" && Array.isArray(typed.events)) {
        setEvents((previous) =>
          mergeRunInspectorEvents(previous, typed.events ?? [], limit),
        );
        setLastUpdatedAt(typed.timestamp ?? null);
      } else if (typed.type === "event" && typed.event) {
        setEvents((previous) =>
          mergeRunInspectorEvents(previous, [typed.event as RunInspectorEvent], limit),
        );
        setLastUpdatedAt(typed.event.timestamp);
      }
    });

    ws.addEventListener("error", () => {
      if (!cancelled) {
        setState("offline");
        setError("Event stream connection failed");
      }
    });

    ws.addEventListener("close", (event) => {
      if (cancelled || unmounting) {
        return;
      }
      if (event.code === 4401) {
        setState("auth_failed");
        setError("Event stream auth failed");
        return;
      }
      setState("disconnected");
      setError("Event stream disconnected");
    });

    return () => {
      cancelled = true;
      unmounting = true;
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [enabled, fetcher, limit, refreshVersion]);

  return useMemo(
    () => ({
      events,
      error,
      lastUpdatedAt,
      refresh,
      state,
    }),
    [events, error, lastUpdatedAt, refresh, state],
  );
}

function classifyEventStreamError(error: Error): RunInspectorEventStreamState {
  if (/^40[13]\b/.test(error.message) || error.message.includes("Unauthorized")) {
    return "auth_failed";
  }
  if (
    error.name === "AbortError" ||
    error.message.includes("Failed to fetch") ||
    error.message.includes("NetworkError")
  ) {
    return "offline";
  }
  return "disconnected";
}
