import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsModal from '../../components/SettingsModal'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  getOpenRouterKey: vi.fn(() => ''),
  setOpenRouterKey: vi.fn(),
  getUserId: vi.fn(() => ''),
  setUserId: vi.fn(),
  getInstanceId: vi.fn(() => ''),
  setInstanceId: vi.fn(),
}))

describe('SettingsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when open is false', () => {
    const { container } = render(<SettingsModal open={false} onClose={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders form fields when open is true', () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />)
    expect(screen.getByPlaceholderText('sk-or-...')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('user-uuid')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('instance-uuid')).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<SettingsModal open={true} onClose={onClose} />)
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('persists values and closes on Save', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<SettingsModal open={true} onClose={onClose} />)
    await user.type(screen.getByPlaceholderText('sk-or-...'), 'sk-or-testkey')
    await user.type(screen.getByPlaceholderText('user-uuid'), 'uid-1')
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(client.setOpenRouterKey).toHaveBeenCalledWith('sk-or-testkey')
    expect(client.setUserId).toHaveBeenCalledWith('uid-1')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when overlay is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<SettingsModal open={true} onClose={onClose} />)
    await user.click(document.querySelector('.modal-overlay')!)
    expect(onClose).toHaveBeenCalledOnce()
  })
})
