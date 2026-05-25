import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CartridgeLibrary from '../../components/CartridgeLibrary'
import * as client from '../../api/client'
import type { Cartridge, CartridgeVersion } from '../../types'

vi.mock('../../api/client', () => ({
  createCartridge: vi.fn(),
  deleteCartridge: vi.fn(),
  listCartridges: vi.fn(),
  listCartridgeVersions: vi.fn(),
  uploadCartridgeVersion: vi.fn(),
}))

vi.mock('../../components/CartridgeBuilder', () => ({
  default: ({ cartridgeId, initialPanes }: { cartridgeId: string; initialPanes?: unknown }) => (
    <div data-testid="cartridge-builder" data-cartridge-id={cartridgeId}>
      {initialPanes ? <span data-testid="builder-initial-panes">panes-loaded</span> : null}
    </div>
  ),
}))

const mockCartridges: Cartridge[] = [
  {
    id: 'c-1',
    creator_id: 'u-1',
    title: 'Test Cartridge',
    description: 'Description',
    genre: 'fantasy',
    visibility: 'PUBLIC',
  },
]

const mockVersion: CartridgeVersion = {
  id: 'v-1',
  cartridge_id: 'c-1',
  version_tag: '1.0.0',
  yare_spec: {},
  prompt_directives: {},
  bot_lore: 'Lore',
  first_message: 'Hello there',
  checksum: 'abc123',
  published_at: '2026-01-01T00:00:00Z',
}

describe('CartridgeLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'alert').mockImplementation(() => undefined)
  })

  it('shows the first-message file input in individual-file upload mode', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue([])
    const user = userEvent.setup()

    render(<CartridgeLibrary />)
    await waitFor(() => screen.getByText('Test Cartridge'))
    await user.click(screen.getByText('Test Cartridge'))
    await user.click(screen.getByRole('button', { name: /upload version/i }))
    await user.selectOptions(screen.getByRole('combobox', { name: /upload mode/i }), 'files')

    expect(screen.getByLabelText(/first-message\.md/i)).toBeInTheDocument()
  })

  it('retries loading cartridges after a transient fetch failure', async () => {
    vi.mocked(client.listCartridges)
      .mockRejectedValueOnce(new Error('Failed to fetch'))
      .mockResolvedValueOnce(mockCartridges)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue([])

    render(<CartridgeLibrary />)

    await waitFor(() => expect(screen.getByText('Test Cartridge')).toBeInTheDocument())
    expect(screen.queryByText(/failed to load cartridges/i)).not.toBeInTheDocument()
  })

  it('submits first-message file with individual-file uploads', async () => {
    vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
    vi.mocked(client.listCartridgeVersions).mockResolvedValue([])
    vi.mocked(client.uploadCartridgeVersion).mockResolvedValue(mockVersion)
    const user = userEvent.setup()

    render(<CartridgeLibrary />)
    await waitFor(() => screen.getByText('Test Cartridge'))
    await user.click(screen.getByText('Test Cartridge'))
    await user.click(screen.getByRole('button', { name: /upload version/i }))
    await user.selectOptions(screen.getByRole('combobox', { name: /upload mode/i }), 'files')
    await user.type(screen.getByLabelText(/version tag/i), '1.0.0')

    const firstMessageInput = screen.getByLabelText(/first-message\.md/i) as HTMLInputElement
    const directivesInput = screen.getByLabelText(/prompt_directives\.yaml/i) as HTMLInputElement
    const file = new File(['hello'], 'first-message.md', { type: 'text/markdown' })
    const directivesFile = new File(['director: {}'], 'prompt_directives.yaml', { type: 'text/yaml' })
    await user.upload(firstMessageInput, file)
    await user.upload(screen.getByLabelText(/yare\.yaml/i), new File(['yare'], 'yare.yaml', { type: 'text/yaml' }))
    await user.upload(screen.getByLabelText(/bot_lore\.md/i), new File(['lore'], 'bot_lore.md', { type: 'text/markdown' }))
    await user.upload(directivesInput, directivesFile)

    await user.click(screen.getByRole('button', { name: /^upload$/i }))

    await waitFor(() => expect(client.uploadCartridgeVersion).toHaveBeenCalled())
    expect(client.uploadCartridgeVersion).toHaveBeenCalledWith('c-1', '1.0.0', expect.objectContaining({
      firstMessageFile: file,
      directivesFile,
    }))
  })

  describe('Edit in Builder flow', () => {
    it('shows an "Edit in Builder" button for each version', async () => {
      vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
      vi.mocked(client.listCartridgeVersions).mockResolvedValue([mockVersion])
      const user = userEvent.setup()

      render(<CartridgeLibrary />)
      await waitFor(() => screen.getByText('Test Cartridge'))
      await user.click(screen.getByText('Test Cartridge'))

      await waitFor(() =>
        expect(
          screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }),
        ).toBeInTheDocument(),
      )
    })

    it('opens CartridgeBuilder with correct cartridgeId when "Edit in Builder" is clicked', async () => {
      vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
      vi.mocked(client.listCartridgeVersions).mockResolvedValue([mockVersion])
      const user = userEvent.setup()

      render(<CartridgeLibrary />)
      await waitFor(() => screen.getByText('Test Cartridge'))
      await user.click(screen.getByText('Test Cartridge'))

      await waitFor(() =>
        screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }),
      )
      await user.click(screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }))

      const builder = screen.getByTestId('cartridge-builder')
      expect(builder).toBeInTheDocument()
      expect(builder).toHaveAttribute('data-cartridge-id', 'c-1')
    })

    it('populates the builder with initial panes from the selected version', async () => {
      vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
      vi.mocked(client.listCartridgeVersions).mockResolvedValue([mockVersion])
      const user = userEvent.setup()

      render(<CartridgeLibrary />)
      await waitFor(() => screen.getByText('Test Cartridge'))
      await user.click(screen.getByText('Test Cartridge'))

      await waitFor(() =>
        screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }),
      )
      await user.click(screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }))

      expect(screen.getByTestId('builder-initial-panes')).toBeInTheDocument()
    })

    it('shows a back button inside the builder that returns to the cartridge detail', async () => {
      vi.mocked(client.listCartridges).mockResolvedValue(mockCartridges)
      vi.mocked(client.listCartridgeVersions).mockResolvedValue([mockVersion])
      const user = userEvent.setup()

      render(<CartridgeLibrary />)
      await waitFor(() => screen.getByText('Test Cartridge'))
      await user.click(screen.getByText('Test Cartridge'))

      await waitFor(() =>
        screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }),
      )
      await user.click(screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i }))

      expect(screen.getByTestId('cartridge-builder')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: /back to test cartridge/i }))

      expect(screen.queryByTestId('cartridge-builder')).not.toBeInTheDocument()
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /edit version 1\.0\.0 in builder/i })).toBeInTheDocument(),
      )
    })
  })
})
