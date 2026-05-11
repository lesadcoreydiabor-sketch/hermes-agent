import type {
  BrowserManageResponse,
  CommandsCatalogResponse,
  DelegationPauseResponse,
  DesktopStatusResponse,
  ProcessStopResponse,
  ReloadEnvResponse,
  ReloadMcpResponse,
  RollbackDiffResponse,
  RollbackListResponse,
  RollbackRestoreResponse,
  RunInspectorAssignmentPlan,
  RunInspectorAttentionSignal,
  RunInspectorEventSummary,
  RunInspectorEventsResponse,
  RunInspectorHealthSummary,
  RunInspectorMemoryWorkbench,
  RunInspectorMemoryWorkbenchResponse,
  RunInspectorSnapshotSummary,
  RunInspectorStatusResponse,
  SlashExecResponse,
  SpawnTreeListResponse,
  SpawnTreeLoadResponse,
  ToolsConfigureResponse
} from '../../../gatewayTypes.js'
import type { PanelSection } from '../../../types.js'
import { applyDelegationStatus, getDelegationState } from '../../delegationStore.js'
import { patchOverlayState } from '../../overlayStore.js'
import { getSpawnHistory, pushDiskSnapshot, setDiffPair, type SpawnSnapshot } from '../../spawnHistoryStore.js'
import type { SlashCommand } from '../types.js'

interface SkillInfo {
  category?: string
  description?: string
  name?: string
  path?: string
}

interface SkillsListResponse {
  skills?: Record<string, string[]>
}

interface SkillsInspectResponse {
  info?: SkillInfo
}

interface SkillsSearchResponse {
  results?: { description?: string; name: string }[]
}

interface SkillsInstallResponse {
  installed?: boolean
  name?: string
}

interface SkillsBrowseItem {
  description?: string
  name: string
  source?: string
  trust?: string
}

interface SkillsBrowseResponse {
  items?: SkillsBrowseItem[]
  page?: number
  total?: number
  total_pages?: number
}

interface SkillsReloadResponse {
  output?: string
}

const INSPECTOR_DEFAULT_PORT = 9119
const INSPECTOR_EVENTS_DEFAULT_LIMIT = 12
const INSPECTOR_TEXT_LIMIT = 140
const INSPECTOR_EVENT_FILTERS = ['all', 'active', 'attention', 'approval', 'cancelled', 'completed', 'failed', 'terminal', 'gateway', 'run', 'tool'] as const

type InspectorEventFilter = (typeof INSPECTOR_EVENT_FILTERS)[number]

const parseInspectorPort = (arg: string): null | number => {
  const text = arg.trim()
  if (!text) {
    return INSPECTOR_DEFAULT_PORT
  }
  if (!/^\d+$/.test(text)) {
    return null
  }
  const port = Number(text)
  return port >= 1 && port <= 65535 ? port : null
}

const parseInspectorEventsLimit = (arg: string): null | number => {
  const text = arg.trim()
  if (!text) {
    return INSPECTOR_EVENTS_DEFAULT_LIMIT
  }
  if (!/^\d+$/.test(text)) {
    return null
  }
  const limit = Number(text)
  return limit >= 1 && limit <= 100 ? limit : null
}

const parseInspectorEventsArgs = (
  arg: string
): null | { filter: InspectorEventFilter; limit: number } => {
  const parts = arg.trim().toLowerCase().split(/\s+/).filter(Boolean)
  let limit = INSPECTOR_EVENTS_DEFAULT_LIMIT
  let filter: InspectorEventFilter = 'all'

  for (const part of parts) {
    if (/^\d+$/.test(part)) {
      const parsed = parseInspectorEventsLimit(part)
      if (parsed === null) {
        return null
      }
      limit = parsed
      continue
    }

    if ((INSPECTOR_EVENT_FILTERS as readonly string[]).includes(part)) {
      filter = part as InspectorEventFilter
      continue
    }

    return null
  }

  return { filter, limit }
}

const desktopSummary = (r: DesktopStatusResponse): string => {
  if (r.record_present) {
    if (r.pid_status === 'running' && r.health === 'ok') {
      return 'running'
    }
    return `recorded (${r.pid_status || 'unknown'} / ${r.health || 'unknown'})`
  }
  if (r.compatible_dashboard) {
    return 'compatible dashboard'
  }
  if (r.ok === false) {
    return 'status unavailable'
  }
  return `not recorded (${r.health || 'unavailable'})`
}

const desktopSourceSummary = (r: DesktopStatusResponse): string => {
  if (r.record_present) {
    if (r.pid_status === 'running') {
      return 'desktop runtime record'
    }
    if (r.pid_status === 'stale') {
      return 'stale desktop runtime record'
    }
    return 'desktop runtime record present'
  }
  if (r.compatible_dashboard) {
    return 'reusable dashboard'
  }
  if (r.runtime_record_cleared) {
    return 'runtime record cleared'
  }
  return 'no desktop runtime record'
}

const clipInspectorText = (value: unknown, fallback = 'unknown', limit = INSPECTOR_TEXT_LIMIT): string => {
  if (value === null || value === undefined) {
    return fallback
  }

  let text = ''
  if (typeof value === 'string') {
    text = value
  } else {
    try {
      text = JSON.stringify(value) ?? ''
    } catch {
      text = String(value)
    }
  }

  text = text.replace(/\s+/g, ' ').trim()
  if (!text) {
    return fallback
  }
  return text.length > limit ? `${text.slice(0, Math.max(1, limit - 3))}...` : text
}

const activeToolSummary = (snapshot?: null | RunInspectorSnapshotSummary): null | string => {
  const tool = snapshot?.active_tool
  const name = clipInspectorText(tool?.name, '', 64)
  if (!name) {
    return null
  }

  const status = clipInspectorText(tool?.status, '', 48)
  const base = status ? `${name} (${status})` : name
  const summary = tool?.summary ?? tool?.args_summary
  const detail = summary ? clipInspectorText(summary, '', 96) : ''
  return detail ? `${base} - ${detail}` : base
}

const healthSummary = (
  items: RunInspectorSnapshotSummary['mcp_health'],
  okStatuses: string[]
): null | string => {
  if (!items?.length) {
    return null
  }

  const ok = items.filter(item => okStatuses.includes(String(item.status || '').toLowerCase())).length
  const attention = items.length - ok
  return attention > 0 ? `${ok}/${items.length} ok, ${attention} attention` : `${ok}/${items.length} ok`
}

const renderInspectorHealthRows = (
  items: RunInspectorHealthSummary[] | undefined,
  emptyLabel: string
): [string, string][] => {
  if (!items?.length) {
    return [[emptyLabel, 'none']]
  }

  return items.map(item => {
    const name = clipInspectorText(item.name, 'unknown', 64)
    const status = clipInspectorText(item.status, 'unknown', 40)
    const details = [
      item.toolset && `toolset=${clipInspectorText(item.toolset, '', 48)}`,
      item.reason && `reason=${clipInspectorText(item.reason, '', 72)}`,
      item.last_error_class && `error=${clipInspectorText(item.last_error_class, '', 48)}`,
      item.affected_tools?.length && `affected=${item.affected_tools.map(tool => clipInspectorText(tool, '', 32)).filter(Boolean).join(', ')}`
    ].filter(Boolean)

    return [`${name} (${status})`, details.join(' / ') || 'no details']
  })
}

const renderRunInspectorSnapshot = (snapshot?: null | RunInspectorSnapshotSummary) => {
  const status = clipInspectorText(snapshot?.status, 'unknown', 64)
  const source = clipInspectorText(snapshot?.source, 'unknown', 64)
  const rows: [string, string][] = [['Run', `${status} / ${source}`]]

  if (snapshot?.run_id && snapshot.run_id !== 'unknown') {
    rows.push(['Run ID', clipInspectorText(snapshot.run_id, '', 96)])
  }
  if (snapshot?.session_id) {
    rows.push(['Session', clipInspectorText(snapshot.session_id, '', 96)])
  }
  if (snapshot?.last_activity_at) {
    rows.push(['Last activity', clipInspectorText(snapshot.last_activity_at, '', 96)])
  }

  const tool = activeToolSummary(snapshot)
  if (tool) {
    rows.push(['Active tool', tool])
  }

  const tools = healthSummary(snapshot?.tool_health, ['available', 'running'])
  if (tools) {
    rows.push(['Tools', tools])
  }
  const mcp = healthSummary(snapshot?.mcp_health, ['connected'])
  if (mcp) {
    rows.push(['MCP', mcp])
  }
  if (snapshot?.degraded_reason) {
    rows.push(['Degraded', clipInspectorText(snapshot.degraded_reason)])
  }
  if (snapshot?.recovery_hint) {
    rows.push(['Recovery', clipInspectorText(snapshot.recovery_hint)])
  }
  if (snapshot?.privacy_flags?.length) {
    rows.push(['Privacy', snapshot.privacy_flags.map(flag => clipInspectorText(flag, '', 32)).filter(Boolean).join(', ')])
  }

  return rows
}

const renderAttentionSignals = (
  signals?: RunInspectorAttentionSignal[],
  attentionError?: null | string,
  maxSignals = 3
) => {
  const rows: [string, string][] = []
  const visible = signals?.slice(0, maxSignals) ?? []

  for (const signal of visible) {
    const title = clipInspectorText(signal.title || signal.kind, 'Attention', 64)
    const severity = clipInspectorText(signal.severity, '', 32)
    const context = [
      signal.run_id && `run=${clipInspectorText(signal.run_id, '', 64)}`,
      signal.session_id && `session=${clipInspectorText(signal.session_id, '', 64)}`,
      signal.route && `route=${clipInspectorText(signal.route, '', 64)}`
    ].filter(Boolean)
    rows.push([
      severity ? `${title} (${severity})` : title,
      [
        clipInspectorText(signal.body || signal.route || signal.kind, 'Open Run Inspector for details'),
        context.join(' / ')
      ].filter(Boolean).join('\n')
    ])
  }

  if ((signals?.length ?? 0) > visible.length) {
    rows.push(['More', `${(signals?.length ?? 0) - visible.length} more attention signals`])
  }
  if (attentionError) {
    rows.push(['Attention source', clipInspectorText(attentionError)])
  }
  if (!rows.length) {
    rows.push(['Attention', 'none'])
  }

  return rows
}

const renderRunInspectorEvents = (
  events?: RunInspectorEventSummary[],
  error?: null | string,
  emptyText = 'none'
) => {
  const rows: [string, string][] = []

  for (const event of events ?? []) {
    const id = event.id === undefined ? '?' : String(event.id)
    const type = clipInspectorText(event.type, 'event', 64)
    const meta = [
      event.status && `status=${clipInspectorText(event.status, '', 40)}`,
      event.tool && `tool=${clipInspectorText(event.tool, '', 48)}`,
      event.source && `source=${clipInspectorText(event.source, '', 48)}`,
      event.run_id && `run=${clipInspectorText(event.run_id, '', 64)}`,
      event.session_id && `session=${clipInspectorText(event.session_id, '', 64)}`
    ].filter(Boolean)
    const message = clipInspectorText(event.message || event.timestamp, 'no message', 120)
    rows.push([`#${id} ${type}`, meta.length ? `${meta.join(' / ')}\n${message}` : message])
  }

  if (error) {
    rows.push(['Event source', clipInspectorText(error)])
  }
  if (!rows.length) {
    rows.push(['Events', emptyText])
  }

  return rows
}

const isAttentionRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  return isApprovalRunInspectorEvent(event) || isFailedRunInspectorEvent(event)
}

const isActiveRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  const type = String(event.type || '').toLowerCase()
  const status = String(event.status || '').toLowerCase()
  return (
    status === 'running' ||
    status === 'queued' ||
    type === 'gateway.forwarder.started' ||
    type === 'run.started' ||
    type === 'run.running' ||
    type === 'tool.started' ||
    type === 'tool.progress'
  )
}

const isApprovalRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  const type = String(event.type || '').toLowerCase()
  const status = String(event.status || '').toLowerCase()
  return type === 'approval.request' || status === 'waiting'
}

const isFailedRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  const type = String(event.type || '').toLowerCase()
  const status = String(event.status || '').toLowerCase()
  return status === 'failed' || type.endsWith('.failed')
}

const isCancelledRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  const type = String(event.type || '').toLowerCase()
  const status = String(event.status || '').toLowerCase()
  return status === 'cancelled' || type.endsWith('.cancelled')
}

const isCompletedRunInspectorEvent = (event: RunInspectorEventSummary): boolean => {
  const type = String(event.type || '').toLowerCase()
  const status = String(event.status || '').toLowerCase()
  return status === 'completed' || type.endsWith('.completed')
}

const isTerminalRunInspectorEvent = (event: RunInspectorEventSummary): boolean =>
  isCancelledRunInspectorEvent(event) || isCompletedRunInspectorEvent(event) || isFailedRunInspectorEvent(event)

const latestRunInspectorEvent = (events: RunInspectorEventSummary[]): RunInspectorEventSummary | undefined =>
  [...events].sort((left, right) => Number(left.id ?? 0) - Number(right.id ?? 0)).at(-1)

const renderRunInspectorEventSummary = (
  events: RunInspectorEventSummary[] | undefined,
  filtered: RunInspectorEventSummary[],
  filter: InspectorEventFilter
): [string, string][] => {
  const source = events ?? []
  const latest = latestRunInspectorEvent(source)
  const latestType = latest ? clipInspectorText(latest.type, 'event', 64) : 'none'
  const latestId = latest?.id === undefined ? '?' : String(latest.id)

  return [
    ['Fetched', String(source.length)],
    ['Showing', filter === 'all' ? String(filtered.length) : `${filtered.length} ${filter}`],
    ['Active', String(source.filter(isActiveRunInspectorEvent).length)],
    ['Attention', String(source.filter(isAttentionRunInspectorEvent).length)],
    ['Approval', String(source.filter(isApprovalRunInspectorEvent).length)],
    ['Cancelled', String(source.filter(isCancelledRunInspectorEvent).length)],
    ['Completed', String(source.filter(isCompletedRunInspectorEvent).length)],
    ['Failed', String(source.filter(isFailedRunInspectorEvent).length)],
    ['Terminal', String(source.filter(isTerminalRunInspectorEvent).length)],
    ['Latest', latest ? `#${latestId} ${latestType}` : 'none']
  ]
}

const inspectorListCount = (items?: unknown[]): number => items?.length ?? 0

const renderInspectorTaskIds = (ids?: string[], limit = 6): string => {
  const visible = ids?.map(id => clipInspectorText(id, '', 48)).filter(Boolean) ?? []
  if (!visible.length) {
    return 'none'
  }
  const shown = visible.slice(0, limit)
  const more = visible.length > shown.length ? `, +${visible.length - shown.length} more` : ''
  return `${shown.join(', ')}${more}`
}

const plannedInspectorTaskCount = (plan?: RunInspectorAssignmentPlan): number => {
  if (!Array.isArray(plan?.batches)) {
    return 0
  }
  return plan.batches.reduce((count, batch) => count + inspectorListCount(batch.task_ids), 0)
}

const renderRunInspectorMemoryWorkbenchSummary = (
  workbench?: null | RunInspectorMemoryWorkbench
): [string, string][] => {
  const assignments = workbench?.agent_assignments
  const summary = assignments?.summary
  const plan = assignments?.parallel_plan
  const handoff = assignments?.handoff_protocol
  const plannedTasks = plannedInspectorTaskCount(plan)
  const rows: [string, string][] = [
    [
      'Workbench',
      [
        clipInspectorText(workbench?.status, 'unknown', 48),
        clipInspectorText(workbench?.status_reason, '', 96)
      ].filter(Boolean).join(' / ')
    ],
    [
      'Assignments',
      summary
        ? `${summary.total_count ?? 0} total / ${summary.active_count ?? 0} active / ${inspectorListCount(summary.ready_task_ids)} ready`
        : 'unknown'
    ],
    [
      'Plan',
      plan
        ? `${plannedTasks} planned / ${inspectorListCount(plan.batches)} batches / ${plan.max_parallel_workers ?? 0} max`
        : 'unknown'
    ],
    [
      'Waiting',
      plan
        ? `${inspectorListCount(plan.waiting_task_ids)} waiting / ${inspectorListCount(plan.blocked_task_ids)} blocked`
        : `${inspectorListCount(summary?.dependency_waiting_task_ids)} waiting / ${summary?.blocked_count ?? 0} blocked`
    ],
    [
      'Conflicts',
      plan
        ? `${inspectorListCount(plan.conflict_task_ids)} scoped / ${inspectorListCount(plan.conflicts)} pairs`
        : `${inspectorListCount(summary?.conflicts)} pairs`
    ],
    [
      'Handoff',
      handoff
        ? `${inspectorListCount(handoff.ready_task_ids)} ready / ${inspectorListCount(handoff.verification_missing_task_ids)} verify / ${inspectorListCount(handoff.reviewer_required_task_ids)} review`
        : 'unknown'
    ],
    [
      'Memory',
      `${workbench?.memory?.status ?? 'unknown'} / ${workbench?.memory?.provider_count ?? 0} providers`
    ],
    [
      'Persistence',
      `${workbench?.runtime_persistence?.status ?? 'unknown'} / ${workbench?.runtime_persistence?.enabled_count ?? 0} enabled`
    ]
  ]

  const degraded =
    workbench?.degraded_reason ||
    assignments?.degraded_reason ||
    summary?.degraded_reason ||
    plan?.degraded_reason ||
    handoff?.degraded_reason ||
    workbench?.memory?.degraded_reason ||
    workbench?.runtime_persistence?.degraded_reason
  if (degraded) {
    rows.push(['Degraded', clipInspectorText(degraded)])
  }
  if (workbench?.privacy_class) {
    rows.push(['Privacy', clipInspectorText(workbench.privacy_class, '', 48)])
  }
  return rows
}

const renderRunInspectorAssignmentRows = (
  workbench?: null | RunInspectorMemoryWorkbench,
  limit = 5
): [string, string][] => {
  const assignments = workbench?.agent_assignments?.assignments ?? []
  const rows = assignments.slice(0, limit).map(assignment => {
    const task = clipInspectorText(assignment.task_id || assignment.title, 'task', 64)
    const files = inspectorListCount(assignment.write_scope?.files)
    const directories = inspectorListCount(assignment.write_scope?.directories)
    const dependencies = inspectorListCount(assignment.dependencies?.task_ids)
    return [
      task,
      [
        `role=${clipInspectorText(assignment.role, 'unknown', 32)}`,
        `status=${clipInspectorText(assignment.status, 'unknown', 32)}`,
        `deps=${dependencies}`,
        `scope=${files} files/${directories} dirs`
      ].join(' / ')
    ] as [string, string]
  })

  if (assignments.length > rows.length) {
    rows.push(['More', `${assignments.length - rows.length} more assignments`])
  }
  if (!rows.length) {
    rows.push(['Assignments', 'none'])
  }
  return rows
}

const renderRunInspectorAssignmentPlanRows = (
  workbench?: null | RunInspectorMemoryWorkbench,
  limit = 5
): [string, string][] => {
  const plan = workbench?.agent_assignments?.parallel_plan
  if (!plan) {
    return [['Plan', 'none']]
  }

  const rows = (plan.batches ?? []).slice(0, limit).map(batch => [
    `Batch ${batch.index ?? '?'}`,
    renderInspectorTaskIds(batch.task_ids)
  ] as [string, string])
  if ((plan.batches?.length ?? 0) > rows.length) {
    rows.push(['More batches', `${(plan.batches?.length ?? 0) - rows.length} more batches`])
  }
  rows.push(['Active', renderInspectorTaskIds(plan.active_task_ids)])
  rows.push(['Waiting', renderInspectorTaskIds(plan.waiting_task_ids)])
  rows.push(['Blocked', renderInspectorTaskIds(plan.blocked_task_ids)])
  rows.push(['Sequenced', renderInspectorTaskIds(plan.conflict_task_ids)])
  if (plan.degraded_reason) {
    rows.push(['Plan degraded', clipInspectorText(plan.degraded_reason)])
  }
  return rows
}

const renderRunInspectorHandoffRows = (
  workbench?: null | RunInspectorMemoryWorkbench
): [string, string][] => {
  const handoff = workbench?.agent_assignments?.handoff_protocol
  if (!handoff) {
    return [['Handoff', 'none']]
  }

  const rows: [string, string][] = [
    ['Status', clipInspectorText(handoff.status, 'unknown', 48)],
    ['Ready', renderInspectorTaskIds(handoff.ready_task_ids)],
    ['Needs verification', renderInspectorTaskIds(handoff.verification_missing_task_ids)],
    ['Needs review', renderInspectorTaskIds(handoff.reviewer_required_task_ids)],
    ['Human decision', renderInspectorTaskIds(handoff.human_decision_task_ids)],
    ['Blocked', renderInspectorTaskIds(handoff.blocked_task_ids)],
    ['Conflicts', renderInspectorTaskIds(handoff.conflict_task_ids)]
  ]
  if (handoff.degraded_reason) {
    rows.push(['Handoff degraded', clipInspectorText(handoff.degraded_reason)])
  }
  return rows
}

const filterRunInspectorEvents = (
  events: RunInspectorEventSummary[] | undefined,
  filter: InspectorEventFilter
): RunInspectorEventSummary[] => {
  const source = events ?? []
  if (filter === 'all') {
    return source
  }

  return source.filter(event => {
    const type = String(event.type || '').toLowerCase()
    const status = String(event.status || '').toLowerCase()
    const sourceName = String(event.source || '').toLowerCase()

    if (filter === 'active') {
      return isActiveRunInspectorEvent(event)
    }
    if (filter === 'attention') {
      return isAttentionRunInspectorEvent(event)
    }
    if (filter === 'approval') {
      return isApprovalRunInspectorEvent(event)
    }
    if (filter === 'cancelled') {
      return isCancelledRunInspectorEvent(event)
    }
    if (filter === 'completed') {
      return isCompletedRunInspectorEvent(event)
    }
    if (filter === 'failed') {
      return type.endsWith('.failed') || status === 'failed'
    }
    if (filter === 'terminal') {
      return isTerminalRunInspectorEvent(event)
    }
    if (filter === 'gateway') {
      return type.startsWith('gateway.') || sourceName.includes('gateway')
    }
    if (filter === 'run') {
      return type.startsWith('run.')
    }
    if (filter === 'tool') {
      return type.startsWith('tool.')
    }
    return true
  })
}

const renderInspectorStatus = (r: DesktopStatusResponse) => {
  const rows: [string, string][] = [
    ['Desktop', desktopSummary(r)],
    ['Source', desktopSourceSummary(r)],
    ['Run Inspector', r.url || `http://127.0.0.1:${r.port || INSPECTOR_DEFAULT_PORT}/run-inspector`],
    ['Health', [r.health || 'unknown', r.health_reason].filter(Boolean).join(' / ')],
    ['PID', r.pid ? `${r.pid} (${r.pid_status || 'unknown'})` : r.pid_status || 'none']
  ]

  if (r.pid_reason) {
    rows.push(['PID reason', r.pid_reason])
  }
  if (r.started_at) {
    rows.push(['Started', r.started_at])
  }
  if (r.host) {
    rows.push(['Host', r.host])
  }
  if (r.route) {
    rows.push(['Route', r.route])
  }
  if (r.runtime_record_cleared) {
    rows.push(['Record', 'cleared stale runtime record'])
  }
  if (r.reuse_command) {
    rows.push(['Reuse', r.reuse_command])
  }
  if (r.manual_url) {
    rows.push(['Open', r.manual_url])
  }
  if (r.stop_command) {
    rows.push(['Stop guidance', r.stop_command])
  }
  if (r.error) {
    rows.push(['Error', r.error])
  }

  return rows
}

export const opsCommands: SlashCommand[] = [
  {
    help: 'stop background processes',
    name: 'stop',
    run: (_arg, ctx) => {
      ctx.gateway
        .rpc<ProcessStopResponse>('process.stop', {})
        .then(
          ctx.guarded<ProcessStopResponse>(r => {
            const killed = Number(r.killed ?? 0)
            const noun = killed === 1 ? 'process' : 'processes'
            ctx.transcript.sys(`stopped ${killed} background ${noun}`)
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['reload_mcp'],
    help: 'reload MCP servers in the live session (warns about prompt cache invalidation)',
    name: 'reload-mcp',
    run: (arg, ctx) => {
      // Parse arg: `now` / `always` skip the confirmation gate.
      // `always` additionally persists approvals.mcp_reload_confirm=false.
      const a = (arg || '').trim().toLowerCase()
      const params: { session_id: string | null; confirm?: boolean; always?: boolean } = {
        session_id: ctx.sid
      }
      if (a === 'now' || a === 'approve' || a === 'once' || a === 'yes') {
        params.confirm = true
      } else if (a === 'always') {
        params.confirm = true
        params.always = true
      }

      ctx.gateway
        .rpc<ReloadMcpResponse>('reload.mcp', params)
        .then(
          ctx.guarded<ReloadMcpResponse>(r => {
            if (r.status === 'confirm_required') {
              ctx.transcript.sys(r.message || '/reload-mcp requires confirmation')
              return
            }
            if (r.status === 'reloaded') {
              ctx.transcript.sys(
                params.always
                  ? 'MCP servers reloaded · future /reload-mcp will run without confirmation'
                  : 'MCP servers reloaded'
              )
              return
            }
            ctx.transcript.sys('reload complete')
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    help: 're-read ~/.hermes/.env into the running gateway (CLI parity)',
    name: 'reload',
    run: (_arg, ctx) => {
      ctx.gateway
        .rpc<ReloadEnvResponse>('reload.env', {})
        .then(
          ctx.guarded<ReloadEnvResponse>(r => {
            const n = Number(r.updated ?? 0)
            const noun = n === 1 ? 'var' : 'vars'

            ctx.transcript.sys(`reloaded .env (${n} ${noun} updated)`)
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    help: 'manage browser CDP connection [connect|disconnect|status]',
    name: 'browser',
    run: (arg, ctx) => {
      const [rawAction = 'status', ...rest] = arg.trim().split(/\s+/).filter(Boolean)
      const action = rawAction.toLowerCase()

      if (!['connect', 'disconnect', 'status'].includes(action)) {
        return ctx.transcript.sys(
          'usage: /browser [connect|disconnect|status] [url] · persistent: set browser.cdp_url in config.yaml'
        )
      }

      const sid = ctx.sid ?? null
      const url = action === 'connect' ? rest.join(' ').trim() || 'http://127.0.0.1:9222' : undefined

      if (url) {
        ctx.transcript.sys(`checking Chrome remote debugging at ${url}...`)
      }

      ctx.gateway
        .rpc<BrowserManageResponse>('browser.manage', { action, session_id: sid, ...(url && { url }) })
        .then(
          ctx.guarded<BrowserManageResponse>(r => {
            // Without a session we can't subscribe to streamed
            // browser.progress events, so flush the bundled list.
            if (!sid) {
              r.messages?.forEach(message => ctx.transcript.sys(message))
            }

            if (action === 'status') {
              return ctx.transcript.sys(
                r.connected
                  ? `browser connected: ${r.url || '(url unavailable)'}`
                  : 'browser not connected (try /browser connect <url> or set browser.cdp_url in config.yaml)'
              )
            }

            if (action === 'disconnect') {
              return ctx.transcript.sys('browser disconnected')
            }

            if (r.connected) {
              ctx.transcript.sys('Browser connected to live Chrome via CDP')
              ctx.transcript.sys(`Endpoint: ${r.url || '(url unavailable)'}`)
              ctx.transcript.sys('next browser tool call will use this CDP endpoint')
            }
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector'],
    help: 'show read-only Run Inspector snapshot, attention, and desktop status [/inspector [port]]',
    name: 'inspector',
    run: (arg, ctx) => {
      const port = parseInspectorPort(arg)
      if (port === null) {
        return ctx.transcript.sys('usage: /inspector [port]')
      }

      ctx.gateway
        .rpc<RunInspectorStatusResponse>('run_inspector.status', { port })
        .then(
          ctx.guarded<RunInspectorStatusResponse>(r => {
            ctx.transcript.panel('Run Inspector', [
              {
                rows: renderRunInspectorSnapshot(r?.snapshot),
                title: 'Run Snapshot'
              },
              {
                rows: renderAttentionSignals(r?.attention, r?.attention_error),
                title: 'Attention'
              },
              {
                rows: renderInspectorStatus(r?.desktop || {}),
                title: 'Desktop Shell'
              },
              {
                text: 'read-only status; use hermes desktop to start, stop, or reuse the dashboard'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-attention'],
    help: 'show read-only Run Inspector attention signals [/inspector-attention [port]]',
    name: 'inspector-attention',
    run: (arg, ctx) => {
      const port = parseInspectorPort(arg)
      if (port === null) {
        return ctx.transcript.sys('usage: /inspector-attention [port]')
      }

      ctx.gateway
        .rpc<RunInspectorStatusResponse>('run_inspector.status', { port })
        .then(
          ctx.guarded<RunInspectorStatusResponse>(r => {
            ctx.transcript.panel('Run Inspector Attention', [
              {
                rows: renderAttentionSignals(r?.attention, r?.attention_error, 20),
                title: `Signals ${r?.attention?.length ?? 0}`
              },
              {
                text: 'read-only attention summary; raw logs, prompts, tool args, and secrets are not shown'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-snapshot'],
    help: 'show read-only Run Inspector run snapshot [/inspector-snapshot [port]]',
    name: 'inspector-snapshot',
    run: (arg, ctx) => {
      const port = parseInspectorPort(arg)
      if (port === null) {
        return ctx.transcript.sys('usage: /inspector-snapshot [port]')
      }

      ctx.gateway
        .rpc<RunInspectorStatusResponse>('run_inspector.status', { port })
        .then(
          ctx.guarded<RunInspectorStatusResponse>(r => {
            ctx.transcript.panel('Run Inspector Snapshot', [
              {
                rows: renderRunInspectorSnapshot(r?.snapshot),
                title: 'Run Snapshot'
              },
              {
                text: 'read-only snapshot summary; raw prompts, tool args, and secrets are not shown'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-desktop'],
    help: 'show read-only Run Inspector desktop shell status [/inspector-desktop [port]]',
    name: 'inspector-desktop',
    run: (arg, ctx) => {
      const port = parseInspectorPort(arg)
      if (port === null) {
        return ctx.transcript.sys('usage: /inspector-desktop [port]')
      }

      ctx.gateway
        .rpc<RunInspectorStatusResponse>('run_inspector.status', { port })
        .then(
          ctx.guarded<RunInspectorStatusResponse>(r => {
            ctx.transcript.panel('Run Inspector Desktop', [
              {
                rows: renderInspectorStatus(r?.desktop || {}),
                title: 'Desktop Shell'
              },
              {
                text: 'read-only desktop status; use hermes desktop to start, stop, or reuse the dashboard'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-health'],
    help: 'show read-only Run Inspector tool and MCP health [/inspector-health [port]]',
    name: 'inspector-health',
    run: (arg, ctx) => {
      const port = parseInspectorPort(arg)
      if (port === null) {
        return ctx.transcript.sys('usage: /inspector-health [port]')
      }

      ctx.gateway
        .rpc<RunInspectorStatusResponse>('run_inspector.status', { port })
        .then(
          ctx.guarded<RunInspectorStatusResponse>(r => {
            ctx.transcript.panel('Run Inspector Health', [
              {
                rows: renderInspectorHealthRows(r?.snapshot?.tool_health, 'Tools'),
                title: 'Tools'
              },
              {
                rows: renderInspectorHealthRows(r?.snapshot?.mcp_health, 'MCP'),
                title: 'MCP'
              },
              {
                text: 'read-only health summary; no tool dispatch, MCP reconnect, or config mutation'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-events'],
    help: 'show recent read-only Run Inspector events [/inspector-events [limit] [all|active|attention|approval|cancelled|completed|failed|terminal|gateway|run|tool]]',
    name: 'inspector-events',
    run: (arg, ctx) => {
      const parsed = parseInspectorEventsArgs(arg)
      if (parsed === null) {
        return ctx.transcript.sys('usage: /inspector-events [limit 1..100] [all|active|attention|approval|cancelled|completed|failed|terminal|gateway|run|tool]')
      }

      ctx.gateway
        .rpc<RunInspectorEventsResponse>('run_inspector.events', { limit: parsed.limit })
        .then(
          ctx.guarded<RunInspectorEventsResponse>(r => {
            const filtered = filterRunInspectorEvents(r?.events, parsed.filter)
            const sourceCount = r?.events?.length ?? 0
            const emptyText =
              parsed.filter === 'all' || sourceCount === 0 ? 'none' : `no ${parsed.filter} events`
            ctx.transcript.panel('Run Inspector Events', [
              {
                rows: renderRunInspectorEventSummary(r?.events, filtered, parsed.filter),
                title: 'Summary'
              },
              {
                rows: renderRunInspectorEvents(filtered, r?.error, emptyText),
                title:
                  parsed.filter === 'all'
                    ? `Recent ${sourceCount}`
                    : `Recent ${filtered.length}/${sourceCount} ${parsed.filter}`
              },
              {
                text: 'read-only event timeline; raw logs, prompts, tool args, and secrets are not shown'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['run-inspector-memory'],
    help: 'show read-only Run Inspector multi-agent memory workbench [/inspector-memory [limit]]',
    name: 'inspector-memory',
    run: (arg, ctx) => {
      const limit = parseInspectorEventsLimit(arg)
      if (limit === null) {
        return ctx.transcript.sys('usage: /inspector-memory [limit 1..100]')
      }

      ctx.gateway
        .rpc<RunInspectorMemoryWorkbenchResponse>('run_inspector.memory_workbench', { limit })
        .then(
          ctx.guarded<RunInspectorMemoryWorkbenchResponse>(r => {
            ctx.transcript.panel('Run Inspector Memory', [
              {
                rows: renderRunInspectorMemoryWorkbenchSummary(r?.workbench),
                title: r?.ok === false ? 'Summary degraded' : 'Summary'
              },
              {
                rows: renderRunInspectorAssignmentRows(r?.workbench),
                title: 'Assignments'
              },
              {
                rows: renderRunInspectorAssignmentPlanRows(r?.workbench),
                title: 'Parallel Plan'
              },
              {
                rows: renderRunInspectorHandoffRows(r?.workbench),
                title: 'Handoff'
              },
              {
                text: 'read-only memory workbench; no agent spawn, tool dispatch, memory write, skill edit, config edit, or task mutation'
              }
            ])
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    help: 'list, diff, or restore checkpoints',
    name: 'rollback',
    run: (arg, ctx) => {
      if (!ctx.sid) {
        return ctx.transcript.sys('no active session — nothing to rollback')
      }

      const trimmed = arg.trim()
      const [first = '', ...rest] = trimmed.split(/\s+/).filter(Boolean)
      const lower = first.toLowerCase()

      if (!trimmed || lower === 'list' || lower === 'ls') {
        return ctx.gateway
          .rpc<RollbackListResponse>('rollback.list', { session_id: ctx.sid })
          .then(
            ctx.guarded<RollbackListResponse>(r => {
              if (!r.enabled) {
                return ctx.transcript.sys('checkpoints are not enabled')
              }

              const checkpoints = r.checkpoints ?? []

              if (!checkpoints.length) {
                return ctx.transcript.sys('no checkpoints found')
              }

              ctx.transcript.panel('Rollback checkpoints', [
                {
                  rows: checkpoints.map((c, idx) => [
                    `${idx + 1}. ${c.hash.slice(0, 10)}`,
                    [c.timestamp, c.message].filter(Boolean).join(' · ') || '(no metadata)'
                  ])
                }
              ])
            })
          )
          .catch(ctx.guardedErr)
      }

      if (lower === 'diff') {
        const hash = rest[0]

        if (!hash) {
          return ctx.transcript.sys('usage: /rollback diff <checkpoint>')
        }

        return ctx.gateway
          .rpc<RollbackDiffResponse>('rollback.diff', { hash, session_id: ctx.sid })
          .then(
            ctx.guarded<RollbackDiffResponse>(r => {
              const body = (r.rendered || r.diff || '').trim()

              if (!body && !r.stat) {
                return ctx.transcript.sys('no changes since this checkpoint')
              }

              const text = [r.stat || '', body].filter(Boolean).join('\n\n')
              ctx.transcript.page(text, 'Rollback diff')
            })
          )
          .catch(ctx.guardedErr)
      }

      const hash = first
      const filePath = rest.join(' ').trim()

      return ctx.gateway
        .rpc<RollbackRestoreResponse>('rollback.restore', {
          ...(filePath ? { file_path: filePath } : {}),
          hash,
          session_id: ctx.sid
        })
        .then(
          ctx.guarded<RollbackRestoreResponse>(r => {
            if (!r.success) {
              return ctx.transcript.sys(`rollback failed: ${r.error || r.message || 'unknown error'}`)
            }

            const target = filePath || 'workspace'
            const detail = r.reason || r.message || r.restored_to || 'restored'
            ctx.transcript.sys(`rollback restored ${target}: ${detail}`)

            if ((r.history_removed ?? 0) > 0) {
              ctx.transcript.setHistoryItems(prev => ctx.transcript.trimLastExchange(prev))
            }
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    aliases: ['tasks'],
    help: 'open the spawn-tree dashboard (live audit + kill/pause controls)',
    name: 'agents',
    run: (arg, ctx) => {
      const sub = arg.trim().toLowerCase()

      // Stay compatible with the gateway `/agents [pause|resume|status]` CLI —
      // explicit subcommands skip the overlay and act directly so scripts and
      // multi-step flows can drive it without entering interactive mode.
      if (sub === 'pause' || sub === 'resume' || sub === 'unpause') {
        const paused = sub === 'pause'
        ctx.gateway.gw
          .request<DelegationPauseResponse>('delegation.pause', { paused })
          .then(r => {
            applyDelegationStatus({ paused: r?.paused })
            ctx.transcript.sys(`delegation · ${r?.paused ? 'paused' : 'resumed'}`)
          })
          .catch(ctx.guardedErr)

        return
      }

      if (sub === 'status') {
        const d = getDelegationState()
        ctx.transcript.sys(
          `delegation · ${d.paused ? 'paused' : 'active'} · caps d${d.maxSpawnDepth ?? '?'}/${d.maxConcurrentChildren ?? '?'}`
        )

        return
      }

      patchOverlayState({ agents: true, agentsInitialHistoryIndex: 0 })
    }
  },

  {
    help: 'replay a completed spawn tree · `/replay [N|last|list|load <path>]`',
    name: 'replay',
    run: (arg, ctx) => {
      const history = getSpawnHistory()
      const raw = arg.trim()
      const lower = raw.toLowerCase()

      // ── Disk-backed listing ─────────────────────────────────────
      if (lower === 'list' || lower === 'ls') {
        ctx.gateway
          .rpc<SpawnTreeListResponse>('spawn_tree.list', {
            limit: 30,
            session_id: ctx.sid ?? 'default'
          })
          .then(
            ctx.guarded<SpawnTreeListResponse>(r => {
              const entries = r.entries ?? []

              if (!entries.length) {
                return ctx.transcript.sys('no archived spawn trees on disk for this session')
              }

              const rows: [string, string][] = entries.map(e => {
                const ts = e.finished_at ? new Date(e.finished_at * 1000).toLocaleString() : '?'
                const label = e.label || `${e.count} subagents`

                return [`${ts} · ${e.count}×`, `${label}\n  ${e.path}`]
              })

              ctx.transcript.panel('Archived spawn trees', [{ rows }])
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      // ── Disk-backed load by path ─────────────────────────────────
      if (lower.startsWith('load ')) {
        const path = raw.slice(5).trim()

        if (!path) {
          return ctx.transcript.sys('usage: /replay load <path>')
        }

        ctx.gateway
          .rpc<SpawnTreeLoadResponse>('spawn_tree.load', { path })
          .then(
            ctx.guarded<SpawnTreeLoadResponse>(r => {
              if (!r.subagents?.length) {
                return ctx.transcript.sys('snapshot empty or unreadable')
              }

              // Push onto the in-memory history so the overlay picks it up
              // by index 1 just like any other snapshot.
              pushDiskSnapshot(r, path)
              patchOverlayState({ agents: true, agentsInitialHistoryIndex: 1 })
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      // ── In-memory nav (same-session) ─────────────────────────────
      if (!history.length) {
        return ctx.transcript.sys('no completed spawn trees this session · try /replay list')
      }

      let index = 1

      if (raw && lower !== 'last') {
        const parsed = parseInt(raw, 10)

        if (Number.isNaN(parsed) || parsed < 1 || parsed > history.length) {
          return ctx.transcript.sys(`replay: index out of range 1..${history.length} · use /replay list for disk`)
        }

        index = parsed
      }

      patchOverlayState({ agents: true, agentsInitialHistoryIndex: index })
    }
  },

  {
    help: 'diff two completed spawn trees · `/replay-diff <baseline> <candidate>` (indexes from /replay list or history N)',
    name: 'replay-diff',
    run: (arg, ctx) => {
      const parts = arg.trim().split(/\s+/).filter(Boolean)

      if (parts.length !== 2) {
        return ctx.transcript.sys('usage: /replay-diff <a> <b>  (e.g. /replay-diff 1 2 for last two)')
      }

      const [a, b] = parts
      const history = getSpawnHistory()

      const resolve = (token: string): null | SpawnSnapshot => {
        const n = parseInt(token!, 10)

        if (Number.isFinite(n) && n >= 1 && n <= history.length) {
          return history[n - 1] ?? null
        }

        return null
      }

      const baseline = resolve(a!)
      const candidate = resolve(b!)

      if (!baseline || !candidate) {
        return ctx.transcript.sys(`replay-diff: could not resolve indices · history has ${history.length} entries`)
      }

      setDiffPair({ baseline, candidate })
      patchOverlayState({ agents: true, agentsInitialHistoryIndex: 0 })
    }
  },

  {
    aliases: ['reload_skills'],
    help: 're-scan installed skills in the live TUI gateway',
    name: 'reload-skills',
    run: (_arg, ctx) => {
      ctx.gateway
        .rpc<SkillsReloadResponse>('skills.reload', {})
        .then(
          ctx.guarded<SkillsReloadResponse>(r => {
            ctx.transcript.page(r.output || 'skills reloaded', 'Reload Skills')
            ctx.gateway
              .rpc<CommandsCatalogResponse>('commands.catalog', {})
              .then(
                ctx.guarded<CommandsCatalogResponse>(catalog => {
                  if (!catalog?.pairs) {
                    return
                  }

                  ctx.local.setCatalog({
                    canon: (catalog.canon ?? {}) as Record<string, string>,
                    categories: catalog.categories ?? [],
                    pairs: catalog.pairs as [string, string][],
                    skillCount: (catalog.skill_count ?? 0) as number,
                    sub: (catalog.sub ?? {}) as Record<string, string[]>
                  })
                })
              )
              .catch(() => {})
          })
        )
        .catch(ctx.guardedErr)
    }
  },

  {
    help: 'browse, inspect, install skills',
    name: 'skills',
    run: (arg, ctx, cmd) => {
      const text = arg.trim()

      if (!text) {
        return patchOverlayState({ skillsHub: true })
      }

      const [sub, ...rest] = text.split(/\s+/)
      const query = rest.join(' ').trim()
      const { rpc } = ctx.gateway
      const { panel, sys } = ctx.transcript
      const runViaSlashWorker = () => {
        ctx.gateway.gw
          .request<SlashExecResponse>('slash.exec', { command: cmd.slice(1), session_id: ctx.sid })
          .then(r => {
            if (ctx.stale()) {
              return
            }

            const body = r?.output || '/skills: no output'
            const formatted = r?.warning ? `warning: ${r.warning}\n${body}` : body
            const long = formatted.length > 180 || formatted.split('\n').filter(Boolean).length > 2

            long ? ctx.transcript.page(formatted, 'Skills') : ctx.transcript.sys(formatted)
          })
          .catch(ctx.guardedErr)
      }

      if (sub === 'list') {
        rpc<SkillsListResponse>('skills.manage', { action: 'list' })
          .then(
            ctx.guarded<SkillsListResponse>(r => {
              const cats = Object.entries(r.skills ?? {}).sort()

              if (!cats.length) {
                return sys('no skills available')
              }

              panel(
                'Skills',
                cats.map<PanelSection>(([title, items]) => ({ items, title }))
              )
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      if (sub === 'inspect') {
        if (!query) {
          return sys('usage: /skills inspect <name>')
        }

        rpc<SkillsInspectResponse>('skills.manage', { action: 'inspect', query })
          .then(
            ctx.guarded<SkillsInspectResponse>(r => {
              const info = r.info ?? {}

              if (!info.name) {
                return sys(`unknown skill: ${query}`)
              }

              const rows: [string, string][] = [
                ['Name', String(info.name)],
                ['Category', String(info.category ?? '')],
                ['Path', String(info.path ?? '')]
              ]

              const sections: PanelSection[] = [{ rows }]

              if (info.description) {
                sections.push({ text: String(info.description) })
              }

              panel('Skill', sections)
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      if (sub === 'search') {
        if (!query) {
          return sys('usage: /skills search <query>')
        }

        rpc<SkillsSearchResponse>('skills.manage', { action: 'search', query })
          .then(
            ctx.guarded<SkillsSearchResponse>(r => {
              const results = r.results ?? []

              if (!results.length) {
                return sys(`no results for: ${query}`)
              }

              panel(`Search: ${query}`, [{ rows: results.map(s => [s.name, s.description ?? '']) }])
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      if (sub === 'install') {
        if (!query) {
          return sys('usage: /skills install <name or url>')
        }

        sys(`installing ${query}…`)

        rpc<SkillsInstallResponse>('skills.manage', { action: 'install', query })
          .then(
            ctx.guarded<SkillsInstallResponse>(r =>
              sys(r.installed ? `installed ${r.name ?? query}` : 'install failed')
            )
          )
          .catch(ctx.guardedErr)

        return
      }

      if (sub === 'browse') {
        const pageNum = query ? parseInt(query, 10) : 1

        if (Number.isNaN(pageNum) || pageNum < 1) {
          return sys('usage: /skills browse [page]  (page must be a positive number)')
        }

        sys('fetching community skills (scans 6 sources, may take ~15s)…')

        rpc<SkillsBrowseResponse>('skills.manage', { action: 'browse', page: pageNum })
          .then(
            ctx.guarded<SkillsBrowseResponse>(r => {
              const items = r.items ?? []

              if (!items.length) {
                return sys(`no skills on page ${pageNum}${r.total ? ` (total ${r.total})` : ''}`)
              }

              const rows: [string, string][] = items.map(s => [
                s.trust ? `${s.name} · ${s.trust}` : s.name,
                String(s.description ?? '').slice(0, 160)
              ])

              const footer: string[] = []

              if (r.page && r.total_pages) {
                footer.push(`page ${r.page} of ${r.total_pages}`)
              }

              if (r.total) {
                footer.push(`${r.total} skills total`)
              }

              if (r.page && r.total_pages && r.page < r.total_pages) {
                footer.push(`/skills browse ${r.page + 1} for more`)
              }

              panel(`Browse Skills${pageNum > 1 ? ` — p${pageNum}` : ''}`, [
                { rows },
                ...(footer.length ? [{ text: footer.join(' · ') }] : [])
              ])
            })
          )
          .catch(ctx.guardedErr)

        return
      }

      runViaSlashWorker()
    }
  },

  {
    help: 'enable or disable tools (client-side history reset on change)',
    name: 'tools',
    run: (arg, ctx, cmd) => {
      const [subcommand, ...names] = arg.trim().split(/\s+/).filter(Boolean)

      if (subcommand !== 'disable' && subcommand !== 'enable') {
        ctx.gateway.gw
          .request<SlashExecResponse>('slash.exec', { command: cmd.slice(1), session_id: ctx.sid })
          .then(r => {
            if (ctx.stale()) {
              return
            }

            const body = r?.output || '/tools: no output'
            const text = r?.warning ? `warning: ${r.warning}\n${body}` : body
            const long = text.length > 180 || text.split('\n').filter(Boolean).length > 2

            long ? ctx.transcript.page(text, 'Tools') : ctx.transcript.sys(text)
          })
          .catch(ctx.guardedErr)

        return
      }

      if (!names.length) {
        ctx.transcript.sys(`usage: /tools ${subcommand} <name> [name ...]`)
        ctx.transcript.sys(`built-in toolset: /tools ${subcommand} web`)
        ctx.transcript.sys(`MCP tool: /tools ${subcommand} github:create_issue`)

        return
      }

      ctx.gateway
        .rpc<ToolsConfigureResponse>('tools.configure', { action: subcommand, names, session_id: ctx.sid })
        .then(
          ctx.guarded<ToolsConfigureResponse>(r => {
            if (r.info) {
              ctx.session.setSessionStartedAt(Date.now())
              ctx.session.resetVisibleHistory(r.info)
            }

            if (r.changed?.length) {
              ctx.transcript.sys(`${subcommand === 'disable' ? 'disabled' : 'enabled'}: ${r.changed.join(', ')}`)
            }

            if (r.unknown?.length) {
              ctx.transcript.sys(`unknown toolsets: ${r.unknown.join(', ')}`)
            }

            if (r.missing_servers?.length) {
              ctx.transcript.sys(`missing MCP servers: ${r.missing_servers.join(', ')}`)
            }

            if (r.reset) {
              ctx.transcript.sys('session reset. new tool configuration is active.')
            }
          })
        )
        .catch(ctx.guardedErr)
    }
  }
]
