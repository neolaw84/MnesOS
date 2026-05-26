/**
 * Unit tests for [MnesOS-260525-08] Frontend – "I'm Feeling Lucky" Console UI.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LuckyConsole from '../../components/LuckyConsole'
import * as cartridgeBuilder from '../../api/cartridgeBuilder'

vi.mock('../../api/cartridgeBuilder', () => ({
  generateCartridge: vi.fn(),
}))

describe('LuckyConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the requirements text area', () => {
    render(<LuckyConsole />)
    expect(screen.getByRole('textbox', { name: /requirements/i })).toBeInTheDocument()
  })

  it('renders the generate button', () => {
    render(<LuckyConsole />)
    expect(screen.getByRole('button', { name: /generate|i'm feeling lucky/i })).toBeInTheDocument()
  })

  it('disables generate button when requirements is empty', () => {
    render(<LuckyConsole />)
    const btn = screen.getByRole('button', { name: /generate|i'm feeling lucky/i })
    expect(btn).toBeDisabled()
  })

  it('enables generate button when requirements are entered', async () => {
    const user = userEvent.setup()
    render(<LuckyConsole />)

    const textarea = screen.getByRole('textbox', { name: /requirements/i })
    await user.type(textarea, 'Create a dungeon crawler game')

    const btn = screen.getByRole('button', { name: /generate|i'm feeling lucky/i })
    expect(btn).not.toBeDisabled()
  })

  it('calls generateCartridge API on submit', async () => {
    const mockGenerate = vi.mocked(cartridgeBuilder.generateCartridge)
    mockGenerate.mockResolvedValue({
      bot_lore: '# World',
      first_message: 'Welcome',
      prompt_directives: 'director: Be nice',
      yare_spec: 'state_schema: {}',
    })

    const user = userEvent.setup()
    render(<LuckyConsole />)

    const textarea = screen.getByRole('textbox', { name: /requirements/i })
    await user.type(textarea, 'Create a dungeon crawler game')

    const btn = screen.getByRole('button', { name: /generate|i'm feeling lucky/i })
    await user.click(btn)

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith(
        expect.objectContaining({ requirements: 'Create a dungeon crawler game' }),
      )
    })
  })

  it('displays generated results', async () => {
    const mockGenerate = vi.mocked(cartridgeBuilder.generateCartridge)
    mockGenerate.mockResolvedValue({
      bot_lore: '# The Dark Dungeon',
      first_message: 'You enter the dungeon...',
      prompt_directives: 'director: Be dramatic',
      yare_spec: 'state_schema:\n  player:\n    hp: 100',
    })

    const user = userEvent.setup()
    render(<LuckyConsole />)

    const textarea = screen.getByRole('textbox', { name: /requirements/i })
    await user.type(textarea, 'Dungeon game')

    await user.click(screen.getByRole('button', { name: /generate|i'm feeling lucky/i }))

    await waitFor(() => {
      expect(screen.getByText(/The Dark Dungeon/)).toBeInTheDocument()
    })
  })

  it('shows loading state during generation', async () => {
    const mockGenerate = vi.mocked(cartridgeBuilder.generateCartridge)
    // Never resolve to keep loading state
    mockGenerate.mockReturnValue(new Promise(() => {}))

    const user = userEvent.setup()
    render(<LuckyConsole />)

    const textarea = screen.getByRole('textbox', { name: /requirements/i })
    await user.type(textarea, 'Any game')

    await user.click(screen.getByRole('button', { name: /generate|i'm feeling lucky/i }))

    expect(screen.getByText(/generating your cartridge/i)).toBeInTheDocument()
  })

  it('shows error state on API failure', async () => {
    const mockGenerate = vi.mocked(cartridgeBuilder.generateCartridge)
    mockGenerate.mockRejectedValue(new Error('Network error'))

    const user = userEvent.setup()
    render(<LuckyConsole />)

    const textarea = screen.getByRole('textbox', { name: /requirements/i })
    await user.type(textarea, 'Any game')

    await user.click(screen.getByRole('button', { name: /generate|i'm feeling lucky/i }))

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument()
    })
  })
})
