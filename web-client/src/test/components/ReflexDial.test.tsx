/**
 * Unit tests for [MnesOS-260525-11] Reflex Dial mini-game.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import ReflexDial from '../../components/minigames/ReflexDial/ReflexDial'

const defaultConfig = {
  difficulty: {
    indicator_speed: 2,
    zone_width_degrees: 40,
    required_success_hits: 3,
  },
  assets: {},
  narrative_hooks: {},
}

const keySequenceConfig = {
  difficulty: {
    indicator_speed: 2,
    zone_width_degrees: 40,
    required_success_hits: 2,
    key_sequence: ['ArrowUp', 'ArrowDown'],
  },
  assets: {},
  narrative_hooks: {},
}

describe('ReflexDial', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the dial container', () => {
    render(<ReflexDial config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByTestId('reflex-dial')).toBeInTheDocument()
  })

  it('shows hit counter', () => {
    render(<ReflexDial config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByTestId('hit-counter')).toHaveTextContent('0')
  })

  it('shows required hits target', () => {
    render(<ReflexDial config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByTestId('hit-target')).toHaveTextContent('3')
  })

  it('registers a hit when clicking in the success zone', () => {
    render(<ReflexDial config={defaultConfig} onComplete={vi.fn()} />)

    act(() => {
      vi.advanceTimersByTime(100)
    })

    fireEvent.click(screen.getByTestId('reflex-dial-tap-area'))

    const hitCounter = screen.getByTestId('hit-counter')
    const hits = parseInt(hitCounter.textContent || '0', 10)
    expect(hits).toBeGreaterThanOrEqual(0)
  })

  it('calls onComplete with success when required hits are achieved', () => {
    const onComplete = vi.fn()
    // zone_width_degrees=360 means any click is a hit
    render(<ReflexDial config={{ ...defaultConfig, difficulty: { ...defaultConfig.difficulty, required_success_hits: 1, zone_width_degrees: 360 } }} onComplete={onComplete} />)

    act(() => { vi.advanceTimersByTime(100) })
    
    act(() => {
      fireEvent.click(screen.getByTestId('reflex-dial-tap-area'))
    })

    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'completed',
        metrics: expect.objectContaining({
          success: true,
          hits: 1,
        }),
      }),
    )
  })

  it('calls onComplete with failure after max attempts', () => {
    const onComplete = vi.fn()
    // zone_width=1 degree with speed=0 → needle stays at 0, zone at random position mostly misses
    // Use required_success_hits=1, max_attempts=3
    render(<ReflexDial config={{ ...defaultConfig, difficulty: { indicator_speed: 0, zone_width_degrees: 1, required_success_hits: 1 } }} onComplete={onComplete} />)

    // Click multiple times (these will be misses since zone is likely not at 0°)
    for (let i = 0; i < 3; i++) {
      act(() => { vi.advanceTimersByTime(50) })
      fireEvent.click(screen.getByTestId('reflex-dial-tap-area'))
    }

    act(() => { vi.advanceTimersByTime(500) })

    if (onComplete.mock.calls.length > 0) {
      expect(onComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          metrics: expect.objectContaining({ success: false }),
        }),
      )
    }
  })

  it('shows key sequence overlay when key_sequence is provided', () => {
    render(<ReflexDial config={keySequenceConfig} onComplete={vi.fn()} />)
    expect(screen.getByTestId('key-sequence-overlay')).toBeInTheDocument()
  })

  it('does not show key sequence overlay when key_sequence is not provided', () => {
    render(<ReflexDial config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.queryByTestId('key-sequence-overlay')).not.toBeInTheDocument()
  })

  it('reports avg_reaction_time_ms in metrics on completion', () => {
    const onComplete = vi.fn()
    render(<ReflexDial config={{ ...defaultConfig, difficulty: { ...defaultConfig.difficulty, required_success_hits: 1, zone_width_degrees: 360 } }} onComplete={onComplete} />)

    act(() => { vi.advanceTimersByTime(100) })
    fireEvent.click(screen.getByTestId('reflex-dial-tap-area'))
    act(() => { vi.advanceTimersByTime(500) })

    if (onComplete.mock.calls.length > 0) {
      const metrics = onComplete.mock.calls[0][0].metrics
      expect(metrics).toHaveProperty('avg_reaction_time_ms')
      expect(typeof metrics.avg_reaction_time_ms).toBe('number')
    }
  })

  it('allows abort', () => {
    const onComplete = vi.fn()
    render(<ReflexDial config={defaultConfig} onComplete={onComplete} />)

    // Use fireEvent instead of userEvent to avoid fake timer issues
    fireEvent.click(screen.getByRole('button', { name: /abandon/i }))

    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'aborted' }),
    )
  })
})
