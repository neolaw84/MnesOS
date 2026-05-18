import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  processTurn,
  injectState,
  createGameInstance,
  listInstances,
  deleteInstance,
  createSave,
  listSaves,
  listCartridges,
  createCartridge,
  getCartridge,
  deleteCartridge,
  updateCartridge,
  listCartridgeVersions,
  getCartridgeVersion,
  uploadCartridgeVersion,
  listPersonas,
  createPersona,
  getPersona,
  updatePersona,
  deletePersona,
  getGameState,
  setOpenRouterKey,
  setUserId,
} from '../../api/client'

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  })
}

describe('apiFetch – success paths', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('processTurn posts to correct URL and returns response', async () => {
    const expected = { turn_id: 't-1', narrator_response: 'You enter the cave.', yare_delta: {} }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await processTurn('inst-1', { user_input: 'go north' })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances/inst-1/turn')
    expect(calls[0][1].method).toBe('POST')
  })

  it('injectState posts to inject endpoint', async () => {
    const expected = { turn_id: 't-2' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await injectState('inst-1', { yare_delta: { hp: 10 } })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances/inst-1/inject')
  })

  it('createGameInstance posts to /api/instances', async () => {
    const expected = { instance_id: 'new-inst', turn_id: 't-3' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await createGameInstance({ version_id: 'v-1', persona_id: 'p-1' })
    expect(result).toEqual(expected)
  })

  it('listInstances calls GET /api/instances', async () => {
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listInstances()
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances')
    expect(calls[0][1].method).toBe('GET')
  })

  it('createSave posts to saves endpoint', async () => {
    const expected = { save_id: 's-1', created_at: '2026-01-01T00:00:00Z' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await createSave('inst-1', { turn_log_id: 't-1', label: 'checkpoint' })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances/inst-1/saves')
  })

  it('listSaves calls GET on saves endpoint', async () => {
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listSaves('inst-1')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances/inst-1/saves')
    expect(calls[0][1].method).toBe('GET')
  })

  it('listCartridges calls GET /api/cartridges', async () => {
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listCartridges()
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges')
  })

  it('listPersonas calls GET /api/personas', async () => {
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listPersonas()
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/personas')
  })

  it('createPersona posts to /api/personas', async () => {
    const expected = { id: 'p-1', name: 'Hero', description: '', user_id: 'u-1' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await createPersona({ name: 'Hero', pronoun_sub: 'they', pronoun_obj: 'them', pronoun_poss: 'their', pronoun_poss_obj: 'theirs', appearance: '', background: '', personality: '' })
    expect(result).toEqual(expected)
  })

  it('attaches X-OpenRouter-Key header when key is set', async () => {
    setOpenRouterKey('sk-or-test')
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listCartridges()
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][1].headers['X-OpenRouter-Key']).toBe('sk-or-test')
  })

  it('attaches X-User-Id header when userId is set', async () => {
    setUserId('uid-99')
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listCartridges()
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][1].headers['X-User-Id']).toBe('uid-99')
  })
})

describe('apiFetch – error paths', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', mockFetch(404, { detail: 'Not found' }))
    await expect(listCartridges()).rejects.toThrow('API 404')
  })

  it('throws on 500 response', async () => {
    vi.stubGlobal('fetch', mockFetch(500, 'Internal Server Error'))
    await expect(processTurn('inst-1', { user_input: 'hello' })).rejects.toThrow('API 500')
  })
})

describe('Cartridge API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('createCartridge posts to /api/cartridges', async () => {
    const expected = { id: 'c-1', creator_id: 'u-1', title: 'Epic Quest', description: '', genre: 'Fantasy', visibility: 'PUBLIC' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await createCartridge({ title: 'Epic Quest', description: '', genre: 'Fantasy', visibility: 'PUBLIC' })
    expect(result).toEqual(expected)
  })

  it('getCartridge calls GET /api/cartridges/:id', async () => {
    const expected = { id: 'c-1', creator_id: 'u-1', title: 'Epic Quest', description: '', genre: 'Fantasy', visibility: 'PUBLIC' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await getCartridge('c-1')
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1')
  })

  it('deleteCartridge calls DELETE /api/cartridges/:id', async () => {
    vi.stubGlobal('fetch', mockFetch(204, null))
    await deleteCartridge('c-1')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1')
    expect(calls[0][1].method).toBe('DELETE')
  })

  it('deleteCartridge throws on error', async () => {
    vi.stubGlobal('fetch', mockFetch(404, 'not found'))
    await expect(deleteCartridge('c-1')).rejects.toThrow('API 404')
  })

  it('updateCartridge calls PUT /api/cartridges/:id', async () => {
    const expected = { id: 'c-1', creator_id: 'u-1', title: 'New Title', description: '', genre: 'Fantasy', visibility: 'PUBLIC' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await updateCartridge('c-1', { title: 'New Title' })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][1].method).toBe('PUT')
  })

  it('listCartridgeVersions calls GET /api/cartridges/:id/versions', async () => {
    vi.stubGlobal('fetch', mockFetch(200, []))
    await listCartridgeVersions('c-1')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/versions')
  })

  it('getCartridgeVersion calls GET /api/cartridges/:id/versions/:vid', async () => {
    const expected = { id: 'v-1', cartridge_id: 'c-1', version_tag: '1.0.0', created_at: '' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await getCartridgeVersion('c-1', 'v-1')
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/versions/v-1')
  })

  it('uploadCartridgeVersion posts FormData with zipFile', async () => {
    const expected = { id: 'v-2', cartridge_id: 'c-1', version_tag: '2.0.0', created_at: '' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(expected),
    }))
    const zipFile = new File(['content'], 'game.zip', { type: 'application/zip' })
    const result = await uploadCartridgeVersion('c-1', '2.0.0', { zipFile })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/cartridges/c-1/versions')
  })

  it('uploadCartridgeVersion posts individual files when no zipFile', async () => {
    const expected = { id: 'v-3', cartridge_id: 'c-1', version_tag: '3.0.0', created_at: '' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(expected),
    }))
    const yareFile = new File(['yare'], 'yare.yaml', { type: 'text/yaml' })
    const loreFile = new File(['lore'], 'bot_lore.md', { type: 'text/markdown' })
    const directivesFile = new File(['director: {}'], 'prompt_directives.yaml', { type: 'text/yaml' })
    const firstMessageFile = new File(['hello'], 'first-message.md', { type: 'text/markdown' })
    await uploadCartridgeVersion('c-1', '3.0.0', { yareFile, loreFile, directivesFile, firstMessageFile })
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    const formData = calls[0][1].body as FormData
    expect(formData.get('yare_file')).toBeTruthy()
    expect(formData.get('lore_file')).toBeTruthy()
    expect(formData.get('directives_file')).toBeTruthy()
    expect(formData.get('first_message_file')).toBeTruthy()
  })

  it('uploadCartridgeVersion throws on error', async () => {
    vi.stubGlobal('fetch', mockFetch(400, 'Bad Request'))
    await expect(uploadCartridgeVersion('c-1', '1.0', {})).rejects.toThrow('API 400')
  })
})

describe('Persona extended API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('getPersona calls GET /api/personas/:id', async () => {
    const expected = { id: 'p-1', user_id: 'u-1', name: 'Hero', pronoun_sub: 'they', pronoun_obj: 'them', pronoun_poss: 'their', pronoun_poss_obj: 'theirs', appearance: '', background: '', personality: '' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await getPersona('p-1')
    expect(result).toEqual(expected)
  })

  it('updatePersona calls PUT /api/personas/:id', async () => {
    const expected = { id: 'p-1', user_id: 'u-1', name: 'Hero Updated', pronoun_sub: 'they', pronoun_obj: 'them', pronoun_poss: 'their', pronoun_poss_obj: 'theirs', appearance: '', background: '', personality: '' }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await updatePersona('p-1', { name: 'Hero Updated' })
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][1].method).toBe('PUT')
  })

  it('deletePersona calls DELETE /api/personas/:id', async () => {
    vi.stubGlobal('fetch', mockFetch(204, null))
    await deletePersona('p-1')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/personas/p-1')
    expect(calls[0][1].method).toBe('DELETE')
  })

  it('deletePersona throws on error', async () => {
    vi.stubGlobal('fetch', mockFetch(404, 'not found'))
    await expect(deletePersona('p-1')).rejects.toThrow('API 404')
  })

  it('deleteInstance calls DELETE /api/instances/:id', async () => {
    vi.stubGlobal('fetch', mockFetch(204, null))
    await deleteInstance('inst-1')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toBe('/api/instances/inst-1')
    expect(calls[0][1].method).toBe('DELETE')
  })

  it('deleteInstance throws on error', async () => {
    vi.stubGlobal('fetch', mockFetch(500, 'error'))
    await expect(deleteInstance('inst-1')).rejects.toThrow('API 500')
  })

  it('getGameState calls GET /api/instances/:id/state', async () => {
    const expected = { bot_memory: {}, client_messages: [] }
    vi.stubGlobal('fetch', mockFetch(200, expected))
    const result = await getGameState('inst-1', 't-1')
    expect(result).toEqual(expected)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
    expect(calls[0][0]).toContain('/api/instances/inst-1/state')
  })
})

