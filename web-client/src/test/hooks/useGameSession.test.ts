import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useGameSession } from '../../hooks/useGameSession'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  getInstanceId: vi.fn(),
  setInstanceId: vi.fn(),
  processTurn: vi.fn(),
  sendInteraction: vi.fn(),
  getGameState: vi.fn(),
  createSave: vi.fn(),
  listSaves: vi.fn(),
}))

const defaultState = {
  bot_memory: { player: { hp: 100 } },
  client_messages: [
    { role: 'assistant' as const, content: 'Welcome, adventurer.' },
  ],
}

describe('useGameSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(client.getInstanceId).mockReturnValue('inst-1')
    vi.mocked(client.getGameState).mockResolvedValue(defaultState)
  })

  it('initializes with empty state', () => {
    const { result } = renderHook(() => useGameSession())
    expect(result.current.messages).toEqual([])
    expect(result.current.botMemory).toEqual({})
    expect(result.current.currentTurnId).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('sendTurn sets error when no instanceId', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('go north')
    })
    expect(result.current.error).toMatch(/No active game/i)
  })

  it('sendTurn optimistically adds user message and then adds assistant', async () => {
    vi.mocked(client.processTurn).mockResolvedValue({
      turn_id: 't-1',
      narrator_response: 'You enter the cave.',
      yare_delta: {},
    })
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('go north')
    })
    expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'go north' })
    expect(result.current.messages[1]).toMatchObject({ role: 'assistant', content: 'You enter the cave.' })
    expect(result.current.currentTurnId).toBe('t-1')
  })

  it('sendTurn updates botMemory from getGameState', async () => {
    vi.mocked(client.processTurn).mockResolvedValue({
      turn_id: 't-1',
      narrator_response: 'Good.',
      yare_delta: {},
    })
    vi.mocked(client.getGameState).mockResolvedValue({
      bot_memory: { player: { hp: 50 } },
      client_messages: [],
    })
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('fight')
    })
    expect(result.current.botMemory).toEqual({ player: { hp: 50 } })
  })

  it('sendTurn removes optimistic message on error', async () => {
    vi.mocked(client.processTurn).mockRejectedValue(new Error('API error'))
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('go south')
    })
    expect(result.current.messages).toHaveLength(0)
    expect(result.current.error).toBe('API error')
  })

  it('clearError clears the error state', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('test')
    })
    expect(result.current.error).not.toBeNull()
    act(() => {
      result.current.clearError()
    })
    expect(result.current.error).toBeNull()
  })

  it('resetSession with instanceId loads state from API', async () => {
    vi.mocked(client.getGameState).mockResolvedValue({
      bot_memory: { player: { hp: 42 } },
      client_messages: [
        { role: 'user', content: 'look around' },
        { role: 'assistant', content: 'You see a door.' },
      ],
      current_turn_id: 't-loaded',
      last_user_input: 'look around',
      last_parent_turn_id: 't-parent',
    })
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.resetSession('t-init')
    })
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.botMemory).toEqual({ player: { hp: 42 } })
    expect(result.current.currentTurnId).toBe('t-loaded')
    vi.mocked(client.processTurn).mockResolvedValueOnce({
      turn_id: 't-retry',
      narrator_response: 'Retry response.',
      yare_delta: {},
    })
    await act(async () => {
      await result.current.retryLast()
    })
    expect(client.processTurn).toHaveBeenCalledWith('inst-1', {
      parent_turn_id: 't-parent',
      user_input: 'look around',
    })
  })

  it('resetSession without instanceId clears state', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    // First put some data in
    await act(async () => {
      await result.current.resetSession()
    })
    expect(result.current.messages).toEqual([])
    expect(result.current.currentTurnId).toBeNull()
  })

  it('saveCheckpoint calls createSave and refreshes saves', async () => {
    vi.mocked(client.createSave).mockResolvedValue({ save_id: 's-1', created_at: '2026-01-01' })
    vi.mocked(client.listSaves).mockResolvedValue([
      { id: 's-1', instance_id: 'inst-1', turn_log_id: 't-1', label: 'cp1', created_at: '2026-01-01' },
    ])
    // Set currentTurnId first
    vi.mocked(client.processTurn).mockResolvedValue({ turn_id: 't-1', narrator_response: 'ok', yare_delta: {} })
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('test')
    })
    await act(async () => {
      await result.current.saveCheckpoint('My save')
    })
    expect(client.createSave).toHaveBeenCalledWith('inst-1', { turn_log_id: 't-1', label: 'My save' })
    expect(result.current.saves).toHaveLength(1)
  })

  it('loadCheckpoint restores messages and botMemory', async () => {
    vi.mocked(client.getGameState).mockResolvedValue({
      bot_memory: { player: { hp: 30 } },
      client_messages: [
        { role: 'user', content: 'I arrived here.' },
        { role: 'assistant', content: 'You are at the checkpoint.' },
      ],
    })
    const { result } = renderHook(() => useGameSession())
    const save = { id: 's-1', instance_id: 'inst-1', turn_log_id: 'old-turn', label: 'cp', created_at: '2026-01-01' }
    await act(async () => {
      await result.current.loadCheckpoint(save)
    })
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.botMemory).toEqual({ player: { hp: 30 } })
    expect(result.current.currentTurnId).toBe('old-turn')
  })

  it('loadCheckpoint does nothing without an instanceId', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.loadCheckpoint({
        id: 's-1',
        instance_id: 'inst-1',
        turn_log_id: 'old-turn',
        label: 'cp',
        created_at: '2026-01-01',
      })
    })
    expect(client.getGameState).not.toHaveBeenCalled()
  })

  it('retryLast does nothing if no previous input', async () => {
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.retryLast()
    })
    expect(client.processTurn).not.toHaveBeenCalled()
  })

  it('retryLast replaces last assistant message', async () => {
    vi.mocked(client.processTurn)
      .mockResolvedValueOnce({ turn_id: 't-1', narrator_response: 'First response.', yare_delta: {} })
      .mockResolvedValueOnce({ turn_id: 't-2', narrator_response: 'Retried response.', yare_delta: {} })
    const { result } = renderHook(() => useGameSession())
    // First turn
    await act(async () => { await result.current.sendTurn('fight') })
    // Retry
    await act(async () => { await result.current.retryLast() })
    const lastMsg = result.current.messages[result.current.messages.length - 1]
    expect(lastMsg).toMatchObject({ role: 'assistant', content: 'Retried response.' })
  })

  it('retryLast does nothing if no instanceId', async () => {
    vi.mocked(client.processTurn).mockResolvedValueOnce({ turn_id: 't-1', narrator_response: 'ok', yare_delta: {} })
    const { result } = renderHook(() => useGameSession())
    await act(async () => { await result.current.sendTurn('fight') })
    // Remove instanceId
    vi.mocked(client.getInstanceId).mockReturnValue('')
    await act(async () => { await result.current.retryLast() })
    expect(client.processTurn).toHaveBeenCalledTimes(1) // not called again
  })

  it('saveCheckpoint sets error when no currentTurnId', async () => {
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.saveCheckpoint('label')
    })
    expect(result.current.error).toMatch(/No active turn/i)
  })

  it('loadCheckpoint sets error when getGameState fails', async () => {
    vi.mocked(client.getGameState).mockRejectedValue(new Error('Load failed'))
    const { result } = renderHook(() => useGameSession())
    const save = { id: 's-1', instance_id: 'inst-1', turn_log_id: 'old-turn', label: 'cp', created_at: '2026-01-01' }
    await act(async () => {
      await result.current.loadCheckpoint(save)
    })
    expect(result.current.error).toBe('Load failed')
  })

  it('refreshSaves updates saves list', async () => {
    const saves = [{ id: 's-1', instance_id: 'inst-1', turn_log_id: 't-1', label: 'cp', created_at: '2026-01-01' }]
    vi.mocked(client.listSaves).mockResolvedValue(saves)
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.refreshSaves()
    })
    expect(result.current.saves).toHaveLength(1)
  })

  it('refreshSaves does nothing without an instanceId', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.refreshSaves()
    })
    expect(client.listSaves).not.toHaveBeenCalled()
  })

  it('resetSession sets error when getGameState fails', async () => {
    vi.mocked(client.getGameState).mockRejectedValue(new Error('Reset failed'))
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.resetSession('t-1')
    })
    expect(result.current.error).toBe('Reset failed')
  })

  it('clearSession resets all state and instance ID', async () => {
    // Set up some state first
    vi.mocked(client.getInstanceId).mockReturnValueOnce('inst-1')
    vi.mocked(client.getGameState).mockResolvedValueOnce({
      bot_memory: { hp: 100 },
      client_messages: [{ role: 'user', content: 'Test' }],
    })
    const { result } = renderHook(() => useGameSession())
    
    // Load a session
    await act(async () => {
      await result.current.resetSession('t-1')
    })
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.botMemory).toEqual({ hp: 100 })
    
    // Clear the session
    await act(async () => {
      result.current.clearSession()
    })
    
    expect(result.current.messages).toHaveLength(0)
    expect(result.current.botMemory).toEqual({})
    expect(result.current.currentTurnId).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.saves).toHaveLength(0)
    expect(client.setInstanceId).toHaveBeenCalledWith('')
  })

  it('initializes with null pendingInteraction', () => {
    const { result } = renderHook(() => useGameSession())
    expect(result.current.pendingInteraction).toBeNull()
  })

  it('sendTurn extracts _pending_interaction from bot_memory', async () => {
    const pendingInteraction = {
      interaction_type: 'minigame',
      minigame_id: 'lights_out',
      resolver_event: 'resolve_hack',
      config: { difficulty: { grid_size: 4 }, assets: {}, narrative_hooks: {} },
    }
    vi.mocked(client.processTurn).mockResolvedValue({
      turn_id: 't-1',
      narrator_response: 'Hack terminal triggered.',
      yare_delta: {},
    })
    vi.mocked(client.getGameState).mockResolvedValue({
      bot_memory: { _pending_interaction: pendingInteraction },
      client_messages: [],
    })
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('hack the terminal')
    })
    expect(result.current.pendingInteraction).toEqual(pendingInteraction)
  })

  it('sendInteraction calls apiSendInteraction and clears pendingInteraction', async () => {
    // Set up pending interaction via sendTurn
    const pendingInteraction = {
      interaction_type: 'minigame',
      minigame_id: 'lights_out',
      resolver_event: 'resolve_hack',
      config: { difficulty: {}, assets: {}, narrative_hooks: {} },
    }
    vi.mocked(client.processTurn).mockResolvedValue({
      turn_id: 't-1',
      narrator_response: 'Puzzle triggered.',
      yare_delta: {},
    })
    vi.mocked(client.getGameState)
      .mockResolvedValueOnce({
        bot_memory: { _pending_interaction: pendingInteraction },
        client_messages: [],
      })
      .mockResolvedValueOnce({
        // After resolution, _pending_interaction is cleared
        bot_memory: { door_unlocked: true },
        client_messages: [],
      })
    vi.mocked(client.sendInteraction).mockResolvedValue({
      turn_id: 't-2',
      narrator_response: 'You cracked it.',
      yare_delta: {},
    })

    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendTurn('hack the terminal')
    })
    expect(result.current.pendingInteraction).not.toBeNull()

    const interactionPayload = {
      interaction_type: 'minigame' as const,
      minigame_id: 'lights_out',
      status: 'completed' as const,
      metrics: { moves_made: 5 },
      minigame_specific_data: { grid_remaining: 0 },
    }
    await act(async () => {
      await result.current.sendInteraction(interactionPayload)
    })
    expect(client.sendInteraction).toHaveBeenCalledWith('inst-1', interactionPayload, 't-1')
    expect(result.current.pendingInteraction).toBeNull()
    expect(result.current.messages.at(-1)).toMatchObject({ role: 'assistant', content: 'You cracked it.' })
  })

  it('sendInteraction sets error when no instanceId', async () => {
    vi.mocked(client.getInstanceId).mockReturnValue('')
    const { result } = renderHook(() => useGameSession())
    await act(async () => {
      await result.current.sendInteraction({
        interaction_type: 'minigame',
        minigame_id: 'lights_out',
        status: 'completed',
        metrics: {},
        minigame_specific_data: {},
      })
    })
    expect(result.current.error).toMatch(/No active game/i)
  })
})
