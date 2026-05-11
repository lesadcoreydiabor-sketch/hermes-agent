import type { RunInspectorMemoryWorkbench } from "@/lib/api";
import type { Tone } from "@/pages/runInspectorViewModel";

export type RunInspectorMemoryWorkbenchState =
  | "idle"
  | "loading"
  | "ready"
  | "degraded"
  | "auth_failed"
  | "offline";

export interface MemoryWorkbenchDisplay {
  label: string;
  message: string;
  tone: Tone;
}

export function describeMemoryWorkbenchState(
  state: RunInspectorMemoryWorkbenchState,
  workbench: RunInspectorMemoryWorkbench | null,
  error?: string | null,
): MemoryWorkbenchDisplay {
  if (state === "auth_failed") {
    return { label: "Memory unavailable", message: "Auth failed", tone: "destructive" };
  }
  if (state === "offline") {
    return { label: "Memory offline", message: "Connection failed", tone: "destructive" };
  }
  if (state === "loading") {
    return { label: "Loading memory", message: "Reading safe work summaries", tone: "muted" };
  }
  if (state === "degraded" && !workbench) {
    return {
      label: "Memory degraded",
      message: error || "Workbench unavailable",
      tone: "warning",
    };
  }
  if (!workbench) {
    return { label: "Memory unknown", message: "No workbench loaded", tone: "muted" };
  }
  if (workbench.status === "failed") {
    return {
      label: "Memory attention",
      message: workbench.status_reason,
      tone: "destructive",
    };
  }
  if (workbench.status === "active") {
    return { label: "Memory active", message: workbench.status_reason, tone: "primary" };
  }
  if (workbench.status === "degraded") {
    return {
      label: "Memory degraded",
      message: workbench.degraded_reason || workbench.status_reason,
      tone: "warning",
    };
  }
  if (workbench.status === "unavailable") {
    return {
      label: "Memory unavailable",
      message: workbench.degraded_reason || workbench.status_reason,
      tone: "warning",
    };
  }
  return { label: "Memory quiet", message: workbench.status_reason, tone: "muted" };
}

export function memoryProviderTone(status: string): Tone {
  if (status === "available") return "success";
  if (status === "degraded") return "warning";
  if (status === "unavailable") return "muted";
  return "muted";
}

export function describeRuntimePersistenceState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const runtime = workbench?.runtime_persistence ?? null;
  if (!runtime) {
    return {
      label: "Persistence unknown",
      message: "No runtime persistence status",
      tone: "muted",
    };
  }
  if (runtime.degraded_reason) {
    return {
      label: "Persistence degraded",
      message: runtime.degraded_reason,
      tone: "warning",
    };
  }
  if (runtime.enabled_count > 0) {
    return {
      label: "Persistence opt-in",
      message: `${runtime.enabled_count} local writes enabled`,
      tone: "success",
    };
  }
  return {
    label: "Persistence off",
    message: "No delegate persistence writes",
    tone: "muted",
  };
}

export function describeAgentAssignmentState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const assignments = workbench?.agent_assignments ?? null;
  const summary = assignments?.summary ?? null;
  if (!summary) {
    return {
      label: "Assignments unknown",
      message: "No assignment summary",
      tone: "muted",
    };
  }
  const degraded = assignments?.degraded_reason || summary.degraded_reason;
  if (degraded) {
    return {
      label: "Assignments degraded",
      message: degraded,
      tone: "warning",
    };
  }
  if (summary.conflicts.length > 0) {
    return {
      label: "Assignment conflicts",
      message: `${summary.conflicts.length} write conflicts`,
      tone: "destructive",
    };
  }
  if (summary.blocked_count > 0 || summary.dependency_waiting_task_ids.length > 0) {
    return {
      label: "Assignments blocked",
      message: `${summary.blocked_count} blocked / ${summary.dependency_waiting_task_ids.length} waiting`,
      tone: "warning",
    };
  }
  if (summary.active_count > 0) {
    return {
      label: "Assignments active",
      message: `${summary.ready_task_ids.length} ready / ${summary.active_count} active`,
      tone: "primary",
    };
  }
  if (summary.total_count > 0 && summary.completed_count === summary.total_count) {
    return {
      label: "Assignments complete",
      message: `${summary.completed_count} completed`,
      tone: "success",
    };
  }
  return {
    label: "Assignments quiet",
    message: "No active assignments",
    tone: "muted",
  };
}

export function describeParallelAssignmentPlanState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const plan = workbench?.agent_assignments?.parallel_plan ?? null;
  if (!plan) {
    return {
      label: "Plan unknown",
      message: "No parallel plan",
      tone: "muted",
    };
  }
  if (plan.degraded_reason) {
    return {
      label: "Plan degraded",
      message: plan.degraded_reason,
      tone: "warning",
    };
  }
  if (plan.conflict_task_ids.length > 0) {
    return {
      label: "Plan sequenced",
      message: `${plan.conflict_task_ids.length} scoped conflicts`,
      tone: "warning",
    };
  }
  if (plan.waiting_task_ids.length > 0 || plan.blocked_task_ids.length > 0) {
    return {
      label: "Plan waiting",
      message: `${plan.waiting_task_ids.length} waiting / ${plan.blocked_task_ids.length} blocked`,
      tone: "warning",
    };
  }
  const plannedTasks = plan.batches.reduce(
    (count, batch) => count + batch.task_ids.length,
    0,
  );
  if (plannedTasks > 0) {
    return {
      label: "Plan ready",
      message: `${plannedTasks} tasks / ${plan.batches.length} batches`,
      tone: "primary",
    };
  }
  if (plan.active_task_ids.length > 0) {
    return {
      label: "Plan active",
      message: `${plan.active_task_ids.length} running`,
      tone: "primary",
    };
  }
  return {
    label: "Plan quiet",
    message: "No planned parallel work",
    tone: "muted",
  };
}

export function describeHandoffProtocolState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const handoff = workbench?.agent_assignments?.handoff_protocol ?? null;
  if (!handoff) {
    return {
      label: "Handoff unknown",
      message: "No handoff summary",
      tone: "muted",
    };
  }
  if (handoff.degraded_reason) {
    return {
      label: "Handoff degraded",
      message: handoff.degraded_reason,
      tone: "warning",
    };
  }
  if (handoff.blocked_task_ids.length > 0 || handoff.human_decision_task_ids.length > 0) {
    return {
      label: "Handoff blocked",
      message: `${handoff.blocked_task_ids.length} blocked / ${handoff.human_decision_task_ids.length} human`,
      tone: "destructive",
    };
  }
  if (handoff.verification_missing_task_ids.length > 0) {
    return {
      label: "Handoff verify",
      message: `${handoff.verification_missing_task_ids.length} missing verification`,
      tone: "warning",
    };
  }
  if (handoff.reviewer_required_task_ids.length > 0) {
    return {
      label: "Handoff review",
      message: `${handoff.reviewer_required_task_ids.length} reviewer gates`,
      tone: "warning",
    };
  }
  if (handoff.ready_task_ids.length > 0) {
    return {
      label: "Handoff ready",
      message: `${handoff.ready_task_ids.length} ready`,
      tone: "success",
    };
  }
  return {
    label: "Handoff quiet",
    message: "No handoff gates",
    tone: "muted",
  };
}

export function describeDelegateRecoveryGateState(
  workbench: RunInspectorMemoryWorkbench | null,
): MemoryWorkbenchDisplay {
  const gates = workbench?.action_ledger?.recovery_gates ?? null;
  if (!gates) {
    return {
      label: "Recovery unknown",
      message: "No recovery summary",
      tone: "muted",
    };
  }
  if (gates.degraded_reason) {
    return {
      label: "Recovery degraded",
      message: gates.degraded_reason,
      tone: "warning",
    };
  }
  if (gates.blocked_count > 0) {
    return {
      label: "Recovery blocked",
      message: `${gates.blocked_count} blocked / ${gates.completed_count} completed`,
      tone: "destructive",
    };
  }
  if (gates.monitoring_count > 0) {
    return {
      label: "Recovery active",
      message: `${gates.monitoring_count} monitoring`,
      tone: "primary",
    };
  }
  if (gates.completed_count > 0) {
    return {
      label: "Recovery ready",
      message: `${gates.completed_count} completed`,
      tone: "success",
    };
  }
  return {
    label: "Recovery quiet",
    message: "No delegate recovery gates",
    tone: "muted",
  };
}
