import { useCallback, useLayoutEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  FileWarning,
  Link,
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
import { useRunInspectorEvents } from "@/hooks/useRunInspectorEvents";
import { useRunInspectorStatus } from "@/hooks/useRunInspectorStatus";
import type {
  RunInspectorEvent,
  RunInspectorGatewayForwarder,
  RunInspectorGatewayRun,
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
  describeRunInspectorEventStream,
  formatRunInspectorEventTime,
  type RunInspectorEventStreamState,
} from "@/pages/runInspectorEventTimeline";
import {
  describeGatewayRunControlState,
  type GatewayRunControlState,
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

export default function RunInspectorPage() {
  const inspector = useRunInspectorStatus();
  const eventStream = useRunInspectorEvents();
  const [gatewayRunId, setGatewayRunId] = useState("");
  const [gatewayForwarder, setGatewayForwarder] =
    useState<RunInspectorGatewayForwarder | null>(null);
  const [gatewayForwarderError, setGatewayForwarderError] = useState<string | null>(null);
  const [gatewayForwarderBusy, setGatewayForwarderBusy] = useState(false);
  const [gatewayRuns, setGatewayRuns] = useState<RunInspectorGatewayRun[]>([]);
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
  const gatewayControlState = describeGatewayRunControlState({
    events: eventStream.events,
    recentRuns: gatewayRuns,
    runId: gatewayRunId,
  });

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

  useLayoutEffect(() => {
    setTitle("Run Inspector");
    setAfterTitle(
      <Badge tone={BADGE_TONE[stateDisplay.tone]} className="text-[10px]">
        {stateDisplay.label}
      </Badge>,
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
            <HealthCard snapshot={snapshot} />
            <GatewayRunFollowCard
              busy={gatewayForwarderBusy}
              controlBusy={gatewayControlBusy}
              controlError={gatewayControlError}
              controlState={gatewayControlState}
              error={gatewayForwarderError}
              forwarder={gatewayForwarder}
              launchBusy={gatewayLaunchBusy}
              launchError={gatewayLaunchError}
              launchInput={gatewayLaunchInput}
              onRefresh={refreshGatewayFollowStatus}
              onRefreshRuns={refreshGatewayRuns}
              onLaunchInputChange={setGatewayLaunchInput}
              onLaunchSubmit={handleGatewayLaunchSubmit}
              onApprovalDeny={() => void respondGatewayApproval("deny")}
              onApprovalOnce={() => void respondGatewayApproval("once")}
              onRunIdChange={setGatewayRunId}
              onStop={stopGatewayRun}
              recentRuns={gatewayRuns}
              recentRunsBusy={gatewayRunsBusy}
              recentRunsError={gatewayRunsError}
              onSubmit={handleGatewayFollowSubmit}
              runId={gatewayRunId}
            />
            <EventTimelineCard
              error={eventStream.error}
              events={eventStream.events}
              lastUpdatedAt={eventStream.lastUpdatedAt}
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
  launchBusy,
  launchError,
  launchInput,
  onApprovalDeny,
  onApprovalOnce,
  onRefresh,
  onRefreshRuns,
  onLaunchInputChange,
  onLaunchSubmit,
  onRunIdChange,
  onStop,
  recentRuns,
  recentRunsBusy,
  recentRunsError,
  onSubmit,
  runId,
}: {
  busy: boolean;
  controlBusy: "stop" | "allow" | "deny" | null;
  controlError: string | null;
  controlState: GatewayRunControlState;
  error: string | null;
  forwarder: RunInspectorGatewayForwarder | null;
  launchBusy: boolean;
  launchError: string | null;
  launchInput: string;
  onApprovalDeny: () => void;
  onApprovalOnce: () => void;
  onRefresh: () => void;
  onRefreshRuns: () => void;
  onLaunchInputChange: (value: string) => void;
  onLaunchSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRunIdChange: (value: string) => void;
  onStop: () => void;
  recentRuns: RunInspectorGatewayRun[];
  recentRunsBusy: boolean;
  recentRunsError: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  runId: string;
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

        {recentRuns.length > 0 ? (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {recentRuns.map((run) => (
              <button
                key={run.run_id}
                className="grid min-w-0 gap-1 px-3 py-2 text-left transition-colors hover:bg-secondary/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground sm:grid-cols-[minmax(0,1fr)_auto]"
                onClick={() => onRunIdChange(run.run_id)}
                type="button"
              >
                <span className="min-w-0 truncate font-mono-ui text-xs">
                  {formatDisplayValue(run.run_id)}
                </span>
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <Badge tone={gatewayRunTone(run)} className="w-fit text-[10px]">
                    {formatDisplayValue(run.status)}
                  </Badge>
                  {run.last_event ? (
                    <span className="truncate text-[10px] text-muted-foreground">
                      {formatDisplayValue(run.last_event)}
                    </span>
                  ) : null}
                </span>
              </button>
            ))}
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

function EventTimelineCard({
  error,
  events,
  lastUpdatedAt,
  state,
}: {
  error: string | null;
  events: RunInspectorEvent[];
  lastUpdatedAt: string | null;
  state: RunInspectorEventStreamState;
}) {
  const stream = describeRunInspectorEventStream(state);
  const newestFirst = [...events].reverse();

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

        {newestFirst.length === 0 ? (
          <p className="border border-border bg-secondary/20 px-3 py-4 text-sm text-muted-foreground">
            No recent events
          </p>
        ) : (
          <div className="flex min-w-0 flex-col divide-y divide-border/70 border border-border">
            {newestFirst.map((event) => {
              const display = describeRunInspectorEvent(event);
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
                    {event.tool ? (
                      <p className="mt-1 truncate font-mono-ui text-[10px] text-muted-foreground/80">
                        {formatDisplayValue(event.tool)}
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

function gatewayRunTone(run: RunInspectorGatewayRun): BadgeTone {
  if (run.has_error || run.status === "failed") {
    return "destructive";
  }
  if (run.status === "completed") {
    return "success";
  }
  if (run.status === "running" || run.status === "queued") {
    return "secondary";
  }
  return "outline";
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
