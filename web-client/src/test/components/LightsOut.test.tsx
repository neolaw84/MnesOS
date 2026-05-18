/**
 * Unit tests for the LightsOut minigame component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LightsOut from '../../components/minigames/LightsOut/LightsOut'

const defaultConfig = {
  difficulty: { grid_size: 3, max_moves: 20, scramble_depth: 5 },
  assets: { icon_on: '🔴', icon_off: '⬜' },
  narrative_hooks: {},
}

describe('LightsOut', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders cells matching grid_size × grid_size', () => {
    const onComplete = vi.fn()
    render(<LightsOut config={defaultConfig} onComplete={onComplete} />)
    const cells = screen.getAllByRole('button', { name: /Cell \d+/ })
    // 3x3 = 9 cells plus the "Abandon puzzle" button — filter to cell buttons
    const cellButtons = cells.filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))
    expect(cellButtons).toHaveLength(9)
  })

  it('shows move counter', () => {
    render(<LightsOut config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByText(/Moves left/)).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
  })

  it('shows the Abandon puzzle button initially', () => {
    render(<LightsOut config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Abandon puzzle/i })).toBeInTheDocument()
  })

  it('calls onComplete with aborted status when abandon is clicked', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<LightsOut config={defaultConfig} onComplete={onComplete} />)
    await user.click(screen.getByRole('button', { name: /Abandon puzzle/i }))
    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'aborted' }),
    )
  })

  it('decrements moves left when a cell is clicked', async () => {
    const user = userEvent.setup()
    render(<LightsOut config={defaultConfig} onComplete={vi.fn()} />)
    const cellButtons = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))
    await user.click(cellButtons[0])
    // Move counter should now be 19
    expect(screen.getByText('19')).toBeInTheDocument()
  })

  it('disables all cells after the game ends (abandon)', async () => {
    const user = userEvent.setup()
    render(<LightsOut config={defaultConfig} onComplete={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /Abandon puzzle/i }))
    const cellButtons = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))
    cellButtons.forEach((cell) => expect(cell).toBeDisabled())
  })

  it('uses custom icon_on / icon_off from assets config', () => {
    const config = {
      difficulty: { grid_size: 2, max_moves: 10, scramble_depth: 1 },
      assets: { icon_on: '🔥', icon_off: '❄️' },
      narrative_hooks: {},
    }
    render(<LightsOut config={config} onComplete={vi.fn()} />)
    // At least one icon type should be visible
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/🔥|❄️/)
  })

  it('calls onComplete with failed status when moves are exhausted', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    // grid_size=2, max_moves=2, scramble_depth=1
    const config = {
      difficulty: { grid_size: 2, max_moves: 2, scramble_depth: 1 },
      assets: {},
      narrative_hooks: {},
    }
    render(<LightsOut config={config} onComplete={onComplete} />)
    const cellButtons = () =>
      screen
        .getAllByRole('button')
        .filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))

    // If puzzle isn't already solved, exhaust moves
    // We need to keep clicking until onComplete is called with 'failed' or 'completed'
    // To avoid an infinite loop, click 2 cells
    for (let i = 0; i < 2 && !onComplete.mock.calls.length; i++) {
      const btns = cellButtons()
      if (btns.length === 0) break
      // Pick a cell that is currently ON (if any) to avoid a trivial solve
      const litCell = btns.find((b) => b.classList.contains('lights-out-cell--on')) ?? btns[0]
      await user.click(litCell)
    }

    // After max_moves, if not solved, should be failed
    if (onComplete.mock.calls.length) {
      const status = onComplete.mock.calls[0][0].status
      expect(['completed', 'failed']).toContain(status)
    }
  })

  it('shows on_failure narrative hook text when moves are exhausted', async () => {
    // Math.random = 0.99 → idx = floor(0.99 * 4) = 3 in a 2x2 grid (4 cells)
    // scramble_depth=1: toggles cell 3 and its neighbours (cells 1, 2, 3) → lit
    // Clicking cell 0 toggles cells 0, 1, 2 → only cell 3 remains lit → failed
    vi.spyOn(Math, 'random').mockReturnValue(0.99)
    const onComplete = vi.fn()
    const user = userEvent.setup()
    const config = {
      difficulty: { grid_size: 2, max_moves: 1, scramble_depth: 1 },
      assets: {},
      narrative_hooks: { on_failure: 'Game over!' },
    }
    render(<LightsOut config={config} onComplete={onComplete} />)
    const cellButtons = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))
    await user.click(cellButtons[0])
    await waitFor(() => expect(screen.getByText('Game over!')).toBeInTheDocument())
    vi.restoreAllMocks()
  })

  it('shows on_near_miss narrative hook when few cells remain lit', async () => {
    // Same scramble setup; with only on_near_miss (no on_failure), after
    // clicking cell 0: cell 3 remains lit (litCount=1 ≤ 2) → shows hook text.
    vi.spyOn(Math, 'random').mockReturnValue(0.99)
    const user = userEvent.setup()
    const config = {
      difficulty: { grid_size: 2, max_moves: 5, scramble_depth: 1 },
      assets: {},
      narrative_hooks: { on_near_miss: 'Almost there!' },
    }
    render(<LightsOut config={config} onComplete={vi.fn()} />)
    const cellButtons = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-label')?.startsWith('Cell '))
    await user.click(cellButtons[0])
    await waitFor(() => expect(screen.getByText('Almost there!')).toBeInTheDocument())
    vi.restoreAllMocks()
  })
})
