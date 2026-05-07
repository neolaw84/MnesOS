import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SaveManager from '../../components/SaveManager'
import type { GameSave } from '../../types'

const mockSaves: GameSave[] = [
  { id: 'save-1', instance_id: 'inst-1', turn_log_id: 'turn-1', label: 'After dragon fight', created_at: '2026-01-01T12:00:00Z' },
  { id: 'save-2', instance_id: 'inst-1', turn_log_id: 'turn-2', label: 'Before boss', created_at: '2026-01-02T12:00:00Z' },
]

function makeProps(overrides = {}) {
  return {
    saves: [],
    currentTurnId: 'turn-123',
    loading: false,
    onSave: vi.fn().mockResolvedValue(undefined),
    onLoad: vi.fn().mockResolvedValue(undefined),
    onRetry: vi.fn().mockResolvedValue(undefined),
    onRefresh: vi.fn().mockResolvedValue(undefined),
    hasMessages: true,
    ...overrides,
  }
}

describe('SaveManager', () => {
  it('calls onRefresh on mount', () => {
    const props = makeProps()
    render(<SaveManager {...props} />)
    expect(props.onRefresh).toHaveBeenCalledOnce()
  })

  it('calls onRetry when Retry is clicked', async () => {
    const user = userEvent.setup()
    const props = makeProps()
    render(<SaveManager {...props} />)
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(props.onRetry).toHaveBeenCalledOnce()
  })

  it('Retry is disabled when loading is true', () => {
    render(<SaveManager {...makeProps({ loading: true })} />)
    expect(screen.getByRole('button', { name: /retry/i })).toBeDisabled()
  })

  it('Retry is disabled when hasMessages is false', () => {
    render(<SaveManager {...makeProps({ hasMessages: false })} />)
    expect(screen.getByRole('button', { name: /retry/i })).toBeDisabled()
  })

  it('calls onSave with typed label when Save is clicked', async () => {
    const user = userEvent.setup()
    const props = makeProps()
    render(<SaveManager {...props} />)
    await user.type(screen.getByPlaceholderText('Save label...'), 'My checkpoint')
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith('My checkpoint')
  })

  it('uses default label if save label is empty', async () => {
    const user = userEvent.setup()
    const props = makeProps()
    render(<SaveManager {...props} />)
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(props.onSave).toHaveBeenCalledWith(expect.stringMatching(/Save .+/))
  })

  it('Save button is disabled when no currentTurnId', () => {
    render(<SaveManager {...makeProps({ currentTurnId: null })} />)
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('shows save count in Loads button', () => {
    render(<SaveManager {...makeProps({ saves: mockSaves })} />)
    expect(screen.getByRole('button', { name: /loads \(2\)/i })).toBeInTheDocument()
  })

  it('expands save list on Loads click', async () => {
    const user = userEvent.setup()
    render(<SaveManager {...makeProps({ saves: mockSaves })} />)
    await user.click(screen.getByRole('button', { name: /loads/i }))
    expect(screen.getByText('After dragon fight')).toBeInTheDocument()
    expect(screen.getByText('Before boss')).toBeInTheDocument()
  })

  it('shows empty state when no saves and list is expanded', async () => {
    const user = userEvent.setup()
    render(<SaveManager {...makeProps({ saves: [] })} />)
    await user.click(screen.getByRole('button', { name: /loads/i }))
    expect(screen.getByText('No saves yet.')).toBeInTheDocument()
  })

  it('calls onLoad when Load button is clicked in save list', async () => {
    const user = userEvent.setup()
    const props = makeProps({ saves: mockSaves })
    render(<SaveManager {...props} />)
    await user.click(screen.getByRole('button', { name: /loads/i }))
    const loadButtons = screen.getAllByRole('button', { name: /^load$/i })
    await user.click(loadButtons[0])
    expect(props.onLoad).toHaveBeenCalledWith(mockSaves[0])
  })
})
