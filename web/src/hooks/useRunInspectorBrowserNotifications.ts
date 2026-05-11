import { useCallback, useEffect, useMemo, useState } from "react";
import type { RunInspectorAttentionSignal } from "@/lib/api";
import {
  attentionSignalExpiresAt,
  describeBrowserNotificationOptIn,
  isAttentionSignalDeliverable,
  safeNotificationPayload,
  type BrowserNotificationOptInDisplay,
  type BrowserNotificationPermission,
} from "@/pages/runInspectorAttention";

const ENABLED_KEY = "hermes.runInspector.browserNotifications.enabled";
const DELIVERED_KEY = "hermes.runInspector.browserNotifications.delivered";

type DeliveredMap = Record<string, number>;

interface UseRunInspectorBrowserNotificationsOptions {
  signals: RunInspectorAttentionSignal[];
}

export interface UseRunInspectorBrowserNotificationsResult {
  deliveredCount: number;
  disable: () => void;
  display: BrowserNotificationOptInDisplay;
  enable: () => Promise<void>;
  enabled: boolean;
  error: string | null;
  isEnabling: boolean;
  permission: BrowserNotificationPermission;
}

export function useRunInspectorBrowserNotifications({
  signals,
}: UseRunInspectorBrowserNotificationsOptions): UseRunInspectorBrowserNotificationsResult {
  const [enabled, setEnabled] = useState(readStoredEnabled);
  const [permission, setPermission] = useState<BrowserNotificationPermission>(
    readBrowserNotificationPermission,
  );
  const [isEnabling, setIsEnabling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deliveredCount, setDeliveredCount] = useState(0);

  useEffect(() => {
    setPermission(readBrowserNotificationPermission());
  }, []);

  const disable = useCallback(() => {
    setEnabled(false);
    setError(null);
    writeStoredEnabled(false);
  }, []);

  const enable = useCallback(async () => {
    setError(null);
    if (!browserNotificationsSupported()) {
      setPermission("unsupported");
      setEnabled(false);
      writeStoredEnabled(false);
      return;
    }

    setIsEnabling(true);
    try {
      const currentPermission = window.Notification.permission;
      const nextPermission =
        currentPermission === "granted"
          ? "granted"
          : await window.Notification.requestPermission();
      setPermission(nextPermission);
      const nextEnabled = nextPermission === "granted";
      setEnabled(nextEnabled);
      writeStoredEnabled(nextEnabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setEnabled(false);
      writeStoredEnabled(false);
    } finally {
      setIsEnabling(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled || permission !== "granted" || !browserNotificationsSupported()) {
      return;
    }

    const nowMs = Date.now();
    const delivered = pruneDeliveredMap(readDeliveredMap(), nowMs);
    let deliveredNow = 0;

    for (const signal of signals) {
      const expiresAt = attentionSignalExpiresAt(signal);
      if (
        !isAttentionSignalDeliverable(signal, {
          deliveredExpiresAt: delivered[signal.dedupe_key],
          nowMs,
        })
      ) {
        continue;
      }

      const payload = safeNotificationPayload(signal);
      try {
        const notification = new window.Notification(payload.title, {
          body: payload.body,
          data: { route: payload.route },
          tag: payload.tag,
        });
        notification.onclick = () => {
          window.focus();
          window.location.assign(payload.route);
          notification.close();
        };
        delivered[signal.dedupe_key] = expiresAt;
        deliveredNow += 1;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        break;
      }
    }

    writeDeliveredMap(delivered);
    if (deliveredNow > 0) {
      setDeliveredCount((value) => value + deliveredNow);
    }
  }, [enabled, permission, signals]);

  const display = useMemo(
    () =>
      describeBrowserNotificationOptIn({
        deliveredCount,
        enabled,
        error,
        permission,
      }),
    [deliveredCount, enabled, error, permission],
  );

  return {
    deliveredCount,
    disable,
    display,
    enable,
    enabled,
    error,
    isEnabling,
    permission,
  };
}

function browserNotificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

function readBrowserNotificationPermission(): BrowserNotificationPermission {
  if (!browserNotificationsSupported()) {
    return "unsupported";
  }
  return window.Notification.permission;
}

function readStoredEnabled(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(ENABLED_KEY) === "true";
}

function writeStoredEnabled(enabled: boolean): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ENABLED_KEY, enabled ? "true" : "false");
}

function readDeliveredMap(): DeliveredMap {
  if (typeof window === "undefined") {
    return {};
  }
  const raw = window.localStorage.getItem(DELIVERED_KEY);
  if (!raw) {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    const delivered: DeliveredMap = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (typeof key === "string" && typeof value === "number") {
        delivered[key] = value;
      }
    }
    return delivered;
  } catch {
    return {};
  }
}

function writeDeliveredMap(delivered: DeliveredMap): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(DELIVERED_KEY, JSON.stringify(delivered));
}

function pruneDeliveredMap(delivered: DeliveredMap, nowMs: number): DeliveredMap {
  return Object.fromEntries(
    Object.entries(delivered).filter(([, expiresAt]) => expiresAt > nowMs),
  );
}
