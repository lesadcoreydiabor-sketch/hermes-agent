// The dashboard can be served either at the root of its host (e.g.
// https://kanban.tilos.com/) or under a URL prefix when reverse-proxied
// (e.g. https://mission-control.tilos.com/hermes/). The Python backend
// injects ``window.__HERMES_BASE_PATH__`` into index.html based on the
// incoming ``X-Forwarded-Prefix`` header so the SPA can address its own
// ``/api/...`` and ``/dashboard-plugins/...`` URLs correctly without a
// rebuild. Empty string means "served at root".
function readBasePath(): string {
  if (typeof window === "undefined") return "";
  const raw = window.__HERMES_BASE_PATH__ ?? "";
  if (!raw) return "";
  // Normalise: ensure leading slash, strip trailing slash.
  const withLead = raw.startsWith("/") ? raw : `/${raw}`;
  return withLead.replace(/\/+$/, "");
}

export const HERMES_BASE_PATH = readBasePath();
const BASE = HERMES_BASE_PATH;

import type { DashboardTheme } from "@/themes/types";

// Ephemeral session token for protected endpoints.
// Injected into index.html by the server — never fetched via API.
declare global {
  interface Window {
    __HERMES_SESSION_TOKEN__?: string;
    __HERMES_BASE_PATH__?: string;
  }
}
let _sessionToken: string | null = null;
const SESSION_HEADER = "X-Hermes-Session-Token";

function setSessionHeader(headers: Headers, token: string): void {
  if (!headers.has(SESSION_HEADER)) {
    headers.set(SESSION_HEADER, token);
  }
}

export async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  // Inject the session token into all /api/ requests.
  const headers = new Headers(init?.headers);
  const token = window.__HERMES_SESSION_TOKEN__;
  if (token) {
    setSessionHeader(headers, token);
  }
  const res = await fetch(`${BASE}${url}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

async function getSessionToken(): Promise<string> {
  if (_sessionToken) return _sessionToken;
  const injected = window.__HERMES_SESSION_TOKEN__;
  if (injected) {
    _sessionToken = injected;
    return _sessionToken;
  }
  throw new Error("Session token not available — page must be served by the Hermes dashboard server");
}

export const api = {
  getStatus: () => fetchJSON<StatusResponse>("/api/status"),
  getRunInspector: (init?: RequestInit) =>
    fetchJSON<RunInspectorResponse>("/api/run-inspector", init),
  getRunInspectorEvents: (limit = 50, init?: RequestInit) =>
    fetchJSON<RunInspectorEventsResponse>(
      `/api/run-inspector/events?limit=${limit}`,
      init,
    ),
  getRunInspectorAttention: (limit = 20, init?: RequestInit) =>
    fetchJSON<RunInspectorAttentionResponse>(
      `/api/run-inspector/attention?limit=${limit}`,
      init,
    ),
  getRunInspectorDesktopStatus: (port = 9119, init?: RequestInit) =>
    fetchJSON<RunInspectorDesktopStatusResponse>(
      `/api/run-inspector/desktop-status?port=${port}`,
      init,
    ),
  getRunInspectorMemoryWorkbench: (limit = 12, init?: RequestInit) =>
    fetchJSON<RunInspectorMemoryWorkbenchResponse>(
      `/api/run-inspector/memory-workbench?limit=${limit}`,
      init,
    ),
  getGatewayRuns: (limit = 20, init?: RequestInit) =>
    fetchJSON<RunInspectorGatewayRunsResponse>(
      `/api/run-inspector/gateway-runs?limit=${limit}`,
      init,
    ),
  launchGatewayRun: (body: RunInspectorGatewayLaunchRequest) =>
    fetchJSON<RunInspectorGatewayLaunchResponse>(
      "/api/run-inspector/gateway-runs/launch",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  stopGatewayRun: (runId: string) =>
    fetchJSON<RunInspectorGatewayStopResponse>(
      `/api/run-inspector/gateway-runs/${encodeURIComponent(runId)}/stop`,
      { method: "POST" },
    ),
  respondGatewayRunApproval: (
    runId: string,
    body: RunInspectorGatewayApprovalRequest,
  ) =>
    fetchJSON<RunInspectorGatewayApprovalResponse>(
      `/api/run-inspector/gateway-runs/${encodeURIComponent(runId)}/approval`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  followGatewayRunEvents: (runId: string) =>
    fetchJSON<RunInspectorGatewayForwarderResponse>(
      `/api/run-inspector/gateway-runs/${encodeURIComponent(runId)}/follow`,
      { method: "POST" },
    ),
  getGatewayRunEventForwarder: (runId: string) =>
    fetchJSON<RunInspectorGatewayForwarderResponse>(
      `/api/run-inspector/gateway-runs/${encodeURIComponent(runId)}/follow`,
    ),
  getSessions: (limit = 20, offset = 0) =>
    fetchJSON<PaginatedSessions>(`/api/sessions?limit=${limit}&offset=${offset}`),
  getSessionMessages: (id: string) =>
    fetchJSON<SessionMessagesResponse>(`/api/sessions/${encodeURIComponent(id)}/messages`),
  getSessionLatestDescendant: (id: string) =>
    fetchJSON<SessionLatestDescendantResponse>(
      `/api/sessions/${encodeURIComponent(id)}/latest-descendant`,
    ),
  deleteSession: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/api/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  getLogs: (params: { file?: string; lines?: number; level?: string; component?: string }) => {
    const qs = new URLSearchParams();
    if (params.file) qs.set("file", params.file);
    if (params.lines) qs.set("lines", String(params.lines));
    if (params.level && params.level !== "ALL") qs.set("level", params.level);
    if (params.component && params.component !== "all") qs.set("component", params.component);
    return fetchJSON<LogsResponse>(`/api/logs?${qs.toString()}`);
  },
  getAnalytics: (days: number) =>
    fetchJSON<AnalyticsResponse>(`/api/analytics/usage?days=${days}`),
  getModelsAnalytics: (days: number) =>
    fetchJSON<ModelsAnalyticsResponse>(`/api/analytics/models?days=${days}`),
  getConfig: () => fetchJSON<Record<string, unknown>>("/api/config"),
  getDefaults: () => fetchJSON<Record<string, unknown>>("/api/config/defaults"),
  getSchema: () => fetchJSON<{ fields: Record<string, unknown>; category_order: string[] }>("/api/config/schema"),
  getModelInfo: () => fetchJSON<ModelInfoResponse>("/api/model/info"),
  getModelOptions: () => fetchJSON<ModelOptionsResponse>("/api/model/options"),
  getAuxiliaryModels: () => fetchJSON<AuxiliaryModelsResponse>("/api/model/auxiliary"),
  setModelAssignment: (body: ModelAssignmentRequest) =>
    fetchJSON<ModelAssignmentResponse>("/api/model/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  saveConfig: (config: Record<string, unknown>) =>
    fetchJSON<{ ok: boolean }>("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    }),
  getConfigRaw: () => fetchJSON<{ yaml: string }>("/api/config/raw"),
  saveConfigRaw: (yaml_text: string) =>
    fetchJSON<{ ok: boolean }>("/api/config/raw", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml_text }),
    }),
  getEnvVars: () => fetchJSON<Record<string, EnvVarInfo>>("/api/env"),
  setEnvVar: (key: string, value: string) =>
    fetchJSON<{ ok: boolean }>("/api/env", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value }),
    }),
  deleteEnvVar: (key: string) =>
    fetchJSON<{ ok: boolean }>("/api/env", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    }),
  revealEnvVar: async (key: string) => {
    const token = await getSessionToken();
    return fetchJSON<{ key: string; value: string }>("/api/env/reveal", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [SESSION_HEADER]: token,
      },
      body: JSON.stringify({ key }),
    });
  },

  // Cron jobs
  getCronJobs: () => fetchJSON<CronJob[]>("/api/cron/jobs"),
  createCronJob: (job: { prompt: string; schedule: string; name?: string; deliver?: string }) =>
    fetchJSON<CronJob>("/api/cron/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(job),
    }),
  pauseCronJob: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/api/cron/jobs/${id}/pause`, { method: "POST" }),
  resumeCronJob: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/api/cron/jobs/${id}/resume`, { method: "POST" }),
  triggerCronJob: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/api/cron/jobs/${id}/trigger`, { method: "POST" }),
  deleteCronJob: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/api/cron/jobs/${id}`, { method: "DELETE" }),

  // Profiles (minimal)
  getProfiles: () =>
    fetchJSON<{ profiles: ProfileInfo[] }>("/api/profiles"),
  createProfile: (body: { name: string; clone_from_default: boolean }) =>
    fetchJSON<{ ok: boolean; name: string; path: string }>("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  renameProfile: (name: string, newName: string) =>
    fetchJSON<{ ok: boolean; name: string; path: string }>(
      `/api/profiles/${encodeURIComponent(name)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName }),
      },
    ),
  deleteProfile: (name: string) =>
    fetchJSON<{ ok: boolean }>(
      `/api/profiles/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),
  getProfileSetupCommand: (name: string) =>
    fetchJSON<{ command: string }>(
      `/api/profiles/${encodeURIComponent(name)}/setup-command`,
    ),
  getProfileSoul: (name: string) =>
    fetchJSON<{ content: string; exists: boolean }>(
      `/api/profiles/${encodeURIComponent(name)}/soul`,
    ),
  updateProfileSoul: (name: string, content: string) =>
    fetchJSON<{ ok: boolean }>(
      `/api/profiles/${encodeURIComponent(name)}/soul`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    ),

  // Skills & Toolsets
  getSkills: () => fetchJSON<SkillInfo[]>("/api/skills"),
  toggleSkill: (name: string, enabled: boolean) =>
    fetchJSON<{ ok: boolean }>("/api/skills/toggle", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, enabled }),
    }),
  getToolsets: () => fetchJSON<ToolsetInfo[]>("/api/tools/toolsets"),

  // Session search (FTS5)
  searchSessions: (q: string) =>
    fetchJSON<SessionSearchResponse>(`/api/sessions/search?q=${encodeURIComponent(q)}`),

  // OAuth provider management
  getOAuthProviders: () =>
    fetchJSON<OAuthProvidersResponse>("/api/providers/oauth"),
  disconnectOAuthProvider: async (providerId: string) => {
    const token = await getSessionToken();
    return fetchJSON<{ ok: boolean; provider: string }>(
      `/api/providers/oauth/${encodeURIComponent(providerId)}`,
      {
        method: "DELETE",
        headers: { [SESSION_HEADER]: token },
      },
    );
  },
  startOAuthLogin: async (providerId: string) => {
    const token = await getSessionToken();
    return fetchJSON<OAuthStartResponse>(
      `/api/providers/oauth/${encodeURIComponent(providerId)}/start`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          [SESSION_HEADER]: token,
        },
        body: "{}",
      },
    );
  },
  submitOAuthCode: async (providerId: string, sessionId: string, code: string) => {
    const token = await getSessionToken();
    return fetchJSON<OAuthSubmitResponse>(
      `/api/providers/oauth/${encodeURIComponent(providerId)}/submit`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          [SESSION_HEADER]: token,
        },
        body: JSON.stringify({ session_id: sessionId, code }),
      },
    );
  },
  pollOAuthSession: (providerId: string, sessionId: string) =>
    fetchJSON<OAuthPollResponse>(
      `/api/providers/oauth/${encodeURIComponent(providerId)}/poll/${encodeURIComponent(sessionId)}`,
    ),
  cancelOAuthSession: async (sessionId: string) => {
    const token = await getSessionToken();
    return fetchJSON<{ ok: boolean }>(
      `/api/providers/oauth/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: "DELETE",
        headers: { [SESSION_HEADER]: token },
      },
    );
  },

  // Gateway / update actions
  restartGateway: () =>
    fetchJSON<ActionResponse>("/api/gateway/restart", { method: "POST" }),
  updateHermes: () =>
    fetchJSON<ActionResponse>("/api/hermes/update", { method: "POST" }),
  getActionStatus: (name: string, lines = 200) =>
    fetchJSON<ActionStatusResponse>(
      `/api/actions/${encodeURIComponent(name)}/status?lines=${lines}`,
    ),

  // Dashboard plugins
  getPlugins: () =>
    fetchJSON<PluginManifestResponse[]>("/api/dashboard/plugins"),
  rescanPlugins: () =>
    fetchJSON<{ ok: boolean; count: number }>("/api/dashboard/plugins/rescan"),

  getPluginsHub: () => fetchJSON<PluginsHubResponse>("/api/dashboard/plugins/hub"),

  installAgentPlugin: (body: AgentPluginInstallRequest) =>
    fetchJSON<AgentPluginInstallResponse>("/api/dashboard/agent-plugins/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body }),
    }),

  enableAgentPlugin: (name: string) =>
    fetchJSON<{ ok: boolean; name: string; unchanged?: boolean }>(
      `/api/dashboard/agent-plugins/${encodeURIComponent(name)}/enable`,
      { method: "POST" },
    ),

  disableAgentPlugin: (name: string) =>
    fetchJSON<{ ok: boolean; name: string; unchanged?: boolean }>(
      `/api/dashboard/agent-plugins/${encodeURIComponent(name)}/disable`,
      { method: "POST" },
    ),

  updateAgentPlugin: (name: string) =>
    fetchJSON<AgentPluginUpdateResponse>(
      `/api/dashboard/agent-plugins/${encodeURIComponent(name)}/update`,
      { method: "POST" },
    ),

  removeAgentPlugin: (name: string) =>
    fetchJSON<{ ok: boolean; name: string }>(
      `/api/dashboard/agent-plugins/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),

  savePluginProviders: (body: PluginProvidersPutRequest) =>
    fetchJSON<{ ok: boolean }>("/api/dashboard/plugin-providers", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  setPluginVisibility: (name: string, hidden: boolean) =>
    fetchJSON<{ ok: boolean; name: string; hidden: boolean }>(
      `/api/dashboard/plugins/${encodeURIComponent(name)}/visibility`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hidden }),
      },
    ),

  // Dashboard themes
  getThemes: () =>
    fetchJSON<DashboardThemesResponse>("/api/dashboard/themes"),
  setTheme: (name: string) =>
    fetchJSON<{ ok: boolean; theme: string }>("/api/dashboard/theme", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
};

export interface ActionResponse {
  name: string;
  ok: boolean;
  pid: number;
}

export interface ActionStatusResponse {
  exit_code: number | null;
  lines: string[];
  name: string;
  pid: number | null;
  running: boolean;
}

export interface PlatformStatus {
  error_code?: string;
  error_message?: string;
  state: string;
  updated_at: string;
}

export interface StatusResponse {
  active_sessions: number;
  config_path: string;
  config_version: number;
  env_path: string;
  gateway_exit_reason: string | null;
  gateway_health_url: string | null;
  gateway_pid: number | null;
  gateway_platforms: Record<string, PlatformStatus>;
  gateway_running: boolean;
  gateway_state: string | null;
  gateway_updated_at: string | null;
  hermes_home: string;
  latest_config_version: number;
  release_date: string;
  version: string;
}

export type RunInspectorSource =
  | "cli"
  | "gateway"
  | "acp"
  | "mcp"
  | "eval"
  | "unknown";

export type RunInspectorStatus =
  | "starting"
  | "thinking"
  | "executing_tool"
  | "waiting_input"
  | "waiting_approval"
  | "rate_limited"
  | "recovering"
  | "completed"
  | "failed"
  | "stopped"
  | "unknown";

export type RunInspectorHealthStatus =
  | "available"
  | "unavailable"
  | "running"
  | "failed"
  | "unknown";

export type RunInspectorMcpStatus =
  | "connected"
  | "degraded"
  | "failed"
  | "unknown";

export interface RunInspectorActiveTool {
  name: string | null;
  call_id: string | null;
  duration_ms: number | null;
  args_summary: Record<string, unknown> | null;
}

export interface RunInspectorToolHealth {
  name: string | null;
  toolset: string | null;
  status: RunInspectorHealthStatus;
  reason: string | null;
}

export interface RunInspectorMcpHealth {
  name: string | null;
  status: RunInspectorMcpStatus;
  last_error_class: string | null;
  affected_tools: string[];
}

export interface RunInspectorSnapshot {
  version: number;
  run_id: string;
  source: RunInspectorSource;
  status: RunInspectorStatus;
  reason: string | null;
  workspace: string | null;
  session_id: string | null;
  last_activity_at: string | null;
  active_tool: RunInspectorActiveTool;
  tool_health: RunInspectorToolHealth[];
  mcp_health: RunInspectorMcpHealth[];
  recovery_hint: string | null;
  privacy_flags: string[];
  degraded_reason: string | null;
}

export interface RunInspectorResponse {
  ok: boolean;
  snapshot: RunInspectorSnapshot;
  refreshed_at: string;
}

export type RunInspectorEventSource =
  | "dashboard_chat"
  | "gateway_run"
  | "run_inspector"
  | "unknown"
  | string;

export interface RunInspectorEvent {
  id: number;
  type: string;
  source: RunInspectorEventSource;
  timestamp: string;
  run_id: string | null;
  session_id: string | null;
  tool: string | null;
  status: string | null;
  message: string | null;
}

export interface RunInspectorEventsResponse {
  ok: boolean;
  events: RunInspectorEvent[];
  refreshed_at: string;
}

export type RunInspectorAttentionKind =
  | "approval_waiting"
  | "run_failed"
  | "run_degraded"
  | "mcp_degraded"
  | "desktop_shell_degraded"
  | "recovery_available"
  | string;

export type RunInspectorAttentionSeverity = "critical" | "warning" | "info";

export type RunInspectorAttentionPrivacyClass =
  | "safe_summary"
  | "redacted_summary"
  | "local_only";

export interface RunInspectorAttentionSignal {
  kind: RunInspectorAttentionKind;
  severity: RunInspectorAttentionSeverity;
  title: string;
  body: string;
  route: string;
  run_id: string | null;
  session_id: string | null;
  timestamp: string;
  dedupe_key: string;
  ttl_ms: number;
  privacy_class: RunInspectorAttentionPrivacyClass;
}

export interface RunInspectorAttentionResponse {
  ok: boolean;
  signals: RunInspectorAttentionSignal[];
  refreshed_at: string;
}

export interface RunInspectorDesktopStatus {
  ok: boolean;
  record_present: boolean;
  runtime_record_cleared: boolean;
  pid: number | null;
  pid_status: "none" | "running" | "stale" | string;
  pid_reason: string;
  host: string;
  port: number;
  route: string;
  url: string;
  started_at: string | null;
  health: "ok" | "unavailable" | string;
  health_reason: string;
  compatible_dashboard: boolean;
  reuse_command: string | null;
  manual_url: string | null;
  stop_command: string | null;
}

export interface RunInspectorDesktopStatusResponse {
  ok: boolean;
  status: RunInspectorDesktopStatus;
  refreshed_at: string;
}

export type RunInspectorMemoryWorkbenchStatus =
  | "empty"
  | "active"
  | "failed"
  | "degraded"
  | "unavailable"
  | string;

export interface RunInspectorMemoryWorkbenchTask {
  task_id: string | null;
  title: string | null;
  status: string | null;
}

export interface RunInspectorMemoryWorkbenchCheckpoint {
  schema_version?: number;
  generated_at?: string;
  source?: string;
  active_capability?: string;
  current_task_id: string | null;
  completed_tasks: RunInspectorMemoryWorkbenchTask[];
  pending_tasks: RunInspectorMemoryWorkbenchTask[];
  blocked_tasks: RunInspectorMemoryWorkbenchTask[];
  last_verification?: string | null;
  open_decisions?: string[];
  next_step: string;
  degraded_reason?: string | null;
  privacy_class?: string;
}

export interface RunInspectorMemoryWorkbenchActiveWork {
  work_id: string | null;
  parent_work_id?: string | null;
  event_type?: string | null;
  role?: string | null;
  status: string | null;
  summary: string | null;
  timestamp?: string | null;
}

export interface RunInspectorMemoryWorkbenchMemoryProvider {
  name: string | null;
  kind: string | null;
  availability: string;
  initialized: boolean | null;
  tool_names: string[];
  last_lifecycle: {
    event: string | null;
    status: string | null;
    timestamp: string | null;
    error_type: string | null;
  } | null;
  privacy_class?: string;
}

export interface RunInspectorMemoryWorkbenchMemory {
  status: string;
  provider_count: number;
  providers: RunInspectorMemoryWorkbenchMemoryProvider[];
  registered_tools: string[];
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchRuntimePersistenceFlag {
  name: string;
  env_var: string;
  enabled: boolean;
  path: string;
  exists: boolean;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchRuntimePersistence {
  status: string;
  enabled_count: number;
  flags: RunInspectorMemoryWorkbenchRuntimePersistenceFlag[];
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchAgentAssignmentSummary {
  schema_version: number;
  status: string;
  total_count: number;
  active_count: number;
  completed_count: number;
  failed_count: number;
  blocked_count: number;
  ready_task_ids: string[];
  dependency_waiting_task_ids: string[];
  blocked_task_ids: string[];
  role_counts: Record<string, number>;
  status_counts: Record<string, number>;
  conflicts: Array<{
    task_ids: string[];
    overlap: string[];
    resolution: string;
    privacy_class: string;
  }>;
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchAgentAssignment {
  schema_version: number;
  task_id: string;
  title: string;
  role: string;
  status: string;
  owner: {
    agent_id: string | null;
    parent_agent_id: string | null;
    human_owner: string | null;
  };
  dependencies: {
    task_ids: string[];
    required_artifacts: string[];
  };
  write_scope: {
    files: string[];
    directories: string[];
    forbidden_paths: string[];
    shared_contracts: string[];
  };
  allowed_tools: {
    toolsets: string[];
    commands: string[];
    disallowed: string[];
  };
  delegate_limits: {
    max_depth: number | null;
    max_parallel_workers: number | null;
    interrupt_policy: string;
  };
  verification: {
    command: string;
    expected_signal: string;
    required_before_handoff: boolean;
  };
  handoff_payload: {
    summary: string;
    changed_files: string[];
    verification_result: string | null;
    blockers: string[];
    next_step: string;
    privacy_class: string;
  };
  conflict_policy: {
    write_scope_must_be_disjoint: boolean;
    shared_contract_requires_reviewer: boolean;
    conflict_resolution: string;
  };
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchAgentAssignmentBatch {
  index: number;
  task_ids: string[];
  roles: Record<string, number>;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchAgentAssignmentPlan {
  schema_version: number;
  status: string;
  max_parallel_workers: number;
  batches: RunInspectorMemoryWorkbenchAgentAssignmentBatch[];
  blocked_task_ids: string[];
  active_task_ids: string[];
  waiting_task_ids: string[];
  conflict_task_ids: string[];
  conflicts: Array<{
    task_ids: string[];
    overlap: string[];
    resolution: string;
    privacy_class: string;
  }>;
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchHandoffProtocol {
  schema_version: number;
  status: string;
  handoff_task_ids: string[];
  ready_task_ids: string[];
  blocked_task_ids: string[];
  verification_missing_task_ids: string[];
  reviewer_required_task_ids: string[];
  human_decision_task_ids: string[];
  conflict_task_ids: string[];
  policy_counts: Record<string, number>;
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchAgentAssignments {
  summary: RunInspectorMemoryWorkbenchAgentAssignmentSummary;
  parallel_plan?: RunInspectorMemoryWorkbenchAgentAssignmentPlan;
  handoff_protocol?: RunInspectorMemoryWorkbenchHandoffProtocol;
  assignments: RunInspectorMemoryWorkbenchAgentAssignment[];
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchEntry {
  [key: string]: unknown;
  entry_id?: string | null;
  event_id?: string | null;
  task_id?: string | null;
  status?: string | null;
  state?: string | null;
  summary?: string | null;
  title?: string | null;
  timestamp?: string | null;
}

export interface RunInspectorMemoryWorkbenchRecoveryGates {
  status: string;
  completed_count: number;
  blocked_count: number;
  monitoring_count: number;
  verification_task_ids: string[];
  blocked_task_ids: string[];
  monitoring_task_ids: string[];
  next_steps: string[];
  blockers: string[];
  source_counts: Record<string, number>;
  latest_event_type: string | null;
  latest_status: string | null;
  latest_timestamp: string | null;
  latest_source: string | null;
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbench {
  schema_version: number;
  generated_at: string;
  status: RunInspectorMemoryWorkbenchStatus;
  status_reason: string;
  active_work: RunInspectorMemoryWorkbenchActiveWork[];
  memory: RunInspectorMemoryWorkbenchMemory;
  runtime_persistence?: RunInspectorMemoryWorkbenchRuntimePersistence;
  agent_assignments?: RunInspectorMemoryWorkbenchAgentAssignments;
  checkpoint: RunInspectorMemoryWorkbenchCheckpoint;
  action_ledger: {
    entries: RunInspectorMemoryWorkbenchEntry[];
    recovery_gates?: RunInspectorMemoryWorkbenchRecoveryGates;
    degraded_reason: string | null;
  };
  long_term_queue: {
    entries: RunInspectorMemoryWorkbenchEntry[];
    unresolved_count: number;
    degraded_reason: string | null;
  };
  skills_journal: {
    entries: RunInspectorMemoryWorkbenchEntry[];
    degraded_reason: string | null;
  };
  degraded_reason: string | null;
  privacy_class: string;
}

export interface RunInspectorMemoryWorkbenchResponse {
  ok: boolean;
  workbench: RunInspectorMemoryWorkbench;
  refreshed_at: string;
}

export interface RunInspectorGatewayForwarder {
  run_id: string;
  state: "running" | "completed" | "failed" | string;
  started_at?: string;
  updated_at?: string;
  events_forwarded?: number;
  last_error?: string | null;
  gateway_url?: string;
  already_running?: boolean;
}

export interface RunInspectorGatewayForwarderResponse {
  ok: boolean;
  forwarder: RunInspectorGatewayForwarder | null;
  refreshed_at: string;
}

export interface RunInspectorGatewayRun {
  run_id: string;
  status: string;
  created_at: number | null;
  updated_at: number | null;
  session_id: string | null;
  model: string | null;
  last_event: string | null;
  has_error: boolean;
}

export interface RunInspectorGatewayRunsResponse {
  ok: boolean;
  runs: RunInspectorGatewayRun[];
  refreshed_at: string;
}

export interface RunInspectorGatewayLaunchRequest {
  input: string;
  model?: string | null;
  session_id?: string | null;
  instructions?: string | null;
  auto_follow?: boolean;
}

export interface RunInspectorGatewayLaunchResponse {
  ok: boolean;
  run: Pick<RunInspectorGatewayRun, "run_id" | "status">;
  forwarder: RunInspectorGatewayForwarder | null;
  refreshed_at: string;
}

export interface RunInspectorGatewayStopResponse {
  ok: boolean;
  run: Pick<RunInspectorGatewayRun, "run_id" | "status">;
  refreshed_at: string;
}

export interface RunInspectorGatewayApprovalRequest {
  choice: "once" | "session" | "always" | "deny";
  resolve_all?: boolean;
}

export interface RunInspectorGatewayApprovalResponse {
  ok: boolean;
  approval: {
    run_id: string;
    choice: string;
    resolved: number;
  };
  refreshed_at: string;
}

export interface SessionInfo {
  id: string;
  source: string | null;
  model: string | null;
  title: string | null;
  started_at: number;
  ended_at: number | null;
  last_active: number;
  is_active: boolean;
  message_count: number;
  tool_call_count: number;
  input_tokens: number;
  output_tokens: number;
  preview: string | null;
  parent_session_id?: string | null;
}

export interface SessionLatestDescendantResponse {
  requested_session_id: string;
  session_id: string;
  path: string[];
  changed: boolean;
}

export interface PaginatedSessions {
  sessions: SessionInfo[];
  total: number;
  limit: number;
  offset: number;
}

export interface EnvVarInfo {
  is_set: boolean;
  redacted_value: string | null;
  description: string;
  url: string | null;
  category: string;
  is_password: boolean;
  tools: string[];
  advanced: boolean;
}

export interface SessionMessage {
  role: "user" | "assistant" | "system" | "tool";
  content: string | null;
  tool_calls?: Array<{
    id: string;
    function: { name: string; arguments: string };
  }>;
  tool_name?: string;
  tool_call_id?: string;
  timestamp?: number;
}

export interface SessionMessagesResponse {
  session_id: string;
  messages: SessionMessage[];
}

export interface LogsResponse {
  file: string;
  lines: string[];
}

export interface AnalyticsDailyEntry {
  day: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  reasoning_tokens: number;
  estimated_cost: number;
  actual_cost: number;
  sessions: number;
  api_calls: number;
}

export interface AnalyticsModelEntry {
  model: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  sessions: number;
  api_calls: number;
}

export interface AnalyticsSkillEntry {
  skill: string;
  view_count: number;
  manage_count: number;
  total_count: number;
  percentage: number;
  last_used_at: number | null;
}

export interface AnalyticsSkillsSummary {
  total_skill_loads: number;
  total_skill_edits: number;
  total_skill_actions: number;
  distinct_skills_used: number;
}

export interface AnalyticsResponse {
  daily: AnalyticsDailyEntry[];
  by_model: AnalyticsModelEntry[];
  totals: {
    total_input: number;
    total_output: number;
    total_cache_read: number;
    total_reasoning: number;
    total_estimated_cost: number;
    total_actual_cost: number;
    total_sessions: number;
    total_api_calls: number;
  };
  skills: {
    summary: AnalyticsSkillsSummary;
    top_skills: AnalyticsSkillEntry[];
  };
}

export interface ProfileInfo {
  name: string;
  path: string;
  is_default: boolean;
  model: string | null;
  provider: string | null;
  has_env: boolean;
  skill_count: number;
}

export interface ModelsAnalyticsModelEntry {
  model: string;
  provider: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  reasoning_tokens: number;
  estimated_cost: number;
  actual_cost: number;
  sessions: number;
  api_calls: number;
  tool_calls: number;
  last_used_at: number;
  avg_tokens_per_session: number;
  capabilities: {
    supports_tools?: boolean;
    supports_vision?: boolean;
    supports_reasoning?: boolean;
    context_window?: number;
    max_output_tokens?: number;
    model_family?: string;
  };
}

export interface ModelsAnalyticsResponse {
  models: ModelsAnalyticsModelEntry[];
  totals: {
    distinct_models: number;
    total_input: number;
    total_output: number;
    total_cache_read: number;
    total_reasoning: number;
    total_estimated_cost: number;
    total_actual_cost: number;
    total_sessions: number;
    total_api_calls: number;
  };
  period_days: number;
}

export interface CronJob {
  id: string;
  name?: string | null;
  prompt?: string | null;
  script?: string | null;
  schedule?: { kind?: string; expr?: string; display?: string };
  schedule_display?: string | null;
  enabled: boolean;
  state?: string | null;
  deliver?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
}

export interface SkillInfo {
  name: string;
  description: string;
  category: string;
  enabled: boolean;
}

export interface ToolsetInfo {
  name: string;
  label: string;
  description: string;
  enabled: boolean;
  configured: boolean;
  tools: string[];
}

export interface SessionSearchResult {
  session_id: string;
  snippet: string;
  role: string | null;
  source: string | null;
  model: string | null;
  session_started: number | null;
}

export interface SessionSearchResponse {
  results: SessionSearchResult[];
}

// ── Model info types ──────────────────────────────────────────────────

export interface ModelInfoResponse {
  model: string;
  provider: string;
  auto_context_length: number;
  config_context_length: number;
  effective_context_length: number;
  capabilities: {
    supports_tools?: boolean;
    supports_vision?: boolean;
    supports_reasoning?: boolean;
    context_window?: number;
    max_output_tokens?: number;
    model_family?: string;
  };
}

// ── Model options / assignment types ──────────────────────────────────

export interface ModelOptionProvider {
  name: string;
  slug: string;
  models?: string[];
  total_models?: number;
  is_current?: boolean;
  is_user_defined?: boolean;
  source?: string;
  warning?: string;
}

export interface ModelOptionsResponse {
  model?: string;
  provider?: string;
  providers?: ModelOptionProvider[];
}

export interface AuxiliaryTaskAssignment {
  task: string;
  provider: string;
  model: string;
  base_url: string;
}

export interface AuxiliaryModelsResponse {
  tasks: AuxiliaryTaskAssignment[];
  main: { provider: string; model: string };
}

export interface ModelAssignmentRequest {
  scope: "main" | "auxiliary";
  provider: string;
  model: string;
  /** For auxiliary: task slot name, "" for all, "__reset__" to reset all. */
  task?: string;
}

export interface ModelAssignmentResponse {
  ok: boolean;
  scope?: string;
  provider?: string;
  model?: string;
  tasks?: string[];
  reset?: boolean;
}

// ── OAuth provider types ────────────────────────────────────────────────

export interface OAuthProviderStatus {
  logged_in: boolean;
  source?: string | null;
  source_label?: string | null;
  token_preview?: string | null;
  expires_at?: string | null;
  has_refresh_token?: boolean;
  last_refresh?: string | null;
  error?: string;
}

export interface OAuthProvider {
  id: string;
  name: string;
  /** "pkce" (browser redirect + paste code), "device_code" (show code + URL),
   *  or "external" (delegated to a separate CLI like Claude Code or Qwen). */
  flow: "pkce" | "device_code" | "external";
  cli_command: string;
  docs_url: string;
  status: OAuthProviderStatus;
}

export interface OAuthProvidersResponse {
  providers: OAuthProvider[];
}

/** Discriminated union — the shape of /start depends on the flow. */
export type OAuthStartResponse =
  | {
      session_id: string;
      flow: "pkce";
      auth_url: string;
      expires_in: number;
    }
  | {
      session_id: string;
      flow: "device_code";
      user_code: string;
      verification_url: string;
      expires_in: number;
      poll_interval: number;
    };

export interface OAuthSubmitResponse {
  ok: boolean;
  status: "approved" | "error";
  message?: string;
}

export interface OAuthPollResponse {
  session_id: string;
  status: "pending" | "approved" | "denied" | "expired" | "error";
  error_message?: string | null;
  expires_at?: number | null;
}

// ── Dashboard theme types ──────────────────────────────────────────────

export interface DashboardThemeSummary {
  description: string;
  label: string;
  name: string;
  /** Full theme definition for user themes; undefined for built-ins
   *  (which the frontend already has locally). */
  definition?: DashboardTheme;
}

export interface DashboardThemesResponse {
  active: string;
  themes: DashboardThemeSummary[];
}

// ── Dashboard plugin types ─────────────────────────────────────────────

export interface PluginManifestResponse {
  name: string;
  label: string;
  description: string;
  icon: string;
  version: string;
  tab: {
    path: string;
    position?: string;
    override?: string;
    hidden?: boolean;
  };
  slots?: string[];
  entry: string;
  css?: string | null;
  has_api: boolean;
  source: string;
}

export interface HubAgentPluginRow {
  name: string;
  version: string;
  description: string;
  source: string;
  runtime_status: "disabled" | "enabled" | "inactive";
  has_dashboard_manifest: boolean;
  dashboard_manifest: PluginManifestResponse | null;
  path: string;
  can_remove: boolean;
  can_update_git: boolean;
  auth_required: boolean;
  auth_command: string;
  user_hidden: boolean;
}

export interface PluginsHubProviders {
  memory_provider: string;
  memory_options: Array<{ name: string; description: string }>;
  context_engine: string;
  context_options: Array<{ name: string; description: string }>;
}

export interface PluginsHubResponse {
  plugins: HubAgentPluginRow[];
  orphan_dashboard_plugins: PluginManifestResponse[];
  providers: PluginsHubProviders;
}

export interface AgentPluginInstallRequest {
  identifier: string;
  force?: boolean;
  enable?: boolean;
}

export interface AgentPluginInstallResponse {
  ok: boolean;
  plugin_name?: string;
  warnings?: string[];
  missing_env?: string[];
  after_install_path?: string | null;
  enabled?: boolean;
  error?: string;
}

export interface AgentPluginUpdateResponse {
  ok: boolean;
  name?: string;
  output?: string;
  unchanged?: boolean;
  error?: string;
}

export interface PluginProvidersPutRequest {
  memory_provider?: string;
  context_engine?: string;
}
