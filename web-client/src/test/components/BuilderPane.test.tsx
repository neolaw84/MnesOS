import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BuilderPane from '../../components/BuilderPane'

describe('BuilderPane', () => {
  const realCreateElement = document.createElement.bind(document)
  let downloadAnchor: HTMLAnchorElement

  beforeEach(() => {
    vi.clearAllMocks()

    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      value: vi.fn(() => 'blob:builder-pane'),
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
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders pane title in the header', () => {
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={vi.fn()}
      />
    )

    expect(screen.getByText('First Message')).toBeInTheDocument()
  })

  it('renders a code editor area', () => {
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={vi.fn()}
      />
    )

    expect(screen.getByRole('textbox', { name: /first message editor/i })).toBeInTheDocument()
  })

  it('calls onChange when content is edited', () => {
    const onChange = vi.fn()
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={onChange}
      />
    )

    fireEvent.change(screen.getByRole('textbox', { name: /first message editor/i }), {
      target: { value: '# Updated intro' },
    })

    expect(onChange).toHaveBeenCalledWith('# Updated intro')
  })

  it('renders a download button', () => {
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={vi.fn()}
      />
    )

    expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument()
  })

  it('clicking download creates and downloads a blob file with the correct name', async () => {
    const user = userEvent.setup()
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={vi.fn()}
      />
    )

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(downloadAnchor.download).toBe('first-message.md')
    expect(downloadAnchor.click).toHaveBeenCalled()
  })

  it('supports readonly mode', () => {
    render(
      <BuilderPane
        title="First Message"
        filename="first-message.md"
        content="# Welcome"
        onChange={vi.fn()}
        readOnly={true}
      />
    )

    expect(screen.getByRole('textbox', { name: /first message editor/i })).toHaveAttribute('readonly')
  })
})
