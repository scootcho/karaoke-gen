import { defineConfig, devices } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// Load .env.local file if it exists (for KARAOKE_ACCESS_TOKEN)
const envLocalPath = path.join(__dirname, '.env.local');
if (fs.existsSync(envLocalPath)) {
  const envContent = fs.readFileSync(envLocalPath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#')) {
      const [key, ...valueParts] = trimmed.split('=');
      const value = valueParts.join('=');
      if (key && value && !process.env[key]) {
        process.env[key] = value;
      }
    }
  }
}

/**
 * Playwright configuration for karaoke-gen frontend E2E tests.
 *
 * DEFAULT: Runs regression tests with mocked API (CI-safe, offline).
 * Tests run against the local dev server (localhost:3000) with mocked API responses.
 *
 * For production tests: use playwright.production.config.ts
 * For fixture recording: use playwright.record.config.ts
 */
export default defineConfig({
  testDir: './e2e/regression',

  // Run tests in parallel for faster CI
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Single worker for now to avoid conflicts with real backend
  workers: 1,

  // Reporter to use
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  // Shared settings for all tests
  use: {
    // Base URL for the local dev server
    baseURL: 'http://localhost:3000',

    // Collect trace on failure for debugging
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video recording (set to 'on' to always record, 'on-first-retry' for failures only)
    video: 'on',

    // Increase timeout for real API calls
    actionTimeout: 30000,

    // Log network requests
    extraHTTPHeaders: {
      'x-playwright-test': 'true',
    },
  },

  // Longer timeout for tests hitting real backend
  timeout: 120000, // 2 minutes per test

  // Expect timeout for assertions
  expect: {
    timeout: 30000, // 30 seconds for expects
  },

  // Configure projects (browsers)
  // Regression tests only use Chromium for CI speed
  // Mobile tests set their own viewport sizes within tests
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Run local dev server before starting tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
