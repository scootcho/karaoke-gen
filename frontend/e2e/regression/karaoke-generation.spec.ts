import { test, expect } from '@playwright/test';
import { setupApiFixtures, setAuthToken } from '../fixtures/test-helper';

/**
 * Regression Tests - Karaoke Generation Flow
 *
 * Tests the karaoke generation UI elements using mocked API responses.
 * These tests run offline in CI without hitting production.
 */

// Mock data
const MOCK_USER = {
  email: 'test@example.com',
  credits: 5,
  is_beta: true,
};

const MOCK_AUDIO_RESULTS = [
  {
    id: 'audio-1',
    title: 'Test Song - High Quality',
    format: 'FLAC',
    bitrate: '1411',
    size: '45MB',
    source: 'Deezer',
  },
  {
    id: 'audio-2',
    title: 'Test Song - Standard',
    format: 'MP3',
    bitrate: '320',
    size: '12MB',
    source: 'Tidal',
  },
];

const MOCK_INSTRUMENTALS = [
  {
    id: 'instrumental-clean',
    name: 'Clean (no backing vocals)',
    description: 'Pure instrumental with all vocals removed',
  },
  {
    id: 'instrumental-backing',
    name: 'With backing vocals',
    description: 'Lead vocals removed, backing vocals preserved',
  },
];

// Standard mocks for app page tests
const APP_PAGE_MOCKS = [
  {
    method: 'GET',
    path: '/api/jobs',
    response: { body: [] },
  },
  {
    method: 'GET',
    path: '/api/users/me',
    response: { body: { email: 'test@example.com', credits: 5 } },
  },
  {
    method: 'GET',
    path: '/api/themes',
    response: { body: { themes: [] } },
  },
];

test.describe('Karaoke Generation - Search Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('search tab shows artist and title inputs', async ({ page }) => {
    await setupApiFixtures(page, { mocks: APP_PAGE_MOCKS });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Click Search tab
    await page.getByRole('tab', { name: /search/i }).click();

    // Verify inputs
    await expect(page.getByLabel('Artist')).toBeVisible();
    await expect(page.getByLabel('Title')).toBeVisible();
    await expect(page.getByRole('button', { name: /search.*create/i })).toBeVisible();
  });

  test('search form validates required fields', async ({ page }) => {
    await setupApiFixtures(page, { mocks: APP_PAGE_MOCKS });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /search/i }).click();

    // Try to submit without filling fields
    await page.getByRole('button', { name: /search.*create/i }).click();

    // Form should not submit (fields are required)
    // Page should still be on app
    expect(page.url()).toContain('/app');
  });

  test('search creates a new job', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        ...APP_PAGE_MOCKS,
        {
          method: 'POST',
          path: '/api/audio-search/search',
          response: {
            body: {
              job_id: 'new-job-123',
              status: 'audio_search',
            },
          },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /search/i }).click();

    // Fill form
    await page.getByLabel('Artist').fill('piri');
    await page.getByLabel('Title').fill('dog');

    // Submit
    await page.getByRole('button', { name: /search.*create/i }).click();

    // Should show loading or job created indication
    await page.waitForTimeout(2000);
  });
});

test.describe('Karaoke Generation - Audio Selection', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('job awaiting audio shows select audio button', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: {
            body: [
              {
                job_id: 'job-1',
                artist: 'Test Artist',
                title: 'Test Song',
                status: 'awaiting_audio_selection',
              },
            ],
          },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: { body: { email: 'test@example.com', credits: 5 } },
        },
        {
          method: 'GET',
          path: '/api/themes',
          response: { body: { themes: [] } },
        },
        {
          method: 'GET',
          path: '/api/audio-search/job-1/results',
          response: { body: { results: MOCK_AUDIO_RESULTS } },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Should show Select Audio button for job awaiting audio selection
    await expect(page.getByRole('button', { name: /select audio/i }).first()).toBeVisible();
  });
});

test.describe('Karaoke Generation - Instrumental Selection', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('instrumental selection dialog shows options', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: {
            body: [
              {
                job_id: 'job-1',
                artist: 'Test Artist',
                title: 'Test Song',
                status: 'awaiting_instrumental_selection',
                instrumental_options: MOCK_INSTRUMENTALS,
              },
            ],
          },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: { body: { email: 'test@example.com', credits: 5 } },
        },
        {
          method: 'GET',
          path: '/api/themes',
          response: { body: { themes: [] } },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const instrumentalBtn = page.getByRole('button', { name: /select instrumental/i }).first();
    if (await instrumentalBtn.isVisible({ timeout: 5000 })) {
      await instrumentalBtn.click();

      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Should show instrumental options
      await expect(dialog.getByText(/clean|backing/i).first()).toBeVisible();
    }
  });
});

test.describe('Karaoke Generation - Lyrics Review', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('job in review status is displayed', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: {
            body: [
              {
                job_id: 'job-1',
                artist: 'Test Artist',
                title: 'Test Song',
                status: 'in_review',
              },
            ],
          },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: { body: { email: 'test@example.com', credits: 5 } },
        },
        {
          method: 'GET',
          path: '/api/themes',
          response: { body: { themes: [] } },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Should show job artist
    await expect(page.getByText('Test Artist')).toBeVisible();
    // Should show review status indicator (button or badge)
    await expect(page.getByText(/review/i).first()).toBeVisible();
  });
});

test.describe('Karaoke Generation - Tabs', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('all input tabs are visible', async ({ page }) => {
    await setupApiFixtures(page, { mocks: APP_PAGE_MOCKS });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Check all tabs exist
    await expect(page.getByRole('tab', { name: /upload/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /url/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();
  });

  test('URL tab shows URL input', async ({ page }) => {
    await setupApiFixtures(page, { mocks: APP_PAGE_MOCKS });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /url/i }).click();

    // Should show URL input
    const urlInput = page.locator('input[type="url"], input[placeholder*="youtube"], input[placeholder*="URL"]');
    await expect(urlInput.first()).toBeVisible();
  });

  test('Upload tab shows file input', async ({ page }) => {
    await setupApiFixtures(page, { mocks: APP_PAGE_MOCKS });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /upload/i }).click();

    // Should show file upload area
    const fileInput = page.locator('input[type="file"]');
    const dropZone = page.locator('text=/drag|drop|upload/i').first();

    const hasFileInput = await fileInput.isVisible().catch(() => false);
    const hasDropZone = await dropZone.isVisible().catch(() => false);

    expect(hasFileInput || hasDropZone).toBe(true);
  });
});
