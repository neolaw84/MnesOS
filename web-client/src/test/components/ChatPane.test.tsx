import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatPane from '../../components/ChatPane'
import type { DisplayMessage } from '../../types'

describe('ChatPane', () => {
  it('shows empty state message when no messages and not loading', () => {
    render(<ChatPane messages={[]} loading={false} />)
    expect(screen.getByText(/No messages yet/i)).toBeInTheDocument()
  })

  it('does not show empty state when loading', () => {
    render(<ChatPane messages={[]} loading={true} />)
    expect(screen.queryByText(/No messages yet/i)).not.toBeInTheDocument()
  })

  it('renders user message with correct role label', () => {
    const messages: DisplayMessage[] = [{ role: 'user', content: 'I attack' }]
    render(<ChatPane messages={messages} loading={false} />)
    expect(screen.getByText('🗡️ Player')).toBeInTheDocument()
    expect(screen.getByText('I attack')).toBeInTheDocument()
  })

  it('renders assistant message with narrator role label', () => {
    const messages: DisplayMessage[] = [{ role: 'assistant', content: 'The dragon roars.' }]
    render(<ChatPane messages={messages} loading={false} />)
    expect(screen.getByText('📜 Narrator')).toBeInTheDocument()
    expect(screen.getByText('The dragon roars.')).toBeInTheDocument()
  })

  it('shows loading indicator when loading is true', () => {
    render(<ChatPane messages={[]} loading={true} />)
    expect(screen.getByText('Thinking')).toBeInTheDocument()
  })

  it('renders multiple messages in order', () => {
    const messages: DisplayMessage[] = [
      { role: 'user', content: 'First' },
      { role: 'assistant', content: 'Second' },
    ]
    render(<ChatPane messages={messages} loading={false} />)
    const texts = screen.getAllByText(/First|Second/)
    expect(texts[0]).toHaveTextContent('First')
    expect(texts[1]).toHaveTextContent('Second')
  })
})
