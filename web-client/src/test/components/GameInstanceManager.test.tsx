import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GameInstanceManager from '../../components/GameInstanceManager'
import * as client from '../../api/client'
import type { GameInstanceResponse } from '../../types'

vi.mock('../../api/client', () => ({
  listInstances: vi.fn(),
  deleteInstance: vi.fn(),
  setInstanceId: vi.fn(),
}))

const mockInstances: GameInstanceResponse[] = [
  {
    id: 'inst-1',
    user_id: 'user-1',
    persona_id: 'persona-1',
    version_id: 'version-1',
    status: 'active',
    created_at: '2026-01-01T10:00:00Z',
    last_played_at: '2026-01-02T10:00:00Z',
  },
]

describe('GameInstanceManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    vi.mocked(client.listInstances).mockReturnValue(new Promise(() => {}))
    render(<GameInstanceManager />)
    expect(screen.getByText('Loading active games...')).toBeInTheDocument()
  })

  it('shows empty state when no instances', async () => {
    vi.mocked(client.listInstances).mockResolvedValue([])
    render(<GameInstanceManager />)
    await waitFor(() => expect(screen.getByText(/No active games/i)).toBeInTheDocument())
  })

  it('renders instance cards when instances are loaded', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    render(<GameInstanceManager />)
    await waitFor(() => expect(screen.getByText('Game Instance')).toBeInTheDocument())
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('shows error message when listInstances fails', async () => {
    vi.mocked(client.listInstances).mockRejectedValue(new Error('Network error'))
    render(<GameInstanceManager />)
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument())
  })

  it('calls setInstanceId and dispatches event on Resume', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    render(<GameInstanceManager />)
    await waitFor(() => screen.getByRole('button', { name: /resume/i }))
    await userEvent.click(screen.getByRole('button', { name: /resume/i }))
    expect(client.setInstanceId).toHaveBeenCalledWith('inst-1')
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: 'mnesos-play-instance' }))
  })

  it('refreshes on Refresh button click', async () => {
    vi.mocked(client.listInstances).mockResolvedValue([])
    render(<GameInstanceManager />)
    await waitFor(() => screen.getByRole('button', { name: /refresh/i }))
    await userEvent.click(screen.getByRole('button', { name: /refresh/i }))
    expect(client.listInstances).toHaveBeenCalledTimes(2)
  })

  it('dismisses error banner on X click', async () => {
    vi.mocked(client.listInstances).mockRejectedValue(new Error('Oops'))
    render(<GameInstanceManager />)
    await waitFor(() => screen.getByText('Oops'))
    await userEvent.click(screen.getByRole('button', { name: '✕' }))
    expect(screen.queryByText('Oops')).not.toBeInTheDocument()
  })
})
