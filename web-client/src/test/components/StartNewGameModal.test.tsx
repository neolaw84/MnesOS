import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StartNewGameModal from '../../components/StartNewGameModal'
import * as client from '../../api/client'
import type { Cartridge, CartridgeVersion, Persona } from '../../types'

vi.mock('../../api/client', () => ({
  listCartridges: vi.fn(),
  listCartridgeVersions: vi.fn(),
  listPersonas: vi.fn(),
  createGameInstance: vi.fn(),
  setInstanceId: vi.fn(),
}))

const mockCartridges: Cartridge[] = [
  { id: 'c-1', creator_id: 'u-1', title: 'Dark Fantasy', description: 'Dark world', genre: 'Fantasy', visibility: 'PUBLIC' },
]
const mockVersions: CartridgeVersion[] = [
  { id: 'v-1', cartridge_id: 'c-1', version_tag: '1.0.0', created_at: '2026-01-01T00:00:00Z' } as unknown as CartridgeVersion,
]
const mockPersonas: Persona[] = [
  { id: 'p-1', user_id: 'u-1', name: 'Hero', pronoun_sub: 'they', pronoun_obj: 'them', pronoun_poss: 'their', pronoun_poss_obj: 'theirs', appearance: '', background: '', personality: '' },
]

describe('StartNewGameModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when closed', () => {
    const { container } = render(
      <StartNewGameModal open={false} onClose={vi.fn()} onStart={vi.fn()} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows loading state while fetching data', () => {
    vi.mocked(client.listCartridges).mockReturnValue(new Promise(() => {}))
    vi.mocked(client.listPersonas).mockReturnValue(new Promise(() => {}))
    render(<StartNewGameModal open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders selects after data loads', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue(mockVersions)
    render(<StartNewGameModal open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Dark Fantasy')).toBeInTheDocument())
    expect(screen.getByText('Hero (they/them)')).toBeInTheDocument()
  })

  it('Start button is disabled when no version is available', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue([])
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue([])
    render(<StartNewGameModal open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    await waitFor(() => screen.getByRole('button', { name: /start game/i }))
    expect(screen.getByRole('button', { name: /start game/i })).toBeDisabled()
  })

  it('calls createGameInstance and onStart on success', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue(mockVersions)
    vi.mocked(client.createGameInstance).mockResolvedValue({ instance_id: 'new-inst', turn_id: 't-1' })
    const onStart = vi.fn()
    const onClose = vi.fn()
    render(<StartNewGameModal open={true} onClose={onClose} onStart={onStart} />)
    await waitFor(() => screen.getByRole('button', { name: /start/i }))
    await userEvent.click(screen.getByRole('button', { name: /start/i }))
    await waitFor(() => expect(onStart).toHaveBeenCalledWith('t-1'))
    expect(client.setInstanceId).toHaveBeenCalledWith('new-inst')
    expect(onClose).toHaveBeenCalled()
  })

  it('shows error when createGameInstance fails', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue(mockVersions)
    vi.mocked(client.createGameInstance).mockRejectedValue(new Error('Server error'))
    render(<StartNewGameModal open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    await waitFor(() => screen.getByRole('button', { name: /start/i }))
    await userEvent.click(screen.getByRole('button', { name: /start/i }))
    await waitFor(() => expect(screen.getByText('Server error')).toBeInTheDocument())
  })

  it('calls onClose when Cancel is clicked', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue([])
    vi.mocked(client.listPersonas).mockResolvedValue([])
    vi.mocked(client.listCartridgeVersions).mockResolvedValue([])
    const onClose = vi.fn()
    render(<StartNewGameModal open={true} onClose={onClose} onStart={vi.fn()} />)
    await waitFor(() => screen.getByRole('button', { name: /cancel/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it('Start button is disabled when no persona is available', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listPersonas).mockResolvedValue([])
    vi.mocked(client.listCartridgeVersions).mockResolvedValue(mockVersions)
    render(<StartNewGameModal open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    await waitFor(() => screen.getByRole('button', { name: /start game/i }))
    expect(screen.getByRole('button', { name: /start game/i })).toBeDisabled()
  })
})
