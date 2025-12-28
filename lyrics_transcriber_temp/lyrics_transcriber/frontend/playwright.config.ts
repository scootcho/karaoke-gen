import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for lyrics-transcriber frontend E2E tests.
 * Tests run against the local dev server (localhost:5173) served by vite.
 */
export default defineConfig({
  testDir: './e2e',

  // Run tests sequentially for now
  fullyParallel: false,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Single worker
  workers: 1,

  // Reporter to use
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  // Shared settings for all tests
  use: {
    // Base URL for the local dev server
    baseURL: 'http://localhost:5173',

    // Collect trace on failure for debugging
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'on-first-retry',

    // Increase timeout for complex interactions
    actionTimeout: 30000,
  },

  // Longer timeout for tests
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
  ],

  // Run local dev server before starting tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
