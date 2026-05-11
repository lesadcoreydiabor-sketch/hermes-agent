import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createSlashHandler } from '../app/createSlashHandler.js'
import { getOverlayState, resetOverlayState } from '../app/overlayStore.js'
import { getUiState, patchUiState, resetUiState } from '../app/uiStore.js'
import { TUI_SESSION_MODEL_FLAG } from '../domain/slash.js'

describe('createSlashHandler', () => {
  beforeEach(() => {
    resetOverlayState()
    resetUiState()
  })

  it('opens the resume picker locally', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/resume')).toBe(true)
    expect(getOverlayState().picker).toBe(true)
  })

  it('handles /redraw locally without slash worker fallback', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/redraw')).toBe(true)
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('ui redrawn')
  })

  it('exits locally for /quit', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/quit')).toBe(true)
    expect(ctx.session.die).toHaveBeenCalledTimes(1)
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('routes /status to live session.status instead of slash worker', async () => {
    patchUiState({ sid: 'sid-abc' })
    const rpc = vi.fn(() => Promise.resolve({ output: 'Hermes TUI Status' }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/status')).toBe(true)
    expect(rpc).toHaveBeenCalledWith('session.status', { session_id: 'sid-abc' })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.page).toHaveBeenCalledWith('Hermes TUI Status', 'Status')
    })
  })

  it('keeps typed /model switches session-scoped by default', async () => {
    patchUiState({ sid: 'sid-abc' })

    const ctx = buildCtx({
      gateway: {
        ...buildGateway(),
        rpc: vi.fn(() => Promise.resolve({ value: 'x-model' }))
      }
    })

    expect(createSlashHandler(ctx)('/model x-model')).toBe(true)
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'model',
      session_id: 'sid-abc',
      value: 'x-model'
    })
  })

  it('honors TUI picker session scope without adding --global', async () => {
    patchUiState({ sid: 'sid-abc' })

    const ctx = buildCtx({
      gateway: {
        ...buildGateway(),
        rpc: vi.fn(() => Promise.resolve({ value: 'anthropic/claude-sonnet-4.6' }))
      }
    })

    expect(
      createSlashHandler(ctx)(`/model anthropic/claude-sonnet-4.6 --provider openrouter ${TUI_SESSION_MODEL_FLAG}`)
    ).toBe(true)
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'model',
      session_id: 'sid-abc',
      value: 'anthropic/claude-sonnet-4.6 --provider openrouter'
    })
  })

  it('does not duplicate --global for explicit persistent model switches', () => {
    patchUiState({ sid: 'sid-abc' })
    const ctx = buildCtx()

    createSlashHandler(ctx)('/model x-model --global')
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'model',
      session_id: 'sid-abc',
      value: 'x-model --global'
    })
  })

  it('applies /reasoning hide to the thinking section immediately', async () => {
    patchUiState({ sections: { thinking: 'expanded' }, showReasoning: true, sid: 'sid-abc' })
    const ctx = buildCtx({
      gateway: {
        ...buildGateway(),
        rpc: vi.fn(() => Promise.resolve({ value: 'hide' }))
      }
    })

    expect(createSlashHandler(ctx)('/reasoning hide')).toBe(true)

    await vi.waitFor(() => {
      expect(getUiState().showReasoning).toBe(false)
      expect(getUiState().sections.thinking).toBe('hidden')
    })
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'reasoning',
      session_id: 'sid-abc',
      value: 'hide'
    })
  })

  it('applies /reasoning show to the thinking section immediately', async () => {
    patchUiState({ sections: { thinking: 'hidden' }, showReasoning: false, sid: 'sid-abc' })
    const ctx = buildCtx({
      gateway: {
        ...buildGateway(),
        rpc: vi.fn(() => Promise.resolve({ value: 'show' }))
      }
    })

    expect(createSlashHandler(ctx)('/reasoning show')).toBe(true)

    await vi.waitFor(() => {
      expect(getUiState().showReasoning).toBe(true)
      expect(getUiState().sections.thinking).toBe('expanded')
    })
  })

  it('opens the skills hub locally for bare /skills', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/skills')).toBe(true)
    expect(getOverlayState().skillsHub).toBe(true)
    expect(ctx.gateway.rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('routes /skills install <name> to skills.manage without opening overlay', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/skills install foo')).toBe(true)
    expect(getOverlayState().skillsHub).toBe(false)
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('skills.manage', {
      action: 'install',
      query: 'foo'
    })
  })

  it('routes /skills inspect <name> to skills.manage', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/skills inspect my-skill')
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('skills.manage', {
      action: 'inspect',
      query: 'my-skill'
    })
  })

  it('routes /skills search <query> to skills.manage', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/skills search vibe')
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('skills.manage', {
      action: 'search',
      query: 'vibe'
    })
  })

  it('routes /skills browse [page] to skills.manage with a numeric page', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/skills browse 3')
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('skills.manage', {
      action: 'browse',
      page: 3
    })
  })

  it('delegates non-native /skills subcommands to slash.exec', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/skills check')
    expect(ctx.gateway.rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).toHaveBeenCalledWith('slash.exec', {
      command: 'skills check',
      session_id: null
    })
  })

  it('passes /new <title> through to the session lifecycle', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/new sprint planning')
    getOverlayState().confirm?.onConfirm()

    expect(ctx.session.newSession).toHaveBeenCalledWith('new session started', 'sprint planning')
    expect(ctx.gateway.rpc).not.toHaveBeenCalled()
  })

  it('reloads skills in the live gateway and refreshes the catalog', async () => {
    const rpc = vi.fn((method: string) => {
      if (method === 'skills.reload') {
        return Promise.resolve({ output: '42 skill(s) available' })
      }
      if (method === 'commands.catalog') {
        return Promise.resolve({ canon: { '/new-skill': '/new-skill' }, pairs: [['/new-skill', 'demo']] })
      }
      return Promise.resolve({})
    })
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    createSlashHandler(ctx)('/reload-skills')

    expect(rpc).toHaveBeenCalledWith('skills.reload', {})
    await vi.waitFor(() => {
      expect(ctx.transcript.page).toHaveBeenCalledWith('42 skill(s) available', 'Reload Skills')
      expect(ctx.local.setCatalog).toHaveBeenCalledWith(
        expect.objectContaining({ canon: { '/new-skill': '/new-skill' }, pairs: [['/new-skill', 'demo']] })
      )
    })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  // Regressions from Copilot review on #19835: /voice output + frontend
  // binding state must both track the gateway's fresh ``record_key`` on
  // every response, or a config edit shows the new shortcut in text
  // while push-to-talk still fires the old one until the next mtime
  // poll (~5s).
  it('/voice status renders the gateway record_key and pushes it into frontend state', async () => {
    const rpc = vi.fn(() => Promise.resolve({ enabled: true, record_key: 'ctrl+space', tts: false }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/voice status')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('  Record key: Ctrl+Space')
    })
    expect(ctx.voice.setVoiceRecordKey).toHaveBeenCalledWith(
      expect.objectContaining({ ch: 'space', mod: 'ctrl', named: 'space' })
    )
  })

  it('/voice on renders the configured binding for the start/stop hint', async () => {
    const rpc = vi.fn(() => Promise.resolve({ enabled: true, record_key: 'alt+r', tts: false }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/voice on')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('Voice mode enabled')
      expect(ctx.transcript.sys).toHaveBeenCalledWith('  Alt+R to start/stop recording')
    })
    expect(ctx.voice.setVoiceRecordKey).toHaveBeenCalledWith(expect.objectContaining({ ch: 'r', mod: 'alt' }))
  })

  it('/voice falls back to Ctrl+B when the gateway response omits record_key', async () => {
    const rpc = vi.fn(() => Promise.resolve({ enabled: false, tts: false }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/voice status')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('  Record key: Ctrl+B')
    })
  })

  // Round-2 Copilot review on #19835: a response missing ``record_key``
  // (e.g. the old tts branch, or any future branch that forgets to
  // include it) MUST NOT clobber the user's cached binding back to
  // Ctrl+B. The label still renders the default for display; the
  // frontend state keeps whatever was last authoritatively set.
  it('/voice tts without record_key does not clobber cached frontend binding', async () => {
    const rpc = vi.fn(() => Promise.resolve({ enabled: true, tts: true }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/voice tts')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('Voice TTS enabled.')
    })
    expect(ctx.voice.setVoiceRecordKey).not.toHaveBeenCalled()
  })

  it('cycles details mode and persists it', async () => {
    const ctx = buildCtx()

    expect(getUiState().detailsMode).toBe('collapsed')
    expect(createSlashHandler(ctx)('/details toggle')).toBe(true)
    expect(getUiState().detailsMode).toBe('expanded')
    expect(getUiState().detailsModeCommandOverride).toBe(true)
    expect(getUiState().sections).toEqual({
      thinking: 'expanded',
      tools: 'expanded',
      subagents: 'expanded',
      activity: 'expanded'
    })
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'details_mode',
      value: 'expanded'
    })
    expect(ctx.transcript.sys).toHaveBeenCalledWith('details: expanded')
  })

  it('sets a per-section override and persists it under details_mode.<section>', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/details activity hidden')).toBe(true)
    expect(getUiState().sections.activity).toBe('hidden')
    expect(ctx.gateway.rpc).toHaveBeenCalledWith('config.set', {
      key: 'details_mode.activity',
      value: 'hidden'
    })
    expect(ctx.transcript.sys).toHaveBeenCalledWith('details activity: hidden')
  })

  it('clears a per-section override on /details <section> reset', () => {
    const ctx = buildCtx()
    createSlashHandler(ctx)('/details tools expanded')
    expect(getUiState().sections.tools).toBe('expanded')

    createSlashHandler(ctx)('/details tools reset')
    expect(getUiState().sections.tools).toBeUndefined()
    expect(ctx.gateway.rpc).toHaveBeenLastCalledWith('config.set', {
      key: 'details_mode.tools',
      value: ''
    })
    expect(ctx.transcript.sys).toHaveBeenCalledWith('details tools: reset')
  })

  it('rejects unknown section modes with a usage hint', () => {
    const ctx = buildCtx()
    createSlashHandler(ctx)('/details tools blink')
    expect(getUiState().sections.tools).toBeUndefined()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /details <section> [hidden|collapsed|expanded|reset]')
  })

  it('shows tool enable usage when names are missing', () => {
    const ctx = buildCtx()

    expect(createSlashHandler(ctx)('/tools enable')).toBe(true)
    expect(ctx.transcript.sys).toHaveBeenNthCalledWith(1, 'usage: /tools enable <name> [name ...]')
    expect(ctx.transcript.sys).toHaveBeenNthCalledWith(2, 'built-in toolset: /tools enable web')
    expect(ctx.transcript.sys).toHaveBeenNthCalledWith(3, 'MCP tool: /tools enable github:create_issue')
  })

  it.each([
    ['/browser status', 'browser.manage', { action: 'status', session_id: null }],
    ['/browser connect', 'browser.manage', { action: 'connect', session_id: null, url: 'http://127.0.0.1:9222' }],
    ['/inspector', 'run_inspector.status', { port: 9119 }],
    ['/inspector-attention', 'run_inspector.status', { port: 9119 }],
    ['/inspector-desktop', 'run_inspector.status', { port: 9119 }],
    ['/inspector-events', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events active', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events attention', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events cancelled', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events completed', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events failed', 'run_inspector.events', { limit: 12 }],
    ['/inspector-events terminal', 'run_inspector.events', { limit: 12 }],
    ['/inspector-health', 'run_inspector.status', { port: 9119 }],
    ['/inspector-memory', 'run_inspector.memory_workbench', { limit: 12 }],
    ['/inspector-snapshot', 'run_inspector.status', { port: 9119 }],
    ['/run-inspector-attention 9222', 'run_inspector.status', { port: 9222 }],
    ['/run-inspector-desktop 9222', 'run_inspector.status', { port: 9222 }],
    ['/run-inspector-health 9222', 'run_inspector.status', { port: 9222 }],
    ['/run-inspector-snapshot 9222', 'run_inspector.status', { port: 9222 }],
    ['/run-inspector-events 7', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 active', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 attention', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 cancelled', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 completed', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 failed', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-events 7 terminal', 'run_inspector.events', { limit: 7 }],
    ['/run-inspector-memory 7', 'run_inspector.memory_workbench', { limit: 7 }],
    ['/run-inspector 9222', 'run_inspector.status', { port: 9222 }],
    ['/reload-mcp', 'reload.mcp', { session_id: null }],
    ['/reload', 'reload.env', {}],
    ['/stop', 'process.stop', {}],
    ['/fast status', 'config.get', { key: 'fast', session_id: null }],
    ['/busy status', 'config.get', { key: 'busy' }],
    ['/indicator', 'config.get', { key: 'indicator' }]
  ])('routes %s through native RPC (no slash worker)', (command, method, params) => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)(command)).toBe(true)
    expect(rpc).toHaveBeenCalledWith(method, params)
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('renders browser connect progress messages from the gateway', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        connected: false,
        messages: [
          "Chrome isn't running with remote debugging — attempting to launch...",
          'Browser not connected — start Chrome with remote debugging and retry /browser connect'
        ],
        url: 'http://127.0.0.1:9222'
      })
    )

    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/browser connect')).toBe(true)
    expect(ctx.transcript.sys).toHaveBeenCalledWith('checking Chrome remote debugging at http://127.0.0.1:9222...')

    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith(
        "Chrome isn't running with remote debugging — attempting to launch..."
      )
      expect(ctx.transcript.sys).toHaveBeenCalledWith(
        'Browser not connected — start Chrome with remote debugging and retry /browser connect'
      )
      expect(ctx.transcript.sys).not.toHaveBeenCalledWith('browser connect failed')
    })
  })

  it('/inspector renders read-only desktop status without slash worker fallback', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        ok: true,
        snapshot: {
          active_tool: {
            args_summary: { command: 'status' },
            name: 'terminal',
            status: 'running'
          },
          degraded_reason: 'mcp_degraded',
          mcp_health: [
            { name: 'gitnexus', status: 'connected' },
            { last_error_class: 'TimeoutError', name: 'slow-mcp', status: 'degraded' }
          ],
          privacy_flags: ['safe', 'redacted', 'local_only'],
          run_id: 'run_abc',
          session_id: 'sid_123',
          source: 'gateway',
          status: 'waiting_approval',
          tool_health: [{ name: 'terminal', status: 'running' }]
        },
        attention: [
          {
            body: 'A HERMES run is waiting for approval. Open Run Inspector to review safe details.',
            kind: 'approval_waiting',
            route: '/run-inspector',
            severity: 'warning',
            title: 'Approval waiting'
          }
        ],
        desktop: {
          compatible_dashboard: true,
          health: 'ok',
          health_reason: 'ok',
          manual_url: 'http://127.0.0.1:9222/run-inspector',
          ok: true,
          pid: null,
          pid_status: 'none',
          port: 9222,
          record_present: false,
          reuse_command: 'hermes desktop --port 9222',
          stop_command: 'hermes dashboard --stop',
          url: 'http://127.0.0.1:9222/run-inspector'
        }
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector 9222')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.status', { port: 9222 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Run', 'waiting_approval / gateway'],
              ['Run ID', 'run_abc'],
              ['Session', 'sid_123'],
              ['Active tool', 'terminal (running) - {"command":"status"}'],
              ['MCP', '1/2 ok, 1 attention'],
              ['Degraded', 'mcp_degraded'],
              ['Privacy', 'safe, redacted, local_only']
            ]),
            title: 'Run Snapshot'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              [
                'Approval waiting (warning)',
                'A HERMES run is waiting for approval. Open Run Inspector to review safe details.\nroute=/run-inspector'
              ]
            ]),
            title: 'Attention'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Desktop', 'compatible dashboard'],
              ['Run Inspector', 'http://127.0.0.1:9222/run-inspector'],
              ['Reuse', 'hermes desktop --port 9222']
            ]),
            title: 'Desktop Shell'
          })
        ])
      )
    })
  })

  it('/inspector rejects invalid ports before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector nope')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector [port]')
  })

  it('/inspector-attention renders all safe attention signals without slash worker fallback', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        attention: [
          {
            body: 'Approval needs review',
            kind: 'approval_waiting',
            route: '/run-inspector',
            run_id: 'run_wait',
            session_id: 'sid_wait',
            severity: 'warning',
            title: 'Approval waiting'
          },
          {
            body: 'Run failed safely',
            kind: 'run_failed',
            route: '/run-inspector',
            run_id: 'run_failed',
            severity: 'critical',
            title: 'Run failed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-attention 9222')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.status', { port: 9222 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Attention',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Approval waiting (warning)', 'Approval needs review\nrun=run_wait / session=sid_wait / route=/run-inspector'],
              ['Run failed (critical)', 'Run failed safely\nrun=run_failed / route=/run-inspector']
            ]),
            title: 'Signals 2'
          })
        ])
      )
    })
  })

  it('/inspector-attention rejects invalid ports before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-attention nope')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector-attention [port]')
  })

  it('/inspector-snapshot renders read-only run snapshot without slash worker fallback', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        ok: true,
        snapshot: {
          active_tool: {
            name: 'shell',
            status: 'running',
            summary: 'pytest tests/runtime'
          },
          degraded_reason: 'tool_timeout',
          last_activity_at: '2026-05-11T04:10:00Z',
          mcp_health: [{ name: 'gitnexus', status: 'connected' }],
          privacy_flags: ['safe_summary'],
          recovery_hint: 'Review failed tool',
          run_id: 'run_snapshot',
          session_id: 'sid_snapshot',
          source: 'gateway',
          status: 'running',
          tool_health: [
            { name: 'shell', status: 'running' },
            { name: 'browser', status: 'unavailable' }
          ]
        }
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-snapshot 9222')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.status', { port: 9222 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Snapshot',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Run', 'running / gateway'],
              ['Run ID', 'run_snapshot'],
              ['Session', 'sid_snapshot'],
              ['Last activity', '2026-05-11T04:10:00Z'],
              ['Active tool', 'shell (running) - pytest tests/runtime'],
              ['Tools', '1/2 ok, 1 attention'],
              ['MCP', '1/1 ok'],
              ['Degraded', 'tool_timeout'],
              ['Recovery', 'Review failed tool'],
              ['Privacy', 'safe_summary']
            ]),
            title: 'Run Snapshot'
          }),
          expect.objectContaining({
            text: 'read-only snapshot summary; raw prompts, tool args, and secrets are not shown'
          })
        ])
      )
    })
  })

  it('/inspector-snapshot rejects invalid ports before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-snapshot nope')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector-snapshot [port]')
  })

  it('/inspector-desktop renders read-only desktop shell status without slash worker fallback', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        desktop: {
          compatible_dashboard: false,
          host: '127.0.0.1',
          health: 'attention',
          health_reason: 'pid_missing',
          manual_url: 'http://127.0.0.1:9222/run-inspector',
          ok: true,
          pid: 1234,
          pid_reason: 'process exited',
          pid_status: 'stale',
          port: 9222,
          record_present: true,
          reuse_command: 'hermes desktop --port 9222',
          route: '/run-inspector',
          runtime_record_cleared: true,
          started_at: '2026-05-11T04:00:00Z',
          stop_command: 'hermes dashboard --stop',
          url: 'http://127.0.0.1:9222/run-inspector'
        },
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-desktop 9222')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.status', { port: 9222 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Desktop',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Desktop', 'recorded (stale / attention)'],
              ['Source', 'stale desktop runtime record'],
              ['Run Inspector', 'http://127.0.0.1:9222/run-inspector'],
              ['Health', 'attention / pid_missing'],
              ['PID', '1234 (stale)'],
              ['PID reason', 'process exited'],
              ['Started', '2026-05-11T04:00:00Z'],
              ['Host', '127.0.0.1'],
              ['Route', '/run-inspector'],
              ['Record', 'cleared stale runtime record'],
              ['Reuse', 'hermes desktop --port 9222'],
              ['Stop guidance', 'hermes dashboard --stop']
            ]),
            title: 'Desktop Shell'
          }),
          expect.objectContaining({
            text: 'read-only desktop status; use hermes desktop to start, stop, or reuse the dashboard'
          })
        ])
      )
    })
  })

  it('/inspector-desktop rejects invalid ports before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-desktop nope')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector-desktop [port]')
  })

  it('/inspector-health renders tool and MCP health details without slash worker fallback', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        ok: true,
        snapshot: {
          mcp_health: [
            {
              affected_tools: ['search', 'context'],
              last_error_class: 'TimeoutError',
              name: 'gitnexus',
              status: 'degraded'
            }
          ],
          tool_health: [
            {
              name: 'terminal',
              reason: 'ready',
              status: 'available',
              toolset: 'local'
            }
          ]
        }
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-health 9222')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.status', { port: 9222 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Health',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['terminal (available)', 'toolset=local / reason=ready']
            ]),
            title: 'Tools'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['gitnexus (degraded)', 'error=TimeoutError / affected=search, context']
            ]),
            title: 'MCP'
          })
        ])
      )
    })
  })

  it('/inspector-health rejects invalid ports before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-health nope')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector-health [port]')
  })

  it('/inspector-events renders a read-only event timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 9,
            message: 'approval needed',
            run_id: 'run_event',
            session_id: 'sid_event',
            source: 'gateway_run',
            status: 'waiting',
            tool: 'shell',
            type: 'approval.request'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events 1')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 1 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '1'],
              ['Showing', '1'],
              ['Active', '0'],
              ['Attention', '1'],
              ['Approval', '1'],
              ['Cancelled', '0'],
              ['Completed', '0'],
              ['Failed', '0'],
              ['Latest', '#9 approval.request']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              [
                '#9 approval.request',
                'status=waiting / tool=shell / source=gateway_run / run=run_event / session=sid_event\napproval needed'
              ]
            ]),
            title: 'Recent 1'
          })
        ])
      )
    })
  })

  it('/inspector-events filters events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 10,
            message: 'tool running',
            source: 'dashboard_chat',
            status: 'running',
            tool: 'shell',
            type: 'tool.progress'
          },
          {
            id: 11,
            message: 'run failed safely',
            run_id: 'run_failed',
            source: 'gateway_run',
            status: 'failed',
            type: 'run.failed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events failed')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '2'],
              ['Showing', '1 failed'],
              ['Active', '1'],
              ['Attention', '1'],
              ['Approval', '0'],
              ['Cancelled', '0'],
              ['Completed', '0'],
              ['Failed', '1'],
              ['Latest', '#11 run.failed']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['#11 run.failed', 'status=failed / source=gateway_run / run=run_failed\nrun failed safely']
            ]),
            title: 'Recent 1/2 failed'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#10 tool.progress', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events filters active events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 50,
            message: 'run queued',
            run_id: 'run_queued',
            source: 'gateway_run',
            status: 'queued',
            type: 'run.started'
          },
          {
            id: 51,
            message: 'tool running',
            source: 'dashboard_chat',
            status: 'running',
            tool: 'shell',
            type: 'tool.progress'
          },
          {
            id: 52,
            message: 'run done',
            run_id: 'run_done',
            source: 'gateway_run',
            status: 'completed',
            type: 'run.completed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events active')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '3'],
              ['Showing', '2 active'],
              ['Active', '2'],
              ['Attention', '0'],
              ['Approval', '0'],
              ['Cancelled', '0'],
              ['Completed', '1'],
              ['Failed', '0'],
              ['Latest', '#52 run.completed']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['#50 run.started', 'status=queued / source=gateway_run / run=run_queued\nrun queued'],
              ['#51 tool.progress', 'status=running / tool=shell / source=dashboard_chat\ntool running']
            ]),
            title: 'Recent 2/3 active'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#52 run.completed', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events explains an empty filtered timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 55,
            message: 'run done',
            run_id: 'run_done',
            source: 'gateway_run',
            status: 'completed',
            type: 'run.completed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events active')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '1'],
              ['Showing', '0 active'],
              ['Active', '0'],
              ['Completed', '1'],
              ['Terminal', '1'],
              ['Latest', '#55 run.completed']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([['Events', 'no active events']]),
            title: 'Recent 0/1 active'
          })
        ])
      )
    })
  })

  it('/inspector-events filters attention events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 20,
            message: 'tool running',
            source: 'dashboard_chat',
            status: 'running',
            tool: 'shell',
            type: 'tool.progress'
          },
          {
            id: 21,
            message: 'approval needed',
            run_id: 'run_waiting',
            source: 'gateway_run',
            status: 'waiting',
            type: 'approval.request'
          },
          {
            id: 22,
            message: 'run failed safely',
            run_id: 'run_failed',
            source: 'gateway_run',
            status: 'failed',
            type: 'run.failed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events attention')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '3'],
              ['Showing', '2 attention'],
              ['Active', '1'],
              ['Attention', '2'],
              ['Approval', '1'],
              ['Cancelled', '0'],
              ['Completed', '0'],
              ['Failed', '1'],
              ['Latest', '#22 run.failed']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['#21 approval.request', 'status=waiting / source=gateway_run / run=run_waiting\napproval needed'],
              ['#22 run.failed', 'status=failed / source=gateway_run / run=run_failed\nrun failed safely']
            ]),
            title: 'Recent 2/3 attention'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#20 tool.progress', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events filters cancelled events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 30,
            message: 'run started',
            run_id: 'run_active',
            source: 'gateway_run',
            status: 'running',
            type: 'run.running'
          },
          {
            id: 31,
            message: 'run cancelled by operator',
            run_id: 'run_cancelled',
            session_id: 'sid_cancelled',
            source: 'gateway_run',
            status: 'cancelled',
            type: 'run.cancelled'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events cancelled')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '2'],
              ['Showing', '1 cancelled'],
              ['Active', '1'],
              ['Attention', '0'],
              ['Approval', '0'],
              ['Cancelled', '1'],
              ['Completed', '0'],
              ['Failed', '0'],
              ['Latest', '#31 run.cancelled']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              [
                '#31 run.cancelled',
                'status=cancelled / source=gateway_run / run=run_cancelled / session=sid_cancelled\nrun cancelled by operator'
              ]
            ]),
            title: 'Recent 1/2 cancelled'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#30 run.running', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events filters completed events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 40,
            message: 'run started',
            run_id: 'run_active',
            source: 'gateway_run',
            status: 'running',
            type: 'run.running'
          },
          {
            id: 41,
            message: 'run completed',
            run_id: 'run_completed',
            session_id: 'sid_completed',
            source: 'gateway_run',
            status: 'completed',
            type: 'run.completed'
          },
          {
            id: 42,
            message: 'tool completed',
            source: 'dashboard_chat',
            status: 'completed',
            tool: 'shell',
            type: 'tool.completed'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events completed')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '3'],
              ['Showing', '2 completed'],
              ['Active', '1'],
              ['Attention', '0'],
              ['Approval', '0'],
              ['Cancelled', '0'],
              ['Completed', '2'],
              ['Failed', '0'],
              ['Latest', '#42 tool.completed']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              [
                '#41 run.completed',
                'status=completed / source=gateway_run / run=run_completed / session=sid_completed\nrun completed'
              ],
              ['#42 tool.completed', 'status=completed / tool=shell / source=dashboard_chat\ntool completed']
            ]),
            title: 'Recent 2/3 completed'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#40 run.running', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events filters terminal events locally after fetching the bounded timeline', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        events: [
          {
            id: 60,
            message: 'run active',
            run_id: 'run_active',
            source: 'gateway_run',
            status: 'running',
            type: 'run.running'
          },
          {
            id: 61,
            message: 'run failed',
            run_id: 'run_failed',
            source: 'gateway_run',
            status: 'failed',
            type: 'run.failed'
          },
          {
            id: 62,
            message: 'run cancelled',
            run_id: 'run_cancelled',
            source: 'gateway_run',
            status: 'cancelled',
            type: 'run.cancelled'
          },
          {
            id: 63,
            message: 'tool completed',
            source: 'dashboard_chat',
            status: 'completed',
            tool: 'shell',
            type: 'tool.completed'
          },
          {
            id: 64,
            message: 'approval waiting',
            run_id: 'run_waiting',
            source: 'gateway_run',
            status: 'waiting',
            type: 'approval.request'
          }
        ],
        ok: true
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events terminal')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.events', { limit: 12 })
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Events',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Fetched', '5'],
              ['Showing', '3 terminal'],
              ['Active', '1'],
              ['Attention', '2'],
              ['Approval', '1'],
              ['Cancelled', '1'],
              ['Completed', '1'],
              ['Failed', '1'],
              ['Terminal', '3'],
              ['Latest', '#64 approval.request']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['#61 run.failed', 'status=failed / source=gateway_run / run=run_failed\nrun failed'],
              ['#62 run.cancelled', 'status=cancelled / source=gateway_run / run=run_cancelled\nrun cancelled'],
              ['#63 tool.completed', 'status=completed / tool=shell / source=dashboard_chat\ntool completed']
            ]),
            title: 'Recent 3/5 terminal'
          })
        ])
      )
    })
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#60 run.running', expect.any(String)]])
        })
      ])
    )
    expect(ctx.transcript.panel).not.toHaveBeenCalledWith(
      'Run Inspector Events',
      expect.arrayContaining([
        expect.objectContaining({
          rows: expect.arrayContaining([['#64 approval.request', expect.any(String)]])
        })
      ])
    )
  })

  it('/inspector-events rejects invalid limits before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-events 0')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith(
      'usage: /inspector-events [limit 1..100] [all|active|attention|approval|cancelled|completed|failed|terminal|gateway|run|tool]'
    )
  })

  it('/inspector-memory renders read-only multi-agent memory summaries', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        ok: true,
        workbench: {
          status: 'active',
          status_reason: '1 active child',
          privacy_class: 'redacted_summary',
          memory: {
            status: 'available',
            provider_count: 1,
            providers: [],
            registered_tools: ['safe-search'],
            degraded_reason: null,
            privacy_class: 'redacted_summary'
          },
          runtime_persistence: {
            status: 'disabled',
            enabled_count: 0,
            degraded_reason: null,
            privacy_class: 'redacted_summary'
          },
          agent_assignments: {
            summary: {
              total_count: 3,
              active_count: 1,
              completed_count: 1,
              failed_count: 0,
              blocked_count: 0,
              ready_task_ids: ['HMAMO-11'],
              dependency_waiting_task_ids: ['HMAMO-12'],
              blocked_task_ids: [],
              role_counts: { worker: 2 },
              status_counts: { running: 1 },
              conflicts: [],
              degraded_reason: null,
              privacy_class: 'redacted_summary'
            },
            parallel_plan: {
              status: 'ready',
              max_parallel_workers: 2,
              batches: [{ index: 1, task_ids: ['HMAMO-11'], roles: { worker: 1 }, privacy_class: 'redacted_summary' }],
              active_task_ids: ['HMAMO-10'],
              waiting_task_ids: ['HMAMO-12'],
              blocked_task_ids: [],
              conflict_task_ids: [],
              conflicts: [],
              degraded_reason: null,
              privacy_class: 'redacted_summary'
            },
            assignments: [
              {
                task_id: 'HMAMO-11',
                title: 'TUI memory workbench',
                role: 'worker',
                status: 'ready',
                dependencies: { task_ids: ['HMAMO-10'] },
                write_scope: {
                  files: ['redacted_file'],
                  directories: ['redacted_dir'],
                  shared_contracts: []
                },
                privacy_class: 'redacted_summary'
              }
            ],
            degraded_reason: null,
            privacy_class: 'redacted_summary'
          },
          degraded_reason: null
        }
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-memory 7')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.memory_workbench', { limit: 7 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Memory',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Workbench', 'active / 1 active child'],
              ['Assignments', '3 total / 1 active / 1 ready'],
              ['Plan', '1 planned / 1 batches / 2 max'],
              ['Waiting', '1 waiting / 0 blocked'],
              ['Conflicts', '0 scoped / 0 pairs'],
              ['Memory', 'available / 1 providers'],
              ['Persistence', 'disabled / 0 enabled'],
              ['Privacy', 'redacted_summary']
            ]),
            title: 'Summary'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['HMAMO-11', 'role=worker / status=ready / deps=1 / scope=1 files/1 dirs']
            ]),
            title: 'Assignments'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Batch 1', 'HMAMO-11'],
              ['Active', 'HMAMO-10'],
              ['Waiting', 'HMAMO-12'],
              ['Blocked', 'none'],
              ['Sequenced', 'none']
            ]),
            title: 'Parallel Plan'
          })
        ])
      )
    })
  })

  it('/inspector-memory renders degraded workbench state without mutating through slash worker', async () => {
    const rpc = vi.fn(() =>
      Promise.resolve({
        ok: false,
        workbench: {
          status: 'unavailable',
          status_reason: 'Workbench unavailable',
          degraded_reason: 'memory_workbench_unavailable:RuntimeError',
          privacy_class: 'redacted_summary',
          memory: {
            status: 'unavailable',
            provider_count: 0,
            providers: [],
            registered_tools: [],
            degraded_reason: 'memory_workbench_unavailable:RuntimeError',
            privacy_class: 'redacted_summary'
          },
          runtime_persistence: {
            status: 'disabled',
            enabled_count: 0,
            degraded_reason: null,
            privacy_class: 'redacted_summary'
          },
          agent_assignments: {
            summary: {
              total_count: 0,
              active_count: 0,
              completed_count: 0,
              failed_count: 0,
              blocked_count: 0,
              ready_task_ids: [],
              dependency_waiting_task_ids: [],
              blocked_task_ids: [],
              role_counts: {},
              status_counts: {},
              conflicts: [],
              degraded_reason: 'memory_workbench_unavailable:RuntimeError',
              privacy_class: 'redacted_summary'
            },
            parallel_plan: {
              status: 'unavailable',
              max_parallel_workers: 0,
              batches: [],
              active_task_ids: [],
              waiting_task_ids: [],
              blocked_task_ids: [],
              conflict_task_ids: [],
              conflicts: [],
              degraded_reason: 'memory_workbench_unavailable:RuntimeError',
              privacy_class: 'redacted_summary'
            },
            assignments: [],
            degraded_reason: 'memory_workbench_unavailable:RuntimeError',
            privacy_class: 'redacted_summary'
          }
        }
      })
    )
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-memory')).toBe(true)

    expect(rpc).toHaveBeenCalledWith('run_inspector.memory_workbench', { limit: 12 })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(
        'Run Inspector Memory',
        expect.arrayContaining([
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Workbench', 'unavailable / Workbench unavailable'],
              ['Degraded', 'memory_workbench_unavailable:RuntimeError']
            ]),
            title: 'Summary degraded'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([['Assignments', 'none']]),
            title: 'Assignments'
          }),
          expect.objectContaining({
            rows: expect.arrayContaining([
              ['Active', 'none'],
              ['Plan degraded', 'memory_workbench_unavailable:RuntimeError']
            ]),
            title: 'Parallel Plan'
          })
        ])
      )
    })
  })

  it('/inspector-memory rejects invalid limits before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/inspector-memory 0')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /inspector-memory [limit 1..100]')
  })

  it('routes /rollback through native RPC when a session is active', () => {
    patchUiState({ sid: 'sid-abc' })
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/rollback')).toBe(true)
    expect(rpc).toHaveBeenCalledWith('rollback.list', { session_id: 'sid-abc' })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('hot-swaps the live indicator when /indicator <style> succeeds', async () => {
    const rpc = vi.fn(() => Promise.resolve({ value: 'emoji' }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/indicator emoji')).toBe(true)
    expect(rpc).toHaveBeenCalledWith('config.set', { key: 'indicator', value: 'emoji' })
    await vi.waitFor(() => expect(getUiState().indicatorStyle).toBe('emoji'))
  })

  it('rejects unknown indicator styles before hitting the gateway', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    expect(createSlashHandler(ctx)('/indicator sparkle')).toBe(true)
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('usage: /indicator [ascii|emoji|kaomoji|unicode]')
  })

  it('drops stale slash.exec output after a newer slash', async () => {
    let resolveLate: (v: { output?: string }) => void
    let slashExecCalls = 0

    const ctx = buildCtx({
      gateway: {
        gw: {
          getLogTail: vi.fn(() => ''),
          request: vi.fn((method: string) => {
            if (method === 'slash.exec') {
              slashExecCalls += 1

              if (slashExecCalls === 1) {
                return new Promise<{ output?: string }>(res => {
                  resolveLate = res
                })
              }

              return Promise.resolve({ output: 'fresh' })
            }

            return Promise.resolve({})
          })
        },
        rpc: vi.fn(() => Promise.resolve({}))
      }
    })

    const h = createSlashHandler(ctx)
    expect(h('/slow')).toBe(true)
    expect(h('/later')).toBe(true)
    resolveLate!({ output: 'too late' })
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalled()
    })

    expect(ctx.transcript.sys).not.toHaveBeenCalledWith('too late')
  })

  it('dispatches command.dispatch with typed alias', async () => {
    const ctx = buildCtx({
      gateway: {
        gw: {
          getLogTail: vi.fn(() => ''),
          request: vi.fn((method: string) => {
            if (method === 'slash.exec') {
              return Promise.reject(new Error('no'))
            }

            if (method === 'command.dispatch') {
              return Promise.resolve({ type: 'alias', target: 'help' })
            }

            return Promise.resolve({})
          })
        },
        rpc: vi.fn(() => Promise.resolve({}))
      }
    })

    const h = createSlashHandler(ctx)
    expect(h('/zzz')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.panel).toHaveBeenCalledWith(expect.any(String), expect.any(Array))
    })
  })

  it('resolves unique local aliases through the catalog', () => {
    const ctx = buildCtx({
      local: {
        catalog: {
          canon: {
            '/h': '/help',
            '/help': '/help'
          }
        }
      }
    })

    expect(createSlashHandler(ctx)('/h')).toBe(true)
    expect(ctx.transcript.panel).toHaveBeenCalledWith(expect.any(String), expect.any(Array))
  })

  it('lets exact catalog commands win over longer prefix matches', async () => {
    const ctx = buildCtx({
      local: {
        catalog: {
          canon: {
            '/profile': '/profile',
            '/plugins': '/plugins'
          }
        }
      }
    })

    expect(createSlashHandler(ctx)('/profile')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.gateway.gw.request).toHaveBeenCalledWith('slash.exec', {
        command: 'profile',
        session_id: null
      })
    })
    expect(ctx.transcript.sys).not.toHaveBeenCalledWith(expect.stringContaining('ambiguous command'))
  })

  it('keeps ambiguous prefix handling when there is no exact catalog match', () => {
    const ctx = buildCtx({
      local: {
        catalog: {
          canon: {
            '/status': '/status',
            '/statusbar': '/statusbar'
          }
        }
      }
    })

    expect(createSlashHandler(ctx)('/stat')).toBe(true)
    expect(ctx.transcript.sys).toHaveBeenCalledWith('ambiguous command: /status, /statusbar')
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('falls through to command.dispatch for skill commands and sends the message', async () => {
    const skillMessage = 'Use this skill to do X.\n\n## Steps\n1. First step'

    const ctx = buildCtx({
      gateway: {
        gw: {
          getLogTail: vi.fn(() => ''),
          request: vi.fn((method: string) => {
            if (method === 'slash.exec') {
              return Promise.reject(new Error('skill command: use command.dispatch'))
            }

            if (method === 'command.dispatch') {
              return Promise.resolve({ type: 'skill', message: skillMessage, name: 'hermes-agent-dev' })
            }

            return Promise.resolve({})
          })
        },
        rpc: vi.fn(() => Promise.resolve({}))
      }
    })

    const h = createSlashHandler(ctx)
    expect(h('/hermes-agent-dev')).toBe(true)
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('⚡ loading skill: hermes-agent-dev')
    })
    expect(ctx.transcript.send).toHaveBeenCalledWith(skillMessage)
  })

  it('/history pages the current TUI transcript (user + assistant)', () => {
    const ctx = buildCtx({
      local: {
        ...buildLocal(),
        getHistoryItems: vi.fn(() => [
          { role: 'user', text: 'hello' },
          { role: 'system', text: 'ignore me' },
          { role: 'assistant', text: 'hi there' },
          { role: 'user', text: 'test' }
        ])
      }
    })

    createSlashHandler(ctx)('/history')
    expect(ctx.transcript.page).toHaveBeenCalledTimes(1)

    const [body, title] = ctx.transcript.page.mock.calls[0]!

    expect(title).toBe('History')
    expect(body).toContain('[You #1]')
    expect(body).toContain('hello')
    expect(body).toContain('[Hermes #2]')
    expect(body).toContain('hi there')
    expect(body).toContain('[You #3]')
    expect(body).not.toContain('ignore me')
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
  })

  it('/history reports empty state without paging', () => {
    const ctx = buildCtx()

    createSlashHandler(ctx)('/history')
    expect(ctx.transcript.page).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('no conversation yet')
  })

  it('/save forwards to session.save RPC and reports the returned file', async () => {
    patchUiState({ sid: 'sid-abc' })

    const rpc = vi.fn(() => Promise.resolve({ file: '/tmp/hermes_conversation_test.json' }))

    const ctx = buildCtx({
      gateway: { ...buildGateway(), rpc },
      local: {
        ...buildLocal(),
        getHistoryItems: vi.fn(() => [
          { role: 'system', text: 'intro' },
          { role: 'user', text: 'hello' },
          { role: 'assistant', text: 'hi there' }
        ])
      }
    })

    createSlashHandler(ctx)('/save')

    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(rpc).toHaveBeenCalledWith('session.save', { session_id: 'sid-abc' })

    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('conversation saved to: /tmp/hermes_conversation_test.json')
    })
  })

  it('/save reports empty state without calling the RPC or slash worker', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    createSlashHandler(ctx)('/save')

    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('no conversation yet')
  })

  it('/save without an active session tells the user instead of hitting the RPC', () => {
    // sid stays null (default) but there IS visible conversation
    const rpc = vi.fn(() => Promise.resolve({}))

    const ctx = buildCtx({
      gateway: { ...buildGateway(), rpc },
      local: {
        ...buildLocal(),
        getHistoryItems: vi.fn(() => [{ role: 'user', text: 'hello' }])
      }
    })

    createSlashHandler(ctx)('/save')

    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('no active session — nothing to save')
  })

  it('/rollback without an active session tells the user instead of hitting the RPC', () => {
    const rpc = vi.fn(() => Promise.resolve({}))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    createSlashHandler(ctx)('/rollback')

    expect(rpc).not.toHaveBeenCalled()
    expect(ctx.transcript.sys).toHaveBeenCalledWith('no active session — nothing to rollback')
  })

  it('/title <name> uses session.title RPC and bypasses slash.exec', async () => {
    patchUiState({ sid: 'sid-abc' })
    const rpc = vi.fn(() => Promise.resolve({ pending: false, title: 'my title' }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    createSlashHandler(ctx)('/title my title')

    expect(rpc).toHaveBeenCalledWith('session.title', { session_id: 'sid-abc', title: 'my title' })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('session title set: my title')
    })
  })

  it('/title with no args fetches and displays the current title', async () => {
    patchUiState({ sid: 'sid-abc' })
    const rpc = vi.fn(() => Promise.resolve({ title: 'demo title' }))
    const ctx = buildCtx({ gateway: { ...buildGateway(), rpc } })

    createSlashHandler(ctx)('/title')

    expect(rpc).toHaveBeenCalledWith('session.title', { session_id: 'sid-abc' })
    expect(ctx.gateway.gw.request).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(ctx.transcript.sys).toHaveBeenCalledWith('title: demo title')
    })
  })
})

const buildCtx = (overrides: Partial<Ctx> = {}): Ctx => ({
  ...overrides,
  slashFlightRef: overrides.slashFlightRef ?? { current: 0 },
  composer: { ...buildComposer(), ...overrides.composer },
  gateway: { ...buildGateway(), ...overrides.gateway },
  local: { ...buildLocal(), ...overrides.local },
  session: { ...buildSession(), ...overrides.session },
  transcript: { ...buildTranscript(), ...overrides.transcript },
  voice: { ...buildVoice(), ...overrides.voice }
})

const buildComposer = () => ({
  enqueue: vi.fn(),
  hasSelection: false,
  paste: vi.fn(),
  queueRef: { current: [] as string[] },
  selection: { copySelection: vi.fn(async () => '') },
  setInput: vi.fn()
})

const buildGateway = () => ({
  gw: {
    getLogTail: vi.fn(() => ''),
    request: vi.fn(() => Promise.resolve({}))
  },
  rpc: vi.fn(() => Promise.resolve({}))
})

const buildLocal = () => ({
  catalog: null,
  getHistoryItems: vi.fn(() => []),
  getLastUserMsg: vi.fn(() => ''),
  maybeWarn: vi.fn(),
  setCatalog: vi.fn()
})

const buildSession = () => ({
  closeSession: vi.fn(() => Promise.resolve(null)),
  die: vi.fn(),
  guardBusySessionSwitch: vi.fn(() => false),
  newSession: vi.fn(),
  resetVisibleHistory: vi.fn(),
  resumeById: vi.fn(),
  setSessionStartedAt: vi.fn()
})

const buildTranscript = () => ({
  page: vi.fn(),
  panel: vi.fn(),
  send: vi.fn(),
  setHistoryItems: vi.fn(),
  sys: vi.fn(),
  trimLastExchange: vi.fn(items => items)
})

const buildVoice = () => ({
  setVoiceEnabled: vi.fn(),
  setVoiceRecordKey: vi.fn()
})

interface Ctx {
  slashFlightRef: { current: number }
  composer: ReturnType<typeof buildComposer>
  gateway: ReturnType<typeof buildGateway>
  local: ReturnType<typeof buildLocal>
  session: ReturnType<typeof buildSession>
  transcript: ReturnType<typeof buildTranscript>
  voice: ReturnType<typeof buildVoice>
}
