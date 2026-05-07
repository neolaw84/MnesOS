import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import StateDebugger from '../../components/StateDebugger'

describe('StateDebugger', () => {
  const botMemory = {
    player: { hp: 42, gold: 100, level: 3, inventory: ['sword', 'shield'] },
    current_location: 'Dungeon Level 2',
  }

  it('renders toggle button when closed', () => {
    render(<StateDebugger botMemory={{}} visible={false} onToggle={vi.fn()} />)
    expect(screen.getByRole('button', { name: /debug/i })).toBeInTheDocument()
  })

  it('calls onToggle when button is clicked', async () => {
    const onToggle = vi.fn()
    const { getByRole } = render(
      <StateDebugger botMemory={{}} visible={false} onToggle={onToggle} />
    )
    getByRole('button').click()
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it('shows debug content when visible is true', () => {
    render(<StateDebugger botMemory={botMemory} visible={true} onToggle={vi.fn()} />)
    expect(screen.getByText('🔧 State Debugger')).toBeInTheDocument()
  })

  it('hides debug content when visible is false', () => {
    render(<StateDebugger botMemory={botMemory} visible={false} onToggle={vi.fn()} />)
    expect(screen.queryByText('🔧 State Debugger')).not.toBeInTheDocument()
  })

  it('displays quick stats when visible', () => {
    render(<StateDebugger botMemory={botMemory} visible={true} onToggle={vi.fn()} />)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Dungeon Level 2')).toBeInTheDocument()
  })

  it('renders JSON of botMemory in the debug panel', () => {
    render(<StateDebugger botMemory={{ foo: 'bar' }} visible={true} onToggle={vi.fn()} />)
    expect(screen.getByText(/"foo"/)).toBeInTheDocument()
  })

  it('does not render stats for missing fields', () => {
    render(<StateDebugger botMemory={{}} visible={true} onToggle={vi.fn()} />)
    // No HP / Gold / Level stats should appear
    expect(screen.queryByText(/HP:/)).not.toBeInTheDocument()
  })

  it('shows "Hide Debug" label when visible', () => {
    render(<StateDebugger botMemory={{}} visible={true} onToggle={vi.fn()} />)
    expect(screen.getByRole('button', { name: /hide debug/i })).toBeInTheDocument()
  })
})
