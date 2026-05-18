/**
 * MnesOS E2E – Happy Path: Auth → New Game → First Turn
 *
 * MnesOS-260507-03
 *
 * Flow:
 *   1. User lands on the app (Library view).
 *   2. User opens Settings and enters their User ID + API key.
 *   3. User creates a Persona.
 *   4. User starts a new game (picks cartridge + persona).
 *   5. User sends a first turn message.
 *   6. Narrator response appears in the chat pane.
/**
 * MnesOS E2E – Happy Path: Auth → New Game → First Turn
 *
 * MnesOS-260507-03
 *
 * Flow:
 *   1. User lands on the app (Library view).
 *   2. User opens Settings and enters their User ID + API key.
 *   3. User creates a Persona.
 *   4. User starts a new game (picks cartridge + persona).
 *   5. User sends a first turn message.
 *   6. Narrator response appears in the chat pane.
 *
 * The backend is seeded via direct API calls, and OpenRouter is mocked locally.
 */

import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { test, expect, request } from '@playwright/test'

const BASE_API = 'http://localhost:8000/api'
const API_KEY = 'sk-or-mock'
const TEST_USERNAME = `e2e-user-${randomUUID()}`
const TEST_EMAIL = `${TEST_USERNAME}@example.invalid`
const E2E_DB_PATH = resolve(process.cwd(), '..', 'artifacts', 'mnesos-e2e.db')
const E2E_DB_FILES = [E2E_DB_PATH, `${E2E_DB_PATH}-shm`, `${E2E_DB_PATH}-wal`]

let seededUserId = ''
let seededInstanceId = ''
let seededTurnId = ''

async function prepareE2eDbFiles() {
  await mkdir(resolve(E2E_DB_PATH, '..'), { recursive: true })
  await Promise.all(E2E_DB_FILES.map(async (filePath) => rm(filePath, { force: true })))
  await writeFile(E2E_DB_PATH, '')
}

async function cleanupE2eDbFiles() {
  await Promise.all(E2E_DB_FILES.map(async (filePath) => rm(filePath, { force: true })))
}

async function seedUser(apiCtx: Awaited<ReturnType<typeof request.newContext>>) {
  const response = await apiCtx.post(`${BASE_API}/users`, {
    data: {
      username: TEST_USERNAME,
      email: TEST_EMAIL,
      password: 'e2e-passw0rd',
      role: 'PLAYER',
    },
  })
  expect(response.ok()).toBe(true)
  const user = await response.json()
  return user.id as string
}

async function seedCartridge(apiCtx: Awaited<ReturnType<typeof request.newContext>>, userId: string) {
  const response = await apiCtx.post(`${BASE_API}/cartridges`, {
    headers: { 'X-User-Id': userId, 'Content-Type': 'application/json' },
    data: {
      title: 'E2E Test Cartridge',
      description: 'Auto-seeded',
      genre: 'Test',
      visibility: 'PUBLIC',
    },
  })
  expect(response.ok()).toBe(true)
  const cartridge = await response.json()

  const cartridgeRoot = resolve(process.cwd(), '..', 'cartridges', 'generic-rpg')
  const versionResponse = await apiCtx.post(`${BASE_API}/cartridges/${cartridge.id}/versions`, {
    headers: { 'X-User-Id': userId },
    multipart: {
      version_tag: '1.0.0-e2e',
      yare_file: {
        name: 'yare.yaml',
        mimeType: 'text/yaml',
        buffer: readFileSync(resolve(cartridgeRoot, 'yare.yaml')),
      },
      lore_file: {
        name: 'bot_lore.md',
        mimeType: 'text/markdown',
        buffer: readFileSync(resolve(cartridgeRoot, 'bot_lore.md')),
      },
      directives_file: {
        name: 'prompt_directives.yaml',
        mimeType: 'text/yaml',
        buffer: readFileSync(resolve(cartridgeRoot, 'prompt_directives.yaml')),
      },
    },
  })
  expect(versionResponse.ok()).toBe(true)
  const version = await versionResponse.json()
  return { cartridge, version }
}

async function seedPersona(apiCtx: Awaited<ReturnType<typeof request.newContext>>, userId: string) {
  const response = await apiCtx.post(`${BASE_API}/personas`, {
    headers: { 'X-User-Id': userId, 'Content-Type': 'application/json' },
    data: {
      name: 'E2E Hero',
      pronoun_sub: 'they',
      pronoun_obj: 'them',
      pronoun_poss: 'their',
      pronoun_poss_obj: 'theirs',
      appearance: 'Brave adventurer',
      background: 'Unknown',
      personality: 'Curious',
    },
  })
  expect(response.ok()).toBe(true)
  return response.json()
}

async function seedGameInstance(
  apiCtx: Awaited<ReturnType<typeof request.newContext>>,
  userId: string,
  versionId: string,
  personaId: string,
) {
  const response = await apiCtx.post(`${BASE_API}/instances`, {
    headers: { 'X-User-Id': userId, 'Content-Type': 'application/json' },
    data: {
      version_id: versionId,
      persona_id: personaId,
    },
  })
  expect(response.ok()).toBe(true)
  return response.json() as Promise<{ instance_id: string; turn_id: string | null }>
}

test.describe('Happy Path – Auth → New Game → First Turn', () => {
  test.beforeAll(async () => {
    await prepareE2eDbFiles()
    const apiCtx = await request.newContext()
    seededUserId = await seedUser(apiCtx)
    const { version } = await seedCartridge(apiCtx, seededUserId)
    const persona = await seedPersona(apiCtx, seededUserId)
    const instance = await seedGameInstance(apiCtx, seededUserId, version.id, persona.id)
    seededInstanceId = instance.instance_id
    seededTurnId = instance.turn_id ?? ''
    await apiCtx.dispose()
  })

  test.afterAll(async () => {
    await cleanupE2eDbFiles()
  })

  test('1 – App loads and shows the Library view', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('MnesOS')).toBeVisible()
    await expect(page.getByText('Cartridge Library')).toBeVisible()
  })

  test('2 – User can open Settings and save credentials', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /settings/i }).click()
    await page.getByText('Advanced: Manual API Key (BYOK)').click()
    await page.getByPlaceholder('sk-or-...').fill(API_KEY)
    await page.getByPlaceholder('user-uuid').fill(seededUserId)
    await page.getByRole('button', { name: /save/i }).click()
    await expect(page.getByPlaceholder('sk-or-...')).not.toBeVisible()
  })

  test('3 – User can start a new game and send first turn', async ({ page }) => {
    await page.goto('/')

    await page.evaluate(
      ([userId, instanceId, apiKey]) => {
        localStorage.setItem('mnesos_user_id', userId)
        localStorage.setItem('mnesos_instance_id', instanceId)
        localStorage.setItem('mnesos_openrouter_key', apiKey)
      },
      [seededUserId, seededInstanceId, API_KEY],
    )
    await page.reload()

    await page.evaluate((turnId) => {
      window.dispatchEvent(new CustomEvent('mnesos-play-instance', { detail: { turn_id: turnId || undefined } }))
    }, seededTurnId)

    await expect(page.locator('.chat-pane')).toBeVisible({ timeout: 15000 })

    await page.getByPlaceholder('What do you do?').fill('Look around.')
    await page.locator('.btn-send').click()

    await expect(page.locator('.chat-narrator')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.chat-narrator .chat-text').first()).not.toBeEmpty()
  })
})

test.describe('Smoke – App loads without credentials', () => {
  test('app renders the header', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('MnesOS')).toBeVisible()
  })

  test('Settings modal opens and closes', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /settings/i }).click()
    await expect(page.getByRole('button', { name: /Connect OpenRouter/i })).toBeVisible()
    await page.getByRole('button', { name: /cancel/i }).click()
    await expect(page.getByRole('button', { name: /Connect OpenRouter/i })).not.toBeVisible()
  })

  test('navigation between views works', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /play/i }).click()
    await expect(page.getByText('Start New Game')).toBeVisible()
    await page.getByRole('button', { name: /library/i }).click()
    await expect(page.getByText('Cartridge Library')).toBeVisible()
  })
})
