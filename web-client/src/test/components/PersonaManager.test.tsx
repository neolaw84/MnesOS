import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PersonaManager from '../../components/PersonaManager'
import * as client from '../../api/client'
import type { Persona } from '../../types'

vi.mock('../../api/client', () => ({
  listPersonas: vi.fn(),
  createPersona: vi.fn(),
  updatePersona: vi.fn(),
  deletePersona: vi.fn(),
}))

const mockPersonas: Persona[] = [
  {
    id: 'p-1', user_id: 'u-1', name: 'Aria', pronoun_sub: 'she', pronoun_obj: 'her',
    pronoun_poss: 'her', pronoun_poss_obj: 'hers', appearance: 'Tall and fierce', background: '', personality: '',
  },
]

async function fillPersonaForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('e.g. Robin'), 'Test Hero')
  await user.type(screen.getByPlaceholderText('they'), 'they')
  await user.type(screen.getByPlaceholderText('them'), 'them')
  await user.type(screen.getByPlaceholderText('their'), 'their')
  await user.type(screen.getByPlaceholderText('theirs'), 'theirs')
}

describe('PersonaManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    vi.mocked(client.listPersonas).mockReturnValue(new Promise(() => {}))
    render(<PersonaManager />)
    expect(screen.getByText('Loading personas...')).toBeInTheDocument()
  })

  it('shows empty state when no personas', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    render(<PersonaManager />)
    await waitFor(() => expect(screen.getByText(/No personas found/i)).toBeInTheDocument())
  })

  it('renders persona cards after loading', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    render(<PersonaManager />)
    await waitFor(() => expect(screen.getByText('Aria')).toBeInTheDocument())
    expect(screen.getByText('she/her')).toBeInTheDocument()
  })

  it('shows error when listPersonas fails', async () => {
    vi.mocked(client.listPersonas).mockRejectedValue(new Error('Fetch failed'))
    render(<PersonaManager />)
    await waitFor(() => expect(screen.getByText('Fetch failed')).toBeInTheDocument())
  })

  it('opens create modal on New Persona button click', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /new persona/i }))
    await user.click(screen.getByRole('button', { name: /new persona/i }))
    expect(screen.getByText('Create Persona')).toBeInTheDocument()
  })

  it('creates a new persona', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    const newPersona: Persona = { ...mockPersonas[0], id: 'p-new', name: 'Test Hero' }
    vi.mocked(client.createPersona).mockResolvedValue(newPersona)
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /new persona/i }))
    await user.click(screen.getByRole('button', { name: /new persona/i }))
    await fillPersonaForm(user)
    await user.click(screen.getByRole('button', { name: /save persona/i }))
    await waitFor(() => expect(client.createPersona).toHaveBeenCalled())
  })

  it('shows validation error when required fields are empty', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /new persona/i }))
    await user.click(screen.getByRole('button', { name: /new persona/i }))
    await user.click(screen.getByRole('button', { name: /save persona/i }))
    expect(screen.getByText(/name and all pronouns are required/i)).toBeInTheDocument()
  })

  it('opens edit modal on Edit button click', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /edit/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.getByText('Edit Persona')).toBeInTheDocument()
    // Name field should be pre-filled
    expect(screen.getByDisplayValue('Aria')).toBeInTheDocument()
  })

  it('updates a persona', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue(mockPersonas)
    vi.mocked(client.updatePersona).mockResolvedValue({ ...mockPersonas[0], name: 'Aria Updated' })
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /edit/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))
    const nameInput = screen.getByDisplayValue('Aria')
    await user.clear(nameInput)
    await user.type(nameInput, 'Aria Updated')
    await user.click(screen.getByRole('button', { name: /save persona/i }))
    await waitFor(() => expect(client.updatePersona).toHaveBeenCalled())
  })

  it('closes modal on Cancel click', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /new persona/i }))
    await user.click(screen.getByRole('button', { name: /new persona/i }))
    expect(screen.getByText('Create Persona')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText('Create Persona')).not.toBeInTheDocument()
  })

  it('refreshes personas on Refresh button click', async () => {
    vi.mocked(client.listPersonas).mockResolvedValue([])
    const user = userEvent.setup()
    render(<PersonaManager />)
    await waitFor(() => screen.getByRole('button', { name: /refresh/i }))
    await user.click(screen.getByRole('button', { name: /refresh/i }))
    expect(client.listPersonas).toHaveBeenCalledTimes(2)
  })
})
