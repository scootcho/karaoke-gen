/**
 * Example E2E test demonstrating the API fixture system
 *
 * This test shows how to use the fixture system to run tests against
 * mock data instead of a real backend.
 *
 * Run in recording mode to capture new fixtures:
 *   RECORD_FIXTURES=true npm run test:e2e -- fixtures-example.spec.ts
 *
 * Then review and approve fixtures:
 *   npm run fixtures:review
 */

import { test, expect } from '@playwright/test';
import { setupApiFixtures, setupMocks, setAuthToken } from './fixtures';

test.describe('API Fixtures Example', () => {
  test('shows empty state when no jobs exist', async ({ page }) => {
    // Set up mock API responses (frontend uses /api/jobs, not /api/v1/jobs)
    await setupMocks(page, [
      {
        method: 'GET',
        path: '/api/jobs',
        response: { body: [] },
      },
    ]);

    // Set auth token before navigating
    await setAuthToken(page, 'test-token');

    await page.goto('/');

    // Verify the empty state message
    await expect(page.getByText(/No jobs yet/i)).toBeVisible();
  });

  test('shows jobs when they exist', async ({ page }) => {
    // Set up mock with sample job data (frontend uses /api/jobs)
    await setupMocks(page, [
      {
        method: 'GET',
        path: '/api/jobs',
        response: {
          body: [
            {
              job_id: 'job-123',
              title: 'Test Song',
              artist: 'Test Artist',
              status: 'completed',
              created_at: '2024-01-15T10:00:00Z',
              updated_at: '2024-01-15T10:05:00Z',
            },
          ],
        },
      },
    ]);

    await setAuthToken(page, 'test-token');
    await page.goto('/');

    // Verify job is displayed
    await expect(page.getByText('Test Song')).toBeVisible();
    await expect(page.getByText('Test Artist')).toBeVisible();
  });

  test.skip('shows error when API fails', async ({ page }) => {
    // NOTE: Currently the frontend doesn't display API errors visibly
    // This test is skipped until error handling UI is added
    await setupMocks(page, [
      {
        method: 'GET',
        path: '/api/jobs',
        response: {
          status: 500,
          body: { detail: 'Internal server error' },
        },
      },
    ]);

    await setAuthToken(page, 'test-token');
    await page.goto('/');

    // This would require the frontend to display API errors
    await expect(page.getByText(/error/i)).toBeVisible();
  });

  test('shows login prompt when not authenticated', async ({ page }) => {
    // No mock needed - just don't set auth token
    await page.goto('/');

    // Verify login prompt is shown (actual UI text)
    await expect(page.getByText(/Authentication Required/i)).toBeVisible();
  });

  test.skip('records real API responses when RECORD_FIXTURES=true', async ({ page }) => {
    // This test only runs in recording mode
    // It will capture actual API responses for review

    const api = await setupApiFixtures(page, {
      testFile: 'fixtures-example.spec.ts',
    });

    if (!api.isRecording) {
      test.skip();
      return;
    }

    await setAuthToken(page, process.env.TEST_ACCESS_TOKEN || 'your-token');
    await page.goto('/');

    // Perform actions that trigger API calls
    await page.waitForLoadState('networkidle');

    // Stop recording and show captured fixtures
    const fixtures = api.stopRecording();
    console.log(`Captured ${fixtures.length} API calls`);
  });
});
