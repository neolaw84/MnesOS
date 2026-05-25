/**
 * Unit tests for [MnesOS-260525-10] Articulation Scramble mini-game.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ArticulationScramble from '../../components/minigames/ArticulationScramble/ArticulationScramble'

const defaultConfig = {
  difficulty: {
    prompt: 'Convince the guard to let you pass',
    prefix: 'I say: ',
    correct_sequence: ['please', 'let', 'me', 'pass'],
    confuse_words: ['attack', 'flee', 'ignore', 'shout'],
  },
  assets: {},
  narrative_hooks: {},
}

const timedConfig = {
  difficulty: {
    ...defaultConfig.difficulty,
    max_time_seconds: 2,
  },
  assets: {},
  narrative_hooks: {},
}

describe('ArticulationScramble', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the prompt text', () => {
    render(<ArticulationScramble config={defaultConfig} onComplete={vi.fn()} />)
    expect(screen.getByText(/Convince the guard/)).toBeInTheDocument()
  })

  it('renders word buttons for correct_sequence + confuse_words', () => {
    render(<ArticulationScramble config={defaultConfig} onComplete={vi.fn()} />)
    for (const word of [...defaultConfig.difficulty.correct_sequence, ...defaultConfig.difficulty.confuse_words]) {
      expect(screen.getByRole('button', { name: word })).toBeInTheDocument()
    }
  })

  it('allows selecting words in sequence', async () => {
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'please' }))
    expect(screen.getByTestId('selected-words')).toHaveTextContent('please')
  })

  it('calls onComplete with success when correct sequence is submitted', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={onComplete} />)

    for (const word of defaultConfig.difficulty.correct_sequence) {
      await user.click(screen.getByRole('button', { name: word }))
    }

    await user.click(screen.getByRole('button', { name: /end response/i }))

    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'completed',
        metrics: expect.objectContaining({ success: true }),
      }),
    )
  })

  it('calls onComplete with failure when wrong sequence is submitted', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={onComplete} />)

    await user.click(screen.getByRole('button', { name: 'attack' }))
    await user.click(screen.getByRole('button', { name: 'flee' }))

    await user.click(screen.getByRole('button', { name: /end response/i }))

    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'failed',
        metrics: expect.objectContaining({ success: false }),
      }),
    )
  })

  it('auto-submits when timer expires', () => {
    vi.useFakeTimers()
    const onComplete = vi.fn()
    render(<ArticulationScramble config={timedConfig} onComplete={onComplete} />)

    act(() => {
      vi.advanceTimersByTime(2100)
    })

    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        metrics: expect.objectContaining({ success: false }),
      }),
    )
    vi.useRealTimers()
  })

  it('allows deselecting a word by clicking it again in the selection', async () => {
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'please' }))
    expect(screen.getByTestId('selected-words')).toHaveTextContent('please')

    await user.click(screen.getByTestId('selected-word-0'))
    expect(screen.getByTestId('selected-words')).not.toHaveTextContent('please')
  })

  it('reports selected_sequence in metrics', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={onComplete} />)

    await user.click(screen.getByRole('button', { name: 'please' }))
    await user.click(screen.getByRole('button', { name: 'let' }))
    await user.click(screen.getByRole('button', { name: /end response/i }))

    const metrics = onComplete.mock.calls[0][0].metrics
    expect(metrics.selected_sequence).toEqual(['please', 'let'])
  })

  it('reports time_spent_seconds in metrics', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ArticulationScramble config={defaultConfig} onComplete={onComplete} />)

    for (const word of defaultConfig.difficulty.correct_sequence) {
      await user.click(screen.getByRole('button', { name: word }))
    }
    await user.click(screen.getByRole('button', { name: /end response/i }))

    const metrics = onComplete.mock.calls[0][0].metrics
    expect(metrics.time_spent_seconds).toBeGreaterThanOrEqual(0)
  })
})
