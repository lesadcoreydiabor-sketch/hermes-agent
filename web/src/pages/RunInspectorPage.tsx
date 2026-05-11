import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  Database,
  FileWarning,
  Link,
  Monitor,
  Play,
  RefreshCw,
  Shield,
  Terminal,
  Wrench,
  XCircle,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageHeader } from "@/contexts/usePageHeader";
import { useRunInspectorAttention } from "@/hooks/useRunInspectorAttention";
import { useRunInspectorBrowserNotifications } from "@/hooks/useRunInspectorBrowserNotifications";
import { useRunInspectorDesktopStatus } from "@/hooks/useRunInspectorDesktopStatus";
import { useRunInspectorEvents } from "@/hooks/useRunInspectorEvents";
import { useRunInspectorMemoryWorkbench } from "@/hooks/useRunInspectorMemoryWorkbench";
import { useRunInspectorStatus } from "@/hooks/useRunInspectorStatus";
import type {
  RunInspectorAttentionSignal,
  RunInspectorDesktopStatus,
  RunInspectorEvent,
  RunInspectorGatewayForwarder,
  RunInspectorGatewayRun,
  RunInspectorMemoryWorkbench,
  RunInspectorMcpHealth,
  RunInspectorResponse,
  RunInspectorSnapshot,
  RunInspectorToolHealth,
} from "@/lib/api";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";
import {
  TONE_CLASSES,
  countMcpHealth,
  countToolHealth,
  describeRunInspectorState,
  formatArgsSummary,
  formatDateTime,
  formatDisplayValue,
  formatDurationMs,
  responseHealthLabel,
  type StateDisplay,
  type Tone,
} from "@/pages/runInspectorViewModel";
import {
  describeRunInspectorEvent,
  describeRunInspectorEventContext,
  describeRunInspectorEventStream,
  filterRunInspectorEvents,
  formatRunInspectorEventTime,
  RUN_INSPECTOR_EVENT_FILTERS,
  summarizeRunInspectorEvents,
  type RunInspectorEventFilter,
  type RunInspectorEventStreamState,
} from "@/pages/runInspectorEventTimeline";
import {
  attentionSignalTone,
  describeAttentionPreview,
  type BrowserNotificationOptInDisplay,
  type RunInspectorAttentionState,
} from "@/pages/runInspectorAttention";
import {
  describeDesktopShellHeaderSignal,
  describeDesktopShellSource,
  describeDesktopShellStatus,
  type RunInspectorDesktopStatusState,
} from "@/pages/runInspectorDesktopStatus";
import {
  describeMemoryWorkbenchState,
  memoryProviderTone,
  type RunInspectorMemoryWorkbenchState,
} from "@/pages/runInspectorMemoryWorkbench";
import {
  describeGatewayRunDetail,
  describeGatewayRunList,
  describeGatewayRunControlState,
  findLatestPendingApprovalRunId,
  type GatewayRunControlState,
  type GatewayRunDetailState,
  type GatewayRunListFilter,
  type GatewayRunListSummary,
} from "@/pages/runInspectorGatewayControls";

type BadgeTone = "success" | "warning" | "destructive" | "secondary" | "outline";

interface GatewayForwarderDisplay extends StateDisplay {
  message: string;
}

const BADGE_TONE: Record<Tone, BadgeTone> = {
  success: "success",
  warning: "warning",
  destructive: "destructive",
  muted: "outline",
  primary: "secondary",
};

const DEFAULT_GATEWAY_LAUNCH_INPUT =
  "Report current Hermes gateway health in one concise sentence.";
type GatewayRunSelectionMode = "auto" | "manual";

export default function RunInspectorPage() {
  const inspector = useRunInspectorStatus();
  const eventStream = useRunInspectorEvents();
  const attention = useRunInspectorAttention();
  const desktopStatus = useRunInspectorDesktopStatus();
  const memoryWorkbench = useRunInspectorMemoryWorkbench();
  const browserNotifications = useRunInspectorBrowserNotifications({
    signals: attention.signals,
  });
  const [gatewayRunId, setGatewayRunId] = useState("");
  const [gatewayRunSelectionMode, setGatewayRunSelectionMode] =
    useState<GatewayRunSelectionMode>("auto");
  const [gatewayForwarder, setGatewayForwarder] =
    useState<RunInspectorGatewayForwarder | null>(null);
  const [gatewayForwarderError, setGatewayForwarderError] = useState<string | null>(null);
  const [gatewayForwarderBusy, setGatewayForwarderBusy] = useState(false);
  const [gatewayRuns, setGatewayRuns] = useState<RunInspectorGatewayRun[]>([]);
  const [gatewayRunFilter, setGatewayRunFilter] =
    useState<GatewayRunListFilter>("all");
  const [eventTimelineFilter, setEventTimelineFilter] =
    useState<RunInspectorEventFilter>("all");
  const [gatewayRunsError, setGatewayRunsError] = useState<string | null>(null);
  const [gatewayRunsBusy, setGatewayRunsBusy] = useState(false);
  const [gatewayLaunchInput, setGatewayLaunchInput] = useState(
    DEFAULT_GATEWAY_LAUNCH_INPUT,
  );
  const [gatewayLaunchError, setGatewayLaunchError] = useState<string | null>(null);
  const [gatewayLaunchBusy, setGatewayLaunchBusy] = useState(false);
  const [gatewayControlError, setGatewayControlError] = useState<string | null>(null);
  const [gatewayControlBusy, setGatewayControlBusy] = useState<
    "stop" | "allow" | "deny" | null
  >(null);
  const { setAfterTitle, setEnd, setTitle } = usePageHeader();
  const stateDisplay = describeRunInspectorState(inspector.state, inspector.snapshot);
  const desktopHeaderSignal = describeDesktopShellHeaderSignal(
    desktopStatus.state,
    desktopStatus.status,
    desktopStatus.error,
  );
  const gatewayControlState = describeGatewayRunControlState({
    events: eventStream.events,
    recentRuns: gatewayRuns,
    runId: gatewayRunId,
  });
  const gatewayRunDetail = describeGatewayRunDetail({
    events: eventStream.events,
    recentRuns: gatewayRuns,
    runId: gatewayRunId,
  });
  const gatewayRunList = describeGatewayRunList({
    events: eventStream.events,
    filter: gatewayRunFilter,
    recentRuns: gatewayRuns,
  });
  const pendingApprovalRunId = findLatestPendingApprovalRunId({
    events: eventStream.events,
    recentRuns: gatewayRuns,
    selectedRunId: gatewayRunId,
  });

  const handleGatewayRunIdChange = useCallback((value: string) => {
    setGatewayRunSelectionMode(value.trim() ? "manual" : "auto");
    setGatewayRunId(value);
  }, []);

  const followGatewayRun = useCallback(async () => {
    const runId = gatewayRunId.trim();
    if (!runId) {
      setGatewayForwarderError("Run ID is required");
      return;
    }

    setGatewayForwarderBusy(true);
    setGatewayForwarderError(null);
    try {
      const response = await api.followGatewayRunEvents(runId);
      setGatewayForwarder(response.forwarder);
      eventStream.refresh();
    } catch (err) {
      setGatewayForwarderError(errorMessage(err));
    } finally {
      setGatewayForwarderBusy(false);
    }
  }, [eventStream, gatewayRunId]);

  const refreshGatewayFollowStatus = useCallback(async () => {
    const runId = gatewayForwarder?.run_id ?? gatewayRunId.trim();
    if (!runId) {
      setGatewayForwarderError("Run ID is required");
      return;
    }

    setGatewayForwarderBusy(true);
    setGatewayForwarderError(null);
    try {
      const response = await api.getGatewayRunEventForwarder(runId);
      setGatewayForwarder(response.forwarder);
      eventStream.refresh();
    } catch (err) {
      setGatewayForwarderError(errorMessage(err));
    } finally {
      setGatewayForwarderBusy(false);
    }
  }, [eventStream, gatewayForwarder?.run_id, gatewayRunId]);

  const refreshGatewayRuns = useCallback(async () => {
    setGatewayRunsBusy(true);
    setGatewayRunsError(null);
    try {
      const response = await api.getGatewayRuns(10);
      setGatewayRuns(response.runs);
      if (!gatewayRunId.trim() && response.runs.length > 0) {
        setGatewayRunId(response.runs[0].run_id);
      }
    } catch (err) {
      setGatewayRunsError(errorMessage(err));
    } finally {
      setGatewayRunsBusy(false);
    }
  }, [gatewayRunId]);

  const launchGatewayRun = useCallback(async () => {
    const input = gatewayLaunchInput.trim();
    if (!input) {
      setGatewayLaunchError("Input is required");
      return;
    }

    setGatewayLaunchBusy(true);
    setGatewayLaunchError(null);
    try {
      const response = await api.launchGatewayRun({
        input,
        auto_follow: true,
      });
      const launchedRun: RunInspectorGatewayRun = {
        run_id: response.run.run_id,
        status: response.run.status,
        created_at: null,
        updated_at: null,
        session_id: null,
        model: null,
        last_event: "run.started",
        has_error: false,
      };
      setGatewayRunSelectionMode("manual");
      setGatewayRunId(response.run.run_id);
      setGatewayForwarder(response.forwarder);
      setGatewayRuns((runs) => [
        launchedRun,
        ...runs.filter((run) => run.run_id !== response.run.run_id),
      ]);
      eventStream.refresh();
    } catch (err) {
      setGatewayLaunchError(errorMessage(err));
    } finally {
      setGatewayLaunchBusy(false);
    }
  }, [eventStream, gatewayLaunchInput]);

  const handleGatewayLaunchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      void launchGatewayRun();
    },
    [launchGatewayRun],
  );

  const stopGatewayRun = useCallback(async () => {
    const runId = gatewayRunId.trim();
    if (!runId) {
      setGatewayControlError("Run ID is required");
      return;
    }

    setGatewayControlBusy("stop");
    setGatewayControlError(null);
    try {
      const response = await api.stopGatewayRun(runId);
      setGatewayRuns((runs) =>
        runs.map((run) =>
          run.run_id === response.run.run_id
            ? { ...run, status: response.run.status, last_event: "run.stopping" }
            : run,
        ),
      );
      eventStream.refresh();
    } catch (err) {
      setGatewayControlError(errorMessage(err));
    } finally {
      setGatewayControlBusy(null);
    }
  }, [eventStream, gatewayRunId]);

  const respondGatewayApproval = useCallback(
    async (choice: "once" | "deny") => {
      const runId = gatewayRunId.trim();
      if (!runId) {
        setGatewayControlError("Run ID is required");
        return;
      }

      const busyState = choice === "deny" ? "deny" : "allow";
      setGatewayControlBusy(busyState);
      setGatewayControlError(null);
      try {
        const response = await api.respondGatewayRunApproval(runId, { choice });
        setGatewayRuns((runs) =>
          runs.map((run) =>
            run.run_id === response.approval.run_id
              ? { ...run, status: "running", last_event: "approval.responded" }
              : run,
          ),
        );
        eventStream.refresh();
      } catch (err) {
        setGatewayControlError(errorMessage(err));
      } finally {
        setGatewayControlBusy(null);
      }
    },
    [eventStream, gatewayRunId],
  );

  const handleGatewayFollowSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      void followGatewayRun();
    },
    [followGatewayRun],
  );

  useEffect(() => {
    if (
      gatewayRunSelectionMode === "manual" ||
      !pendingApprovalRunId ||
      pendingApprovalRunId === gatewayRunId.trim()
    ) {
      return;
    }
    setGatewayRunId(pendingApprovalRunId);
  }, [gatewayRunId, gatewayRunSelectionMode, pendingApprovalRunId]);

  useEffect(() => {
    attention.refresh();
    desktopStatus.refresh();
    memoryWorkbench.refresh();
  }, [
    attention.refresh,
    desktopStatus.refresh,
    eventStream.lastUpdatedAt,
    inspector.lastUpdatedAt,
    memoryWorkbench.refresh,
  ]);

  useLayoutEffect(() => {
    setTitle("Run Inspector");
    setAfterTitle(
      <span className="flex min-w-0 flex-wrap items-center gap-1.5">
        <Badge tone={BADGE_TONE[stateDisplay.tone]} className="text-[10px]">
          {stateDisplay.label}
        </Badge>
        <Badge
          tone={BADGE_TONE[desktopHeaderSignal.tone]}
          className="hidden max-w-[10rem] truncate text-[10px] sm:inline-flex"
          title={desktopHeaderSignal.message}
        >
          {desktopHeaderSignal.label}
        </Badge>
      </span>,
    );
    setEnd(
      <div className="flex w-full min-w-0 items-center justify-end gap-2">
        <span className="hidden min-w-0 truncate text-xs text-muted-foreground sm:inline">
          {inspector.lastUpdatedAt
            ? `Refreshed ${formatDateTime(inspector.lastUpdatedAt)}`
            : "Not refreshed"}
        </span>
        <Button
          type="button"
          size="sm"
          outlined
          onClick={inspector.refresh}
          disabled={inspector.isLoading}
          prefix={inspector.isLoading ? <Spinner /> : <RefreshCw />}
        >
          Refresh
        </Button>
      </div>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [
    inspector.isLoading,
    inspector.lastUpdatedAt,
    inspector.refresh,
    desktopHeaderSignal.label,
    desktopHeaderSignal.message,
    desktopHeaderSignal.tone,
    setAfterTitle,
    setEnd,
    setTitle,
    stateDisplay.label,
    stateDisplay.tone,
  ]);

  const snapshot = inspector.snapshot;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <PluginSlot name="run-inspector:top" />

      <RunInspectorBanner
        error={inspector.error}
        response={inspector.response}
        snapshot={snapshot}
        state={stateDisplay}
      />

      {inspector.state === "loading" && snapshot === null ? (
        <Card>
          <CardContent className="flex min-h-[240px] items-center justify-center">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Spinner />
              <span>Loading run state</span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <AttentionPreviewCard
              error={attention.error}
              isLoading={attention.isLoading}
              lastUpdatedAt={attention.lastUpdatedAt}
              notificationDisplay={browserNotifications.display}
              notificationEnabled={browserNotifications.enabled}
              notificationIsEnabling={browserNotifications.isEnabling}
              onDisableNotifications={browserNotifications.disable}
              onEnableNotifications={browserNotifications.enable}
              onRefresh={attention.refresh}
              signals={attention.signals}
              state={attention.state}
            />
            <MultiAgentMemoryWorkbenchCard
              error={memoryWorkbench.error}
              isLoading={memoryWorkbench.isLoading}
              lastUpdatedAt={memoryWorkbench.lastUpdatedAt}
              onRefresh={memoryWorkbench.refresh}
              state={memoryWorkbench.state}
              workbench={memoryWorkbench.workbench}
            />
            <OverviewCard
              response={inspector.response}
              snapshot={snapshot}
              state={stateDisplay}
            />
            <ActiveToolCard snapshot={snapshot} />
            <RecoveryCard snapshot={snapshot} />
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <RuntimeCard snapshot={snapshot} />
            <DesktopShellStatusCard
              error={desktopStatus.error}
              isLoading={desktopStatus.isLoading}
              lastUpdatedAt={desktopStatus.lastUpdatedAt}
              onRefresh={desktopStatus.refresh}
              state={desktopStatus.state}
              status={desktopStatus.status}
            />
            <HealthCard snapshot={snapshot} />
            <GatewayRunFollowCard
              busy={gatewayForwarderBusy}
              controlBusy={gatewayControlBusy}
              controlError={gatewayControlError}
              controlState={gatewayControlState}
              error={gatewayForwarderError}
              forwarder={gatewayForwarder}
              runDetail={gatewayRunDetail}
              launchBusy={gatewayLaunchBusy}
              launchError={gatewayLaunchError}
              launchInput={gatewayLaunchInput}
              onRefresh={refreshGatewayFollowStatus}
              onRefreshRuns={refreshGatewayRuns}
              onRunFilterChange={setGatewayRunFilter}
              onLaunchInputChange={setGatewayLaunchInput}
              onLaunchSubmit={handleGatewayLaunchSubmit}
              onApprovalDeny={() => void respondGatewayApproval("deny")}
              onApprovalOnce={() => void respondGatewayApproval("once")}
              onRunIdChange={handleGatewayRunIdChange}
              onStop={stopGatewayRun}
              recentRuns={gatewayRuns}
              runFilter={gatewayRunFilter}
              runList={gatewayRunList}
              recentRunsBusy={gatewayRunsBusy}
              recentRunsError={gatewayRunsError}
              onSubmit={handleGatewayFollowSubmit}
              runId={gatewayRunId}
            />
            <EventTimelineCard
              error={eventStream.error}
              events={eventStream.events}
              filter={eventTimelineFilter}
              lastUpdatedAt={eventStream.lastUpdatedAt}
              onFilterChange={setEventTimelineFilter}
              state={eventStream.state}
            />
            <PrivacyCard snapshot={snapshot} />
          </div>
        </div>
      )}

      <PluginSlot name="run-inspector:bottom" />
    </div>
  );
}

function AttentionPreviewCard({
  error,
  isLoading,
  lastUpdatedAt,
  notificationDisplay,
  notificationEnabled,
  notificationIsEnabling,
  onDisableNotifications,
  onEnableNotifications,
  onRefresh,
  signals,
  state,
}: {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  notificationDisplay: BrowserNotificationOptInDisplay;
  notificationEnabled: boolean;
  notificationIsEnabling: boolean;
  onDisableNotifications: () => void;
  onEnableNotifications: () => Promise<void>;
  onRefresh: () => void;
  signals: RunInspectorAttentionSignal[];
  state: RunInspectorAttentionState;
}) {
  const display = describeAttentionPreview(state, signals, error);
  const newestFirst = [...signals].sort((left, right) =>
    right.timestamp.localeCompare(left.timestamp),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Bell className="h-4 w-4 shrink-0" />
            <span className="truncate">Attention Preview</span>
          </span>
          <Badge tone={BADGE_TONE[display.tone]} className="shrink-0 text-[10px]">
            {display.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 break-words">
            {formatDisplayValue(error, display.message)}
          </span>
          <span className="flex shrink-0 items-center gap-2">
            <span>{lastUpdatedAt ? formatDateTime(lastUpdatedAt) : "Not refreshed"}</span>
            <Button
              type="button"
              size="sm"
              outlined
              disabled={isLoading}
              onClick={onRefresh}
              prefix={isLoading ? <Spinner /> : <RefreshCw />}
            >
              Refresh
            </Button>
          </span>
        </div>

        <BrowserNotificationOptInRow
          display={notificationDisplay}
          enabled={notificationEnabled}
          isEnabling={notificationIsEnabling}
          onDisable={onDisableNotifications}
          onEnable={onEnableNotifications}
        />

        {isLoading && newestFirst.length === 0 ? (
          <div className="flex items-center gap-3 border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            <Spinner />
            <span>Loading safe attention signals</span>
          </div>
        ) : newestFirst.length === 0 ? (
          <p className="border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            No current attention signals
          </p>
        ) : (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {newestFirst.map((signal) => {
              const tone = attentionSignalTone(signal);
              return (
                <div
                  key={signal.dedupe_key}
                  className="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className={cn("truncate text-sm font-medium", TONE_CLASSES[tone])}>
                        {formatDisplayValue(signal.title)}
                      </span>
                      <Badge tone={BADGE_TONE[tone]} className="text-[10px]">
                        {formatDisplayValue(signal.kind.replaceAll("_", " "))}
                      </Badge>
                      <Badge tone="outline" className="text-[10px]">
                        {formatDisplayValue(signal.privacy_class)}
                      </Badge>
                    </div>
                    <p className="mt-1 break-words text-xs text-muted-foreground">
                      {formatDisplayValue(signal.body, "No details")}
                    </p>
                    <p className="mt-1 truncate font-mono-ui text-[10px] text-muted-foreground/80">
                      {formatDisplayValue(signal.dedupe_key)}
                    </p>
                  </div>
                  <span className="font-mono-ui text-xs text-muted-foreground">
                    {formatRunInspectorEventTime(signal.timestamp)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MultiAgentMemoryWorkbenchCard({
  error,
  isLoading,
  lastUpdatedAt,
  onRefresh,
  state,
  workbench,
}: {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  onRefresh: () => void;
  state: RunInspectorMemoryWorkbenchState;
  workbench: RunInspectorMemoryWorkbench | null;
}) {
  const display = describeMemoryWorkbenchState(state, workbench, error);
  const activeWork = workbench?.active_work ?? [];
  const checkpoint = workbench?.checkpoint ?? null;
  const memory = workbench?.memory ?? null;
  const queue = workbench?.long_term_queue ?? null;
  const journal = workbench?.skills_journal ?? null;
  const providers = memory?.providers ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Database className="h-4 w-4 shrink-0" />
            <span className="truncate">Multi-Agent Memory</span>
          </span>
          <Badge tone={BADGE_TONE[display.tone]} className="shrink-0 text-[10px]">
            {display.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 break-words">
            {formatDisplayValue(error, display.message)}
          </span>
          <span className="flex shrink-0 items-center gap-2">
            <span>{lastUpdatedAt ? formatDateTime(lastUpdatedAt) : "Not refreshed"}</span>
            <Button
              type="button"
              size="sm"
              outlined
              disabled={isLoading}
              onClick={onRefresh}
              prefix={isLoading ? <Spinner /> : <RefreshCw />}
            >
              Refresh
            </Button>
          </span>
        </div>

        {isLoading && workbench === null ? (
          <div className="flex items-center gap-3 border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            <Spinner />
            <span>Loading safe memory workbench</span>
          </div>
        ) : null}

        <div className="grid min-w-0 gap-2 sm:grid-cols-2">
          <Metric
            icon={<Activity className="h-4 w-4" />}
            label="Work"
            tone={display.tone}
            value={`${activeWork.length} active`}
          />
          <Metric
            icon={<Database className="h-4 w-4" />}
            label="Memory"
            tone={memoryProviderTone(memory?.status ?? "unavailable")}
            value={formatDisplayValue(memory?.status, "Unavailable")}
          />
          <Metric
            icon={<FileWarning className="h-4 w-4" />}
            label="Queue"
            tone={(queue?.unresolved_count ?? 0) > 0 ? "warning" : "muted"}
            value={`${queue?.unresolved_count ?? 0} unresolved`}
          />
          <Metric
            icon={<CheckCircle2 className="h-4 w-4" />}
            label="Journal"
            value={`${journal?.entries.length ?? 0} accepted`}
          />
        </div>

        {checkpoint ? (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            <DetailRow
              label="Current"
              value={formatDisplayValue(checkpoint.current_task_id, "None")}
            />
            <DetailRow
              label="Next"
              value={formatDisplayValue(checkpoint.next_step, "No next step")}
            />
            <DetailRow
              label="Verified"
              value={formatDisplayValue(checkpoint.last_verification, "Unknown")}
            />
            <DetailRow
              label="Blocked"
              value={String(checkpoint.blocked_tasks.length)}
            />
          </div>
        ) : null}

        {activeWork.length === 0 ? (
          <p className="border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            No active multi-agent work items
          </p>
        ) : (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {activeWork.map((item, index) => (
              <div
                key={`${item.work_id ?? "work"}-${index}`}
                className="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="truncate font-mono-ui text-sm font-medium">
                      {formatDisplayValue(item.work_id, "Unknown work")}
                    </span>
                    <Badge tone="outline" className="text-[10px]">
                      {formatDisplayValue(item.role, "agent")}
                    </Badge>
                    <Badge tone={BADGE_TONE[display.tone]} className="text-[10px]">
                      {formatDisplayValue(item.status, "unknown")}
                    </Badge>
                  </div>
                  <p className="mt-1 break-words text-xs text-muted-foreground">
                    {formatDisplayValue(item.summary, "No details")}
                  </p>
                </div>
                <span className="font-mono-ui text-xs text-muted-foreground">
                  {formatRunInspectorEventTime(item.timestamp ?? "")}
                </span>
              </div>
            ))}
          </div>
        )}

        {providers.length > 0 ? (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {providers.map((provider, index) => (
              <div
                key={`${provider.name ?? "provider"}-${index}`}
                className="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {formatDisplayValue(provider.name, "Unknown provider")}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {provider.tool_names.length} tools -{" "}
                    {provider.initialized === true ? "initialized" : "not initialized"}
                  </p>
                </div>
                <Badge
                  tone={BADGE_TONE[memoryProviderTone(provider.availability)]}
                  className="w-fit text-[10px]"
                >
                  {formatDisplayValue(provider.availability)}
                </Badge>
              </div>
            ))}
          </div>
        ) : null}

        {workbench?.degraded_reason ? (
          <p className="break-words border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
            {formatDisplayValue(workbench.degraded_reason)}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function BrowserNotificationOptInRow({
  display,
  enabled,
  isEnabling,
  onDisable,
  onEnable,
}: {
  display: BrowserNotificationOptInDisplay;
  enabled: boolean;
  isEnabling: boolean;
  onDisable: () => void;
  onEnable: () => Promise<void>;
}) {
  const canEnable =
    display.state === "disabled" ||
    display.state === "promptable" ||
    display.state === "degraded";
  const canDisable = enabled && display.state === "enabled";

  return (
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border border-border bg-background px-3 py-2">
      <div className="flex min-w-0 flex-col gap-1">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <Badge tone={BADGE_TONE[display.tone]} className="text-[10px]">
            {display.label}
          </Badge>
          <span className="break-words text-xs text-muted-foreground">
            {display.message}
          </span>
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {canDisable ? (
          <Button type="button" size="sm" outlined onClick={onDisable}>
            Disable
          </Button>
        ) : canEnable ? (
          <Button
            type="button"
            size="sm"
            outlined
            disabled={isEnabling}
            onClick={onEnable}
            prefix={isEnabling ? <Spinner /> : <Bell />}
          >
            Enable
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function RunInspectorBanner({
  error,
  response,
  snapshot,
  state,
}: {
  error: string | null;
  response: RunInspectorResponse | null;
  snapshot: RunInspectorSnapshot | null;
  state: StateDisplay;
}) {
  const degraded = snapshot?.degraded_reason;
  const message = error ?? degraded;
  if (!message && response?.ok !== false) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex min-w-0 items-start gap-3 border px-4 py-3 text-sm",
        state.tone === "destructive"
          ? "border-destructive/30 bg-destructive/10 text-destructive"
          : "border-warning/30 bg-warning/10 text-warning",
      )}
      role="status"
    >
      {state.tone === "destructive" ? (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
      ) : (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      )}
      <div className="min-w-0">
        <p className="font-medium">{state.label}</p>
        <p className="break-words text-xs opacity-80">
          {formatDisplayValue(message, "Snapshot returned degraded state")}
        </p>
      </div>
    </div>
  );
}

function OverviewCard({
  response,
  snapshot,
  state,
}: {
  response: RunInspectorResponse | null;
  snapshot: RunInspectorSnapshot | null;
  state: StateDisplay;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Current State
        </CardTitle>
      </CardHeader>
      <CardContent className="grid min-w-0 gap-3 sm:grid-cols-2">
        <Metric
          icon={<Activity className="h-4 w-4" />}
          label="Run"
          tone={state.tone}
          value={state.label}
        />
        <Metric
          icon={<CheckCircle2 className="h-4 w-4" />}
          label="Snapshot"
          value={responseHealthLabel(response)}
          tone={response?.ok === false ? "warning" : response ? "success" : "muted"}
        />
        <Metric
          icon={<Terminal className="h-4 w-4" />}
          label="Source"
          value={snapshot?.source ?? "Unknown"}
        />
        <Metric
          icon={<Clock className="h-4 w-4" />}
          label="Last Activity"
          value={formatDateTime(snapshot?.last_activity_at ?? null)}
        />
      </CardContent>
    </Card>
  );
}

function RuntimeCard({ snapshot }: { snapshot: RunInspectorSnapshot | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-4 w-4" />
          Runtime Context
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col divide-y divide-border/70 p-0">
        <DetailRow label="Run ID" value={formatDisplayValue(snapshot?.run_id)} />
        <DetailRow label="Session ID" value={formatDisplayValue(snapshot?.session_id)} />
        <DetailRow label="Workspace" value={formatDisplayValue(snapshot?.workspace)} />
        <DetailRow label="Reason" value={formatDisplayValue(snapshot?.reason, "None")} />
      </CardContent>
    </Card>
  );
}

function DesktopShellStatusCard({
  error,
  isLoading,
  lastUpdatedAt,
  onRefresh,
  state,
  status,
}: {
  error: string | null;
  isLoading: boolean;
  lastUpdatedAt: string | null;
  onRefresh: () => void;
  state: RunInspectorDesktopStatusState;
  status: RunInspectorDesktopStatus | null;
}) {
  const display = describeDesktopShellStatus(state, status, error);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Monitor className="h-4 w-4 shrink-0" />
            <span className="truncate">Desktop Shell</span>
          </span>
          <Badge tone={BADGE_TONE[display.tone]} className="shrink-0 text-[10px]">
            {display.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 break-words">
            {formatDisplayValue(error, display.message)}
          </span>
          <span className="flex shrink-0 items-center gap-2">
            <span>{lastUpdatedAt ? formatDateTime(lastUpdatedAt) : "Not refreshed"}</span>
            <Button
              type="button"
              size="sm"
              outlined
              disabled={isLoading}
              onClick={onRefresh}
              prefix={isLoading ? <Spinner /> : <RefreshCw />}
            >
              Refresh
            </Button>
          </span>
        </div>
        <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
          <DetailRow label="Source" value={describeDesktopShellSource(status)} />
          <DetailRow label="Health" value={formatDisplayValue(status?.health)} />
          <DetailRow label="PID" value={formatDisplayValue(status?.pid ? String(status.pid) : null, "None")} />
          <DetailRow label="PID Status" value={formatDisplayValue(status?.pid_status)} />
          <DetailRow label="Started" value={formatDisplayValue(status?.started_at ? formatDateTime(status.started_at) : null, "Unknown")} />
          <DetailRow label="Host" value={formatDisplayValue(status?.host)} />
          <DetailRow label="Route" value={formatDisplayValue(status?.route)} />
          <DetailRow label="URL" value={formatDisplayValue(status?.url)} />
          <DetailRow label="Manual URL" value={formatDisplayValue(status?.manual_url, "None")} />
          <DetailRow label="Reuse" value={formatDisplayValue(status?.reuse_command, "None")} />
          <DetailRow label="Stop" value={formatDisplayValue(status?.stop_command, "None")} />
        </div>
      </CardContent>
    </Card>
  );
}

function ActiveToolCard({ snapshot }: { snapshot: RunInspectorSnapshot | null }) {
  const tool = snapshot?.active_tool;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="h-4 w-4" />
          Active Tool
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col divide-y divide-border/70 p-0">
        <DetailRow label="Name" value={formatDisplayValue(tool?.name, "None")} />
        <DetailRow label="Call ID" value={formatDisplayValue(tool?.call_id, "None")} />
        <DetailRow label="Duration" value={formatDurationMs(tool?.duration_ms ?? null)} />
        <DetailRow
          label="Args"
          value={formatDisplayValue(formatArgsSummary(tool?.args_summary ?? null))}
        />
      </CardContent>
    </Card>
  );
}

function HealthCard({ snapshot }: { snapshot: RunInspectorSnapshot | null }) {
  const toolCounts = countToolHealth(snapshot?.tool_health ?? []);
  const mcpCounts = countMcpHealth(snapshot?.mcp_health ?? []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4" />
          Dependency Health
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-4">
        <HealthSummary
          title="Tools"
          items={[
            ["available", toolCounts.available, "success"],
            ["running", toolCounts.running, "primary"],
            ["unavailable", toolCounts.unavailable, "warning"],
            ["failed", toolCounts.failed, "destructive"],
            ["unknown", toolCounts.unknown, "muted"],
          ]}
        />
        <HealthRows
          emptyLabel="No tool health rows"
          items={(snapshot?.tool_health ?? []).map((item) => ({
            key: `tool:${item.name ?? "unknown"}:${item.toolset ?? "unknown"}`,
            label: formatDisplayValue(item.name, "Unknown tool"),
            detail: formatDisplayValue(item.toolset ?? item.reason, "No toolset"),
            status: item.status,
            tone: toolTone(item.status),
          }))}
        />

        <HealthSummary
          title="MCP"
          items={[
            ["connected", mcpCounts.connected, "success"],
            ["degraded", mcpCounts.degraded, "warning"],
            ["failed", mcpCounts.failed, "destructive"],
            ["unknown", mcpCounts.unknown, "muted"],
          ]}
        />
        <HealthRows
          emptyLabel="No MCP health rows"
          items={(snapshot?.mcp_health ?? []).map((item) => ({
            key: `mcp:${item.name ?? "unknown"}`,
            label: formatDisplayValue(item.name, "Unknown server"),
            detail: formatDisplayValue(mcpDetail(item)),
            status: item.status,
            tone: mcpTone(item.status),
          }))}
        />
      </CardContent>
    </Card>
  );
}

function RecoveryCard({ snapshot }: { snapshot: RunInspectorSnapshot | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileWarning className="h-4 w-4" />
          Recovery
        </CardTitle>
      </CardHeader>
      <CardContent className="grid min-w-0 gap-3 sm:grid-cols-2">
        <Metric
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Hint"
          value={formatDisplayValue(snapshot?.recovery_hint, "None")}
          tone={snapshot?.recovery_hint ? "warning" : "muted"}
        />
        <Metric
          icon={<FileWarning className="h-4 w-4" />}
          label="Degraded"
          value={formatDisplayValue(snapshot?.degraded_reason, "None")}
          tone={snapshot?.degraded_reason ? "warning" : "muted"}
        />
      </CardContent>
    </Card>
  );
}

function PrivacyCard({ snapshot }: { snapshot: RunInspectorSnapshot | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4" />
          Privacy Flags
        </CardTitle>
      </CardHeader>
      <CardContent>
        {snapshot?.privacy_flags.length ? (
          <div className="flex flex-wrap gap-2">
            {snapshot.privacy_flags.map((flag) => (
              <Badge key={flag} tone="outline" className="max-w-full text-[10px]">
                <span className="truncate">{formatDisplayValue(flag)}</span>
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No privacy flags</p>
        )}
      </CardContent>
    </Card>
  );
}

function GatewayRunFollowCard({
  busy,
  controlBusy,
  controlError,
  controlState,
  error,
  forwarder,
  runDetail,
  launchBusy,
  launchError,
  launchInput,
  onApprovalDeny,
  onApprovalOnce,
  onRefresh,
  onRefreshRuns,
  onRunFilterChange,
  onLaunchInputChange,
  onLaunchSubmit,
  onRunIdChange,
  onStop,
  recentRuns,
  recentRunsBusy,
  recentRunsError,
  onSubmit,
  runId,
  runFilter,
  runList,
}: {
  busy: boolean;
  controlBusy: "stop" | "allow" | "deny" | null;
  controlError: string | null;
  controlState: GatewayRunControlState;
  error: string | null;
  forwarder: RunInspectorGatewayForwarder | null;
  runDetail: GatewayRunDetailState | null;
  launchBusy: boolean;
  launchError: string | null;
  launchInput: string;
  onApprovalDeny: () => void;
  onApprovalOnce: () => void;
  onRefresh: () => void;
  onRefreshRuns: () => void;
  onRunFilterChange: (value: GatewayRunListFilter) => void;
  onLaunchInputChange: (value: string) => void;
  onLaunchSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRunIdChange: (value: string) => void;
  onStop: () => void;
  recentRuns: RunInspectorGatewayRun[];
  recentRunsBusy: boolean;
  recentRunsError: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  runId: string;
  runFilter: GatewayRunListFilter;
  runList: GatewayRunListSummary;
}) {
  const display = describeGatewayForwarder(forwarder);
  const canSubmit = runId.trim().length > 0 && !busy;
  const canLaunch = launchInput.trim().length > 0 && !launchBusy;
  const canControl = runId.trim().length > 0 && !controlBusy && !busy && !launchBusy;
  const canApprove = canControl && controlState.approvalPending;
  const canStop = canControl && controlState.stopAvailable;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Link className="h-4 w-4 shrink-0" />
            <span className="truncate">Gateway Run Follow</span>
          </span>
          <Badge tone={BADGE_TONE[display.tone]} className="shrink-0 text-[10px]">
            {display.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <form className="grid min-w-0 gap-2" onSubmit={onLaunchSubmit}>
          <textarea
            aria-label="Gateway launch input"
            className="min-h-[72px] w-full resize-y border border-input bg-transparent px-3 py-2 text-xs shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            onChange={(event) => onLaunchInputChange(event.target.value)}
            placeholder="Ask gateway to inspect current run health"
            value={launchInput}
          />
          <div className="flex min-w-0 justify-end">
            <Button
              type="submit"
              size="sm"
              disabled={!canLaunch}
              prefix={launchBusy ? <Spinner /> : <Play />}
            >
              Start
            </Button>
          </div>
        </form>

        {launchError ? (
          <p className="break-words border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {formatDisplayValue(launchError)}
          </p>
        ) : null}

        <form
          className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto_auto]"
          onSubmit={onSubmit}
        >
          <Input
            aria-label="Gateway run id"
            className="h-9 font-mono-ui text-xs"
            onChange={(event) => onRunIdChange(event.target.value)}
            placeholder="run_..."
            value={runId}
          />
          <Button
            type="submit"
            size="sm"
            disabled={!canSubmit}
            prefix={busy ? <Spinner /> : <Play />}
          >
            Follow
          </Button>
          <Button
            type="button"
            size="sm"
            outlined
            disabled={recentRunsBusy}
            onClick={onRefreshRuns}
            prefix={recentRunsBusy ? <Spinner /> : <RefreshCw />}
          >
            Runs
          </Button>
          <Button
            type="button"
            size="sm"
            outlined
            disabled={busy || (!forwarder && !runId.trim())}
            onClick={onRefresh}
            prefix={busy ? <Spinner /> : <RefreshCw />}
          >
            Status
          </Button>
        </form>

        <div className="grid min-w-0 gap-2 sm:grid-cols-3">
          <Button
            type="button"
            size="sm"
            outlined={!controlState.approvalHighlighted}
            disabled={!canApprove}
            onClick={onApprovalOnce}
            prefix={controlBusy === "allow" ? <Spinner /> : <CheckCircle2 />}
          >
            Allow
          </Button>
          <Button
            type="button"
            size="sm"
            outlined={!controlState.approvalHighlighted}
            disabled={!canApprove}
            onClick={onApprovalDeny}
            prefix={controlBusy === "deny" ? <Spinner /> : <Shield />}
          >
            Deny
          </Button>
          <Button
            type="button"
            size="sm"
            outlined={!controlState.stopHighlighted}
            disabled={!canStop}
            onClick={onStop}
            prefix={controlBusy === "stop" ? <Spinner /> : <XCircle />}
          >
            Stop
          </Button>
        </div>

        {controlError ? (
          <p className="break-words border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {formatDisplayValue(controlError)}
          </p>
        ) : null}

        {runDetail ? <SelectedGatewayRunDetail detail={runDetail} /> : null}

        {controlState.approvalDetail ? (
          <div className="flex min-w-0 flex-col divide-y divide-warning/30 border border-warning/30 bg-warning/10">
            <DetailRow
              label="Approval"
              value={formatDisplayValue(
                controlState.approvalDetail.message,
                "Pending request",
              )}
            />
            <DetailRow
              label="Tool"
              value={formatDisplayValue(controlState.approvalDetail.tool, "Unknown")}
            />
            <DetailRow
              label="Status"
              value={formatDisplayValue(
                controlState.approvalDetail.status,
                "waiting",
              )}
            />
            <DetailRow
              label="Time"
              value={formatRunInspectorEventTime(
                controlState.approvalDetail.timestamp,
              )}
            />
          </div>
        ) : null}

        {recentRuns.length > 0 ? (
          <GatewayRunFilterControl
            filter={runFilter}
            onChange={onRunFilterChange}
            summary={runList}
          />
        ) : null}

        {recentRuns.length > 0 && runList.items.length === 0 ? (
          <p className="border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            {runList.emptyLabel}
          </p>
        ) : null}

        {runList.items.length > 0 ? (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {runList.items.map((item) => {
              const run = item.run;
              const selected = run.run_id === runId.trim();
              return (
                <button
                  key={run.run_id}
                  className={cn(
                    "grid min-w-0 gap-1 px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground sm:grid-cols-[minmax(0,1fr)_auto]",
                    selected ? "bg-secondary/60" : "hover:bg-secondary/40",
                  )}
                  onClick={() => onRunIdChange(run.run_id)}
                  type="button"
                >
                  <span className="min-w-0 truncate font-mono-ui text-xs">
                    {formatDisplayValue(run.run_id)}
                  </span>
                  <span className="flex min-w-0 flex-wrap items-center gap-2">
                    <Badge tone={BADGE_TONE[item.tone]} className="w-fit text-[10px]">
                      {formatDisplayValue(run.status)}
                    </Badge>
                    {item.latestEvent ? (
                      <span className="truncate text-[10px] text-muted-foreground">
                        {formatDisplayValue(item.latestEvent)}
                      </span>
                    ) : null}
                    {item.attention ? (
                      <Badge tone="warning" className="w-fit text-[10px]">
                        Needs action
                      </Badge>
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}

        {recentRunsError ? (
          <p className="break-words border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
            {formatDisplayValue(recentRunsError)}
          </p>
        ) : null}

        <div className="grid min-w-0 gap-2 sm:grid-cols-2">
          <Metric
            icon={<Shield className="h-4 w-4" />}
            label="Control"
            tone={controlState.tone}
            value={controlState.message}
          />
          <Metric
            icon={<Activity className="h-4 w-4" />}
            label="Forwarder"
            tone={display.tone}
            value={display.message}
          />
          <Metric
            icon={<Clock className="h-4 w-4" />}
            label="Updated"
            value={formatDateTime(forwarder?.updated_at ?? null)}
          />
        </div>

        {forwarder ? (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            <DetailRow label="Run ID" value={formatDisplayValue(forwarder.run_id)} />
            <DetailRow
              label="Events"
              value={String(forwarder.events_forwarded ?? 0)}
            />
            <DetailRow
              label="Gateway"
              value={formatDisplayValue(forwarder.gateway_url, "Unknown")}
            />
            <DetailRow
              label="Error"
              value={formatDisplayValue(forwarder.last_error, "None")}
            />
          </div>
        ) : null}

        {error ? (
          <p className="break-words border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {formatDisplayValue(error)}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

const GATEWAY_RUN_FILTERS: Array<{
  countKey: keyof GatewayRunListSummary["counts"];
  label: string;
  value: GatewayRunListFilter;
}> = [
  { countKey: "all", label: "All", value: "all" },
  { countKey: "attention", label: "Needs action", value: "attention" },
  { countKey: "active", label: "Active", value: "active" },
  { countKey: "terminal", label: "Done", value: "terminal" },
];

function GatewayRunFilterControl({
  filter,
  onChange,
  summary,
}: {
  filter: GatewayRunListFilter;
  onChange: (value: GatewayRunListFilter) => void;
  summary: GatewayRunListSummary;
}) {
  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-4">
      {GATEWAY_RUN_FILTERS.map((item) => {
        const selected = filter === item.value;
        return (
          <Button
            key={item.value}
            aria-pressed={selected}
            type="button"
            size="sm"
            outlined={!selected}
            onClick={() => onChange(item.value)}
          >
            <span className="flex min-w-0 items-center justify-center gap-2">
              <span className="truncate">{item.label}</span>
              <Badge tone={selected ? "secondary" : "outline"} className="text-[10px]">
                {summary.counts[item.countKey]}
              </Badge>
            </span>
          </Button>
        );
      })}
    </div>
  );
}

function SelectedGatewayRunDetail({ detail }: { detail: GatewayRunDetailState }) {
  return (
    <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border bg-secondary/10">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 px-3 py-2">
        <span className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
          Selected Run
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <Badge tone={BADGE_TONE[detail.tone]} className="w-fit text-[10px]">
            {formatDisplayValue(detail.status)}
          </Badge>
          <Badge tone="outline" className="w-fit text-[10px]">
            {formatDisplayValue(detail.source.replaceAll("_", " "))}
          </Badge>
        </span>
      </div>
      <DetailRow label="Run ID" value={formatDisplayValue(detail.runId)} />
      <DetailRow label="Last Event" value={formatDisplayValue(detail.lastEvent)} />
      <DetailRow label="Events" value={String(detail.eventCount)} />
      <DetailRow label="Updated" value={formatDateTime(detail.updatedAt)} />
      <DetailRow label="Last Seen" value={formatDateTime(detail.lastEventAt)} />
      <DetailRow label="Session" value={formatDisplayValue(detail.sessionId, "Unknown")} />
      <DetailRow label="Model" value={formatDisplayValue(detail.model, "Unknown")} />
      <DetailRow
        label="Known"
        value={detail.known ? "Summary or event found" : "Manual selection"}
      />
      <DetailRow label="Error" value={detail.hasError ? "Yes" : "No"} />
      {detail.lastMessage ? (
        <DetailRow
          label="Last Detail"
          value={formatDisplayValue(detail.lastMessage, "No details")}
        />
      ) : null}
    </div>
  );
}

function EventTimelineCard({
  error,
  events,
  filter,
  lastUpdatedAt,
  onFilterChange,
  state,
}: {
  error: string | null;
  events: RunInspectorEvent[];
  filter: RunInspectorEventFilter;
  lastUpdatedAt: string | null;
  onFilterChange: (filter: RunInspectorEventFilter) => void;
  state: RunInspectorEventStreamState;
}) {
  const stream = describeRunInspectorEventStream(state);
  const filteredEvents = filterRunInspectorEvents(events, filter);
  const summary = summarizeRunInspectorEvents(events);
  const latestDisplay = summary.latest ? describeRunInspectorEvent(summary.latest) : null;
  const newestFirst = [...filteredEvents].reverse();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Activity className="h-4 w-4 shrink-0" />
            <span className="truncate">Event Timeline</span>
          </span>
          <Badge tone={BADGE_TONE[stream.tone]} className="shrink-0 text-[10px]">
            {stream.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 truncate">
            {formatDisplayValue(error, stream.message)}
          </span>
          <span className="shrink-0">
            {lastUpdatedAt ? formatDateTime(lastUpdatedAt) : "Not refreshed"}
          </span>
        </div>

        <div className="grid min-w-0 gap-2 sm:grid-cols-4">
          <Metric
            icon={<Activity className="h-4 w-4" />}
            label="Recent"
            value={String(summary.total)}
            tone={summary.total > 0 ? "primary" : "muted"}
          />
          <Metric
            icon={<AlertTriangle className="h-4 w-4" />}
            label="Attention"
            value={String(summary.attention)}
            tone={summary.attention > 0 ? "warning" : "muted"}
          />
          <Metric
            icon={<XCircle className="h-4 w-4" />}
            label="Failed"
            value={String(summary.failed)}
            tone={summary.failed > 0 ? "destructive" : "muted"}
          />
          <Metric
            icon={<Clock className="h-4 w-4" />}
            label="Latest"
            value={
              summary.latest
                ? `${formatRunInspectorEventTime(summary.latest.timestamp)} ${latestDisplay?.label ?? summary.latest.type}`
                : "None"
            }
            tone={latestDisplay?.tone ?? "muted"}
          />
        </div>

        <div className="grid min-w-0 gap-2 sm:grid-cols-5">
          {RUN_INSPECTOR_EVENT_FILTERS.map((item) => {
            const selected = filter === item;
            const count = filterRunInspectorEvents(events, item).length;
            return (
              <Button
                key={item}
                aria-pressed={selected}
                type="button"
                size="sm"
                outlined={!selected}
                onClick={() => onFilterChange(item)}
              >
                <span className="flex min-w-0 items-center justify-center gap-2">
                  <span className="truncate capitalize">{item}</span>
                  <Badge tone={selected ? "secondary" : "outline"} className="text-[10px]">
                    {count}
                  </Badge>
                </span>
              </Button>
            );
          })}
        </div>

        {newestFirst.length === 0 ? (
          <p className="border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            No recent events
          </p>
        ) : (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {newestFirst.map((event) => {
              const display = describeRunInspectorEvent(event);
              const context = describeRunInspectorEventContext(event);
              return (
                <div
                  key={event.id}
                  className="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[84px_minmax(0,1fr)]"
                >
                  <span className="font-mono-ui text-xs text-muted-foreground">
                    {formatRunInspectorEventTime(event.timestamp)}
                  </span>
                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className={cn("truncate text-sm font-medium", TONE_CLASSES[display.tone])}>
                        {formatDisplayValue(display.label)}
                      </span>
                      {event.status ? (
                        <Badge tone={BADGE_TONE[display.tone]} className="text-[10px]">
                          {formatDisplayValue(event.status)}
                        </Badge>
                      ) : null}
                      <Badge tone="outline" className="text-[10px]">
                        {formatDisplayValue(event.source)}
                      </Badge>
                    </div>
                    <p className="mt-1 break-words text-xs text-muted-foreground">
                      {formatDisplayValue(display.message, "No details")}
                    </p>
                    {context ? (
                      <p className="mt-1 break-all font-mono-ui text-[10px] text-muted-foreground/80">
                        {formatDisplayValue(context)}
                      </p>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({
  icon,
  label,
  tone = "muted",
  value,
}: {
  icon: ReactNode;
  label: string;
  tone?: Tone;
  value: string;
}) {
  return (
    <div className="flex min-w-0 items-start gap-3 border border-border bg-secondary/20 p-3">
      <span className={cn("mt-0.5 shrink-0", TONE_CLASSES[tone])}>{icon}</span>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </p>
        <p className={cn("break-words text-sm font-medium", TONE_CLASSES[tone])}>
          {value}
        </p>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 gap-2 px-4 py-3 text-sm sm:grid-cols-[120px_minmax(0,1fr)]">
      <span className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="min-w-0 break-all font-mono-ui text-muted-foreground/90">
        {value}
      </span>
    </div>
  );
}

function HealthSummary({
  items,
  title,
}: {
  items: Array<[string, number, Tone]>;
  title: string;
}) {
  return (
    <div className="min-w-0">
      <p className="mb-2 text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {items.map(([label, count, tone]) => (
          <div
            key={label}
            className="flex min-w-0 items-center justify-between gap-2 border border-border bg-secondary/20 px-3 py-2"
          >
            <span className="min-w-0 truncate text-xs text-muted-foreground">
              {label}
            </span>
            <span className={cn("font-mono-ui text-sm", TONE_CLASSES[tone])}>
              {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HealthRows({
  emptyLabel,
  items,
}: {
  emptyLabel: string;
  items: Array<{
    detail: string;
    key: string;
    label: string;
    status: string;
    tone: Tone;
  }>;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }

  return (
    <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
      {items.map((item) => (
        <div
          key={item.key}
          className="grid min-w-0 gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto]"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{item.label}</p>
            <p className="truncate text-xs text-muted-foreground">{item.detail}</p>
          </div>
          <Badge tone={BADGE_TONE[item.tone]} className="w-fit text-[10px]">
            {item.status}
          </Badge>
        </div>
      ))}
    </div>
  );
}

function toolTone(status: RunInspectorToolHealth["status"]): Tone {
  if (status === "available") return "success";
  if (status === "running") return "primary";
  if (status === "unavailable") return "warning";
  if (status === "failed") return "destructive";
  return "muted";
}

function mcpTone(status: RunInspectorMcpHealth["status"]): Tone {
  if (status === "connected") return "success";
  if (status === "degraded") return "warning";
  if (status === "failed") return "destructive";
  return "muted";
}

function mcpDetail(item: RunInspectorMcpHealth): string {
  const affected = item.affected_tools.length
    ? `${item.affected_tools.length} tools`
    : "No affected tools";
  return item.last_error_class ? `${item.last_error_class} - ${affected}` : affected;
}

function describeGatewayForwarder(
  forwarder: RunInspectorGatewayForwarder | null,
): GatewayForwarderDisplay {
  if (!forwarder) {
    return { label: "Idle", tone: "muted", message: "No run followed" };
  }
  if (forwarder.state === "running") {
    return {
      label: "Following",
      tone: "primary",
      message: `${forwarder.events_forwarded ?? 0} events`,
    };
  }
  if (forwarder.state === "completed") {
    return {
      label: "Completed",
      tone: "success",
      message: `${forwarder.events_forwarded ?? 0} events`,
    };
  }
  if (forwarder.state === "failed") {
    return {
      label: "Failed",
      tone: "destructive",
      message: forwarder.last_error ?? "Forwarder failed",
    };
  }
  return {
    label: formatDisplayValue(forwarder.state, "Unknown"),
    tone: "muted",
    message: `${forwarder.events_forwarded ?? 0} events`,
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "Request failed";
}
