import { Link } from "react-router-dom";
import type { StatusResponse } from "@/lib/api";
import { useSidebarStatus } from "@/hooks/useSidebarStatus";
import { useRunInspectorStatus } from "@/hooks/useRunInspectorStatus";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import {
  TONE_CLASSES,
  deriveSidebarRunInspectorSignal,
  type Tone,
} from "@/pages/runInspectorViewModel";

const SIDEBAR_RUN_INSPECTOR_POLL_MS = 15_000;
const SIDEBAR_RUN_INSPECTOR_TIMEOUT_MS = 4_000;

/** Gateway + session summary for the System sidebar block (no separate strip chrome). */
export function SidebarStatusStrip() {
  const status = useSidebarStatus();
  const runInspector = useRunInspectorStatus({
    pollMs: SIDEBAR_RUN_INSPECTOR_POLL_MS,
    timeoutMs: SIDEBAR_RUN_INSPECTOR_TIMEOUT_MS,
  });
  const { t } = useI18n();
  const runSignal = deriveSidebarRunInspectorSignal(
    runInspector.state,
    runInspector.snapshot,
  );

  if (status === null) {
    return (
      <div className="px-5 py-1.5" aria-hidden>
        <div className="h-2 w-[80%] max-w-full animate-pulse rounded-sm bg-midground/10" />
      </div>
    );
  }

  const gw = gatewayLine(status, t);
  const { activeSessionsLabel, gatewayStatusLabel } = t.app;

  return (
    <div className="px-5 pb-2 pt-0.5">
      <div className="flex flex-col gap-1 font-mondwest text-[0.55rem] leading-snug tracking-[0.12em]">
        <Link
          to="/sessions"
          title={t.app.statusOverview}
          className={cn(
            "block min-w-0 text-left text-muted-foreground/70",
            "transition-colors hover:text-muted-foreground/90",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/40",
            "focus-visible:ring-inset",
          )}
        >
          <p className="break-words">
            <span className="text-muted-foreground/50">{gatewayStatusLabel}</span>{" "}
            <span className={cn("font-medium", gw.tone)}>{gw.label}</span>
          </p>

          <p className="break-words">
            <span className="text-muted-foreground/50">{activeSessionsLabel}</span>{" "}
            <span className="tabular-nums text-muted-foreground/70">
              {status.active_sessions}
            </span>
          </p>
        </Link>

        <Link
          to="/run-inspector"
          title={runSignal.title}
          className={cn(
            "mt-1 flex min-w-0 items-center gap-1.5 border border-current/10 px-2 py-1",
            "text-muted-foreground/70 transition-colors hover:text-muted-foreground/90",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/40",
            "focus-visible:ring-inset",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "h-1.5 w-1.5 shrink-0 rounded-full bg-current",
              runInspector.isLoading && "animate-pulse",
              toneText(runSignal.tone),
            )}
          />
          <span className="min-w-0 truncate text-muted-foreground/50">
            Run Inspector
          </span>
          <span
            className={cn(
              "ml-auto min-w-0 truncate font-medium",
              toneText(runSignal.tone),
            )}
          >
            {runSignal.label}
          </span>
        </Link>
      </div>
    </div>
  );
}

function gatewayLine(
  status: StatusResponse,
  t: ReturnType<typeof useI18n>["t"],
): { label: string; tone: string } {
  const g = t.app.gatewayStrip;
  const byState: Record<string, { label: string; tone: string }> = {
    running: { label: g.running, tone: "text-success" },
    starting: { label: g.starting, tone: "text-warning" },
    startup_failed: { label: g.failed, tone: "text-destructive" },
    stopped: { label: g.stopped, tone: "text-muted-foreground" },
  };
  if (status.gateway_state && byState[status.gateway_state]) {
    return byState[status.gateway_state];
  }
  return status.gateway_running
    ? { label: g.running, tone: "text-success" }
    : { label: g.off, tone: "text-muted-foreground" };
}

function toneText(tone: Tone): string {
  return TONE_CLASSES[tone];
}
