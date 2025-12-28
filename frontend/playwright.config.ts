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
 * Tests run against the local dev server (localhost:3000) which proxies
 * API requests to the real cloud backend (api.nomadkaraoke.com).
 */
export default defineConfig({
  testDir: './e2e',

  // Run tests in parallel
  fullyParallel: false, // Sequential for now since tests may share state

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
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Mobile device testing
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 14'] },
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
