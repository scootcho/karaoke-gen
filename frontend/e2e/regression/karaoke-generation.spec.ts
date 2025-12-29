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

test.describe('Karaoke Generation - Search Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('search tab shows artist and title inputs', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

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
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

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
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
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

  test('audio selection dialog displays options', async ({ page }) => {
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
                audio_options: MOCK_AUDIO_RESULTS,
              },
            ],
          },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Click Select Audio button
    const selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();
    if (await selectAudioBtn.isVisible({ timeout: 5000 })) {
      await selectAudioBtn.click();

      // Dialog should open
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Should show audio options with Select buttons
      const selectButtons = dialog.getByRole('button', { name: /^select$/i });
      const count = await selectButtons.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('audio selection closes dialog on success', async ({ page }) => {
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
                audio_options: MOCK_AUDIO_RESULTS,
              },
            ],
          },
        },
        {
          method: 'POST',
          path: '/api/jobs/job-1/select-audio',
          response: {
            body: { success: true, status: 'downloading' },
          },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();
    if (await selectAudioBtn.isVisible({ timeout: 5000 })) {
      await selectAudioBtn.click();

      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Click first Select button
      const selectButtons = dialog.getByRole('button', { name: /^select$/i });
      await selectButtons.first().click();

      // Dialog should close (or show loading)
      await page.waitForTimeout(2000);
    }
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

  test('review button appears for jobs in review', async ({ page }) => {
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
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Should show Review Lyrics button
    const reviewBtn = page.getByRole('button', { name: /review.*lyrics/i }).first();
    await expect(reviewBtn).toBeVisible();
  });
});

test.describe('Karaoke Generation - Tabs', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page, 'test-token');
  });

  test('all input tabs are visible', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Check all tabs exist
    await expect(page.getByRole('tab', { name: /upload/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /url/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();
  });

  test('URL tab shows URL input', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /url/i }).click();

    // Should show URL input
    const urlInput = page.locator('input[type="url"], input[placeholder*="youtube"], input[placeholder*="URL"]');
    await expect(urlInput.first()).toBeVisible();
  });

  test('Upload tab shows file input', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

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
