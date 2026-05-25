/**
 * Unit tests for the MinigameWrapper component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MinigameWrapper from '../../components/minigames/MinigameWrapper'
import type { PendingInteraction } from '../../types/minigames'

const lightsOutPending: PendingInteraction = {
  interaction_type: 'minigame',
  minigame_id: 'lights_out',
  resolver_event: 'resolve_hack',
  config: {
    difficulty: { grid_size: 3, max_moves: 20, scramble_depth: 5 },
    assets: { icon_on: '🔴', icon_off: '⬜' },
    narrative_hooks: { on_combo: 'Sparks fly!' },
  },
}

describe('MinigameWrapper', () => {
  it('renders LightsOut for minigame_id=lights_out', () => {
    render(
      <MinigameWrapper
        pendingInteraction={lightsOutPending}
        onInteractionComplete={vi.fn()}
      />,
    )
    // LightsOut renders grid cells
    const cells = screen.getAllByRole('button').filter((b) =>
      b.getAttribute('aria-label')?.startsWith('Cell '),
    )
    expect(cells.length).toBe(9)
  })

  it('renders an error message for an unknown minigame_id', () => {
    render(
      <MinigameWrapper
        pendingInteraction={{ ...lightsOutPending, minigame_id: 'unknown_game' }}
        onInteractionComplete={vi.fn()}
      />,
    )
    expect(screen.getByText(/Unknown minigame/i)).toBeInTheDocument()
    expect(screen.getByText('unknown_game')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Dismiss/i })).toBeInTheDocument()
  })

  it('calls onInteractionComplete with aborted when Dismiss is clicked for unknown game', async () => {
    const onInteractionComplete = vi.fn()
    const user = userEvent.setup()
    render(
      <MinigameWrapper
        pendingInteraction={{ ...lightsOutPending, minigame_id: 'unknown_game' }}
        onInteractionComplete={onInteractionComplete}
      />,
    )
    await user.click(screen.getByRole('button', { name: /Dismiss/i }))
    expect(onInteractionComplete).toHaveBeenCalledOnce()
    expect(onInteractionComplete).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'aborted', minigame_id: 'unknown_game' }),
    )
  })

  it('calls onInteractionComplete with correct payload when game is aborted', async () => {
    const onInteractionComplete = vi.fn()
    const user = userEvent.setup()
    render(
      <MinigameWrapper
        pendingInteraction={lightsOutPending}
        onInteractionComplete={onInteractionComplete}
      />,
    )
    await user.click(screen.getByRole('button', { name: /Abandon puzzle/i }))
    expect(onInteractionComplete).toHaveBeenCalledOnce()
    expect(onInteractionComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        interaction_type: 'minigame',
        minigame_id: 'lights_out',
        status: 'aborted',
      }),
    )
  })

  it('passes config correctly to the minigame component', () => {
    render(
      <MinigameWrapper
        pendingInteraction={{
          ...lightsOutPending,
          config: {
            difficulty: { grid_size: 4 },
            assets: { icon_on: '🌟', icon_off: '💀' },
            narrative_hooks: {},
          },
        }}
        onInteractionComplete={vi.fn()}
      />,
    )
    // 4x4 grid = 16 cell buttons
    const cells = screen.getAllByRole('button').filter((b) =>
      b.getAttribute('aria-label')?.startsWith('Cell '),
    )
    expect(cells.length).toBe(16)
    // Custom icons should appear
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/🌟|💀/)
  })

  it('handles missing config gracefully (uses defaults)', () => {
    render(
      <MinigameWrapper
        pendingInteraction={{ interaction_type: 'minigame', minigame_id: 'lights_out' }}
        onInteractionComplete={vi.fn()}
      />,
    )
    // Default 4x4 grid
    const cells = screen.getAllByRole('button').filter((b) =>
      b.getAttribute('aria-label')?.startsWith('Cell '),
    )
    expect(cells.length).toBe(16)
  })
})
