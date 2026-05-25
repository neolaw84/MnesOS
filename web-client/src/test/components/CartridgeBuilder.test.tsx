import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CartridgeBuilder from '../../components/CartridgeBuilder'
import * as client from '../../api/client'

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    saveCartridgeVersion: vi.fn(),
  }
})

vi.mock('../../components/BuilderPane', () => ({
  default: ({
    title,
    content,
    format,
    onDownload,
  }: {
    title: string
    content: string
    format?: 'yaml' | 'js'
    onDownload?: () => void
  }) => (
    <section aria-label={`${title} pane`}>
      <div>
        <h2>{title}</h2>
        <button onClick={onDownload}>Download {title}</button>
      </div>
      <div aria-label={`${title} editor`}>{content}</div>
      {format ? <div>{`Format: ${format}`}</div> : null}
    </section>
  ),
}))

const initialPanes = {
  first_message: '# Welcome to the cartridge builder',
  prompt_directives: 'director:\n  tone: noir',
  yare_rules: 'state_schema: {}',
  yare_type: 'yaml' as const,
  bot_lore: 'The city fell one hundred years ago.',
}

describe('CartridgeBuilder', () => {
  const realCreateElement = document.createElement.bind(document)
  let downloadAnchor: HTMLAnchorElement

  beforeEach(() => {
    vi.clearAllMocks()

    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      value: vi.fn(() => 'blob:cartridge-builder'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      writable: true,
      value: vi.fn(),
    })

    downloadAnchor = realCreateElement('a')
    vi.spyOn(downloadAnchor, 'click').mockImplementation(() => undefined)
    vi.spyOn(document, 'createElement').mockImplementation(((tagName: string) => {
      if (tagName.toLowerCase() === 'a') {
        return downloadAnchor
      }
      return realCreateElement(tagName)
    }) as typeof document.createElement)

    vi.mocked(client.saveCartridgeVersion).mockResolvedValue({
      id: 'version-1',
      cartridge_id: 'cartridge-123',
      version_tag: '1.0.0',
      yare_spec: {},
      prompt_directives: {},
      bot_lore: initialPanes.bot_lore,
      first_message: initialPanes.first_message,
      checksum: 'abc123',
      published_at: '2026-01-01T00:00:00Z',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders all 4 pane headers', () => {
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    expect(screen.getByText('First Message')).toBeInTheDocument()
    expect(screen.getByText('Prompt Directives')).toBeInTheDocument()
    expect(screen.getByText('YARE Rules')).toBeInTheDocument()
    expect(screen.getByText('Bot Lore')).toBeInTheDocument()
  })

  it('renders editor areas for all 4 panes', () => {
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    expect(screen.getByLabelText('First Message editor')).toBeInTheDocument()
    expect(screen.getByLabelText('Prompt Directives editor')).toBeInTheDocument()
    expect(screen.getByLabelText('YARE Rules editor')).toBeInTheDocument()
    expect(screen.getByLabelText('Bot Lore editor')).toBeInTheDocument()
  })

  it('renders download button on each pane header', () => {
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    expect(screen.getByRole('button', { name: 'Download First Message' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Prompt Directives' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download YARE Rules' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Bot Lore' })).toBeInTheDocument()
  })

  it('shows YARE format toggle buttons', () => {
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    expect(screen.getByRole('button', { name: 'YAML' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'JS' })).toBeInTheDocument()
  })

  it('switches the YARE pane mode when the JS format toggle is clicked', async () => {
    const user = userEvent.setup()
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    const yarePane = screen.getByLabelText('YARE Rules pane')
    expect(within(yarePane).getByText('Format: yaml')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'JS' }))

    expect(within(yarePane).getByText('Format: js')).toBeInTheDocument()
  })

  it('clicking a pane download button triggers file download', async () => {
    const user = userEvent.setup()
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    await user.click(screen.getByRole('button', { name: 'Download First Message' }))

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(downloadAnchor.download).toBe('first-message.md')
    expect(downloadAnchor.click).toHaveBeenCalled()
  })

  it('shows Save Version button and opens the version dialog on click', async () => {
    const user = userEvent.setup()
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    await user.click(screen.getByRole('button', { name: /save version/i }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText(/version name/i)).toBeInTheDocument()
  })

  it('enters a version name and confirms save via saveCartridgeVersion API', async () => {
    const user = userEvent.setup()
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    await user.click(screen.getByRole('button', { name: /save version/i }))

    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText(/version name/i), '1.0.0')
    await user.click(within(dialog).getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      expect(client.saveCartridgeVersion).toHaveBeenCalledWith(
        'cartridge-123',
        '1.0.0',
        initialPanes,
      )
    })
  })

  it('shows Download ZIP button and triggers ZIP download', async () => {
    const user = userEvent.setup()
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    await user.click(screen.getByRole('button', { name: /download zip/i }))

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(downloadAnchor.download).toBe('cartridge-123-builder.zip')
    expect(downloadAnchor.click).toHaveBeenCalled()
  })

  it('renders with initial content when provided via props', () => {
    render(<CartridgeBuilder cartridgeId="cartridge-123" initialPanes={initialPanes} />)

    expect(screen.getByLabelText('First Message editor')).toHaveTextContent(initialPanes.first_message)
    expect(screen.getByLabelText('Prompt Directives editor')).toHaveTextContent(initialPanes.prompt_directives)
    expect(screen.getByLabelText('YARE Rules editor')).toHaveTextContent(initialPanes.yare_rules)
    expect(screen.getByLabelText('Bot Lore editor')).toHaveTextContent(initialPanes.bot_lore)
  })
})
