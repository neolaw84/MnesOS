import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  saveCartridgeVersion,
  loadDraft,
  saveDraft,
} from '../../api/client'

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  })
}

const mockPanes = {
  first_message: '# Welcome',
  prompt_directives: 'director:\n  tone: noir',
  yare_rules: 'state_schema: {}',
  yare_type: 'yaml' as const,
  bot_lore: 'The city remembers.',
}

describe('cartridge builder API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('saveCartridgeVersion posts to publish endpoint with version tag and panes', async () => {
    const expected = {
      id: 'v-1',
      cartridge_id: 'c-1',
      version_tag: '1.0.0',
      yare_spec: {},
      prompt_directives: {},
      bot_lore: mockPanes.bot_lore,
      first_message: mockPanes.first_message,
      checksum: 'abc123',
      published_at: '2026-01-01T00:00:00Z',
    }
    vi.stubGlobal('fetch', mockFetch(201, expected))

    const result = await saveCartridgeVersion('c-1', '1.0.0', mockPanes)

    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/versions/publish')
    expect(calls[0][1].method).toBe('POST')
    expect(JSON.parse(calls[0][1].body as string)).toEqual({
      version_tag: '1.0.0',
      ...mockPanes,
    })
  })

  it('loadDraft gets the latest cartridge draft', async () => {
    const expected = {
      cartridge_id: 'c-1',
      ...mockPanes,
    }
    vi.stubGlobal('fetch', mockFetch(200, expected))

    const result = await loadDraft('c-1')

    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/drafts/latest')
    expect(calls[0][1].method).toBe('GET')
  })

  it('saveDraft puts pane content to the draft endpoint', async () => {
    const expected = {
      cartridge_id: 'c-1',
      ...mockPanes,
    }
    vi.stubGlobal('fetch', mockFetch(200, expected))

    const result = await saveDraft('c-1', mockPanes)

    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/drafts')
    expect(calls[0][1].method).toBe('PUT')
    expect(JSON.parse(calls[0][1].body as string)).toEqual(mockPanes)
  })
})
