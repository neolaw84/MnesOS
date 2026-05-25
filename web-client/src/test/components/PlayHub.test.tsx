import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PlayHub from '../../components/PlayHub'
import * as client from '../../api/client'
import type { GameInstanceResponse } from '../../types'

vi.mock('../../api/client', () => ({
  listInstances: vi.fn(),
  deleteInstance: vi.fn(),
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
  {
    id: 'inst-2',
    user_id: 'user-1',
    persona_id: 'persona-1',
    version_id: 'version-1',
    status: 'active',
    created_at: '2026-02-01T10:00:00Z',
  },
]

describe('PlayHub', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    vi.mocked(client.listInstances).mockReturnValue(new Promise(() => {}))
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('always renders the Start New Game card', async () => {
    vi.mocked(client.listInstances).mockResolvedValue([])
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Start New Game')).toBeInTheDocument())
  })

  it('calls onStartNewGame when new game card is clicked', async () => {
    const onStartNewGame = vi.fn()
    vi.mocked(client.listInstances).mockResolvedValue([])
    const user = userEvent.setup()
    render(<PlayHub onStartNewGame={onStartNewGame} onPlayInstance={vi.fn()} />)
    await waitFor(() => screen.getByText('Start New Game'))
    await user.click(screen.getByText('Start New Game'))
    expect(onStartNewGame).toHaveBeenCalledOnce()
  })

  it('renders instance cards when instances are loaded', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => expect(screen.getAllByText('▶ Resume')).toHaveLength(2))
    expect(screen.getAllByText('active')).toHaveLength(2)
  })

  it('shows last played date when present', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => screen.getAllByText('▶ Resume'))
    // inst-1 has last_played_at, inst-2 does not — both should render without error
    expect(screen.getAllByText(/Played/)).toHaveLength(1)
  })

  it('calls onPlayInstance with instance details on Resume', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    const user = userEvent.setup()
    const onPlayInstance = vi.fn()
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={onPlayInstance} />)
    await waitFor(() => screen.getAllByText('▶ Resume'))
    await user.click(screen.getAllByText('▶ Resume')[0])
    expect(onPlayInstance).toHaveBeenCalledWith({ instance_id: 'inst-1', turn_id: null })
  })

  it('removes instance from list on Delete confirm', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    vi.mocked(client.deleteInstance).mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => screen.getAllByText('Delete'))
    await user.click(screen.getAllByText('Delete')[0])
    await waitFor(() => expect(client.deleteInstance).toHaveBeenCalledWith('inst-1'))
    expect(screen.getAllByText('▶ Resume')).toHaveLength(1)
  })

  it('does not delete when confirm is cancelled', async () => {
    vi.mocked(client.listInstances).mockResolvedValue(mockInstances)
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const user = userEvent.setup()
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => screen.getAllByText('Delete'))
    await user.click(screen.getAllByText('Delete')[0])
    expect(client.deleteInstance).not.toHaveBeenCalled()
  })

  it('shows error banner when listInstances fails', async () => {
    vi.mocked(client.listInstances).mockRejectedValue(new Error('Network error'))
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument())
  })

  it('dismisses error banner on close click', async () => {
    vi.mocked(client.listInstances).mockRejectedValue(new Error('Network error'))
    const user = userEvent.setup()
    render(<PlayHub onStartNewGame={vi.fn()} onPlayInstance={vi.fn()} />)
    await waitFor(() => screen.getByText('Network error'))
    await user.click(screen.getByText('✕'))
    expect(screen.queryByText('Network error')).not.toBeInTheDocument()
  })
})
