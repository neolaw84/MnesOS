import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const CONFIG_DIR = fileURLToPath(new URL('.', import.meta.url))
const REPO_ROOT = resolve(CONFIG_DIR, '..')
const PYTHON_BIN = process.env.PYTHON_BIN ?? (process.env.CI ? 'python' : resolve(REPO_ROOT, 'venv', 'bin', 'python'))
const E2E_DB_PATH = resolve(REPO_ROOT, 'artifacts', 'mnesos-e2e.db')
const STATIC_DIR = resolve(REPO_ROOT, 'src', 'MnesOS', 'static')
const MOCK_SERVER = resolve(CONFIG_DIR, 'e2e', 'mock-openrouter.py')

/**
 * Playwright E2E configuration for the MnesOS unified application.
 * The webServer block starts the OpenRouter mock + FastAPI backend.
 * FastAPI serves the built frontend from a staged static directory.
 *
 * See https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      // Local OpenRouter-compatible mock used by backend LLM clients
      command: `${PYTHON_BIN} ${MOCK_SERVER}`,
      url: 'http://127.0.0.1:8899/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      stdout: 'ignore',
      stderr: 'ignore',
    },
    {
      // FastAPI backend serving staged frontend assets (unified mode)
      command: `MNESOS_DB_PATH=${E2E_DB_PATH} MNESOS_STATIC_DIR=${STATIC_DIR} OPENROUTER_BASE_URL=http://127.0.0.1:8899/api/v1 ${PYTHON_BIN} -m uvicorn MnesOS.api.app:app --host 0.0.0.0 --port 8000`,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      stdout: 'ignore',
      stderr: 'ignore',
    },
  ],
})
