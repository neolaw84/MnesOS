import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInput from '../../components/ChatInput'

describe('ChatInput', () => {
  it('renders a textarea and send button', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('button is disabled when input is empty', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('button is disabled when disabled prop is true', async () => {
    const user = userEvent.setup()
    render(<ChatInput onSend={vi.fn()} disabled={true} />)
    await user.type(screen.getByRole('textbox'), 'hello')
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('calls onSend with trimmed input and clears field on button click', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} disabled={false} />)
    await user.type(screen.getByRole('textbox'), '  attack the dragon  ')
    await user.click(screen.getByRole('button'))
    expect(onSend).toHaveBeenCalledWith('attack the dragon')
    expect(screen.getByRole('textbox')).toHaveValue('')
  })

  it('calls onSend on Enter key (not Shift+Enter)', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} disabled={false} />)
    await user.type(screen.getByRole('textbox'), 'look around{Enter}')
    expect(onSend).toHaveBeenCalledWith('look around')
  })

  it('does not call onSend on Shift+Enter', async () => {
    const onSend = vi.fn()
    const user = userEvent.setup()
    render(<ChatInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await user.type(textarea, 'line one')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('shows waiting placeholder when disabled', () => {
    render(<ChatInput onSend={vi.fn()} disabled={true} />)
    expect(screen.getByPlaceholderText('Waiting for narrator...')).toBeInTheDocument()
  })

  it('shows action placeholder when enabled', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} />)
    expect(screen.getByPlaceholderText('What do you do?')).toBeInTheDocument()
  })
})
