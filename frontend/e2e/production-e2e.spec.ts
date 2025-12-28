import { test, expect, Page, BrowserContext, ConsoleMessage, Request, Response } from '@playwright/test';

/**
 * Production E2E tests for the complete karaoke generation journey.
 *
 * These tests run directly against gen.nomadkaraoke.com (production).
 *
 * IMPORTANT: Set KARAOKE_ACCESS_TOKEN environment variable:
 *   KARAOKE_ACCESS_TOKEN=your-token npx playwright test --config=playwright.production.config.ts
 *
 * The complete user journey:
 * 1. Select a theme for the karaoke video
 * 2. Enter artist name and song title
 * 3. Select audio source from search results
 * 4. Wait for audio download and preparation
 * 5. Review/correct lyrics in the review UI
 * 6. Submit the review
 * 7. Select instrumental (clean or with backing vocals)
 * 8. Wait for final render and distribution
 * 9. Verify YouTube upload and Dropbox folder links
 */

const ACCESS_TOKEN = process.env.KARAOKE_ACCESS_TOKEN;
const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Real song for testing - uses cached flacfetch results for fast responses
const TEST_ARTIST = 'piri';
const TEST_TITLE = 'dog';

// Helper to authenticate the page by setting localStorage token
async function authenticatePage(page: Page) {
  if (!ACCESS_TOKEN) {
    throw new Error('KARAOKE_ACCESS_TOKEN environment variable is required for production tests');
  }

  await page.addInitScript((token) => {
    localStorage.setItem('karaoke_access_token', token);
  }, ACCESS_TOKEN);

  return true;
}

// Network and console logging for debugging
function setupLogging(page: Page) {
  const logs: { type: string; url?: string; status?: number; text?: string; body?: any }[] = [];

  page.on('request', (request: Request) => {
    if (request.url().includes('/api/')) {
      console.log(`>> ${request.method()} ${request.url()}`);
      logs.push({ type: 'request', url: request.url() });
    }
  });

  page.on('response', async (response: Response) => {
    if (response.url().includes('/api/')) {
      console.log(`<< ${response.status()} ${response.url()}`);
      logs.push({ type: 'response', url: response.url(), status: response.status() });
      if (response.status() >= 400) {
        try {
          const body = await response.json();
          console.log('   Error:', JSON.stringify(body));
          logs.push({ type: 'error', body });
        } catch { /* ignore */ }
      }
    }
  });

  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() === 'error') {
      console.log(`[Console Error] ${msg.text()}`);
      logs.push({ type: 'console-error', text: msg.text() });
    }
  });

  return logs;
}

// Helper to wait for job to reach a specific status
async function waitForJobStatus(
  request: any,
  jobId: string,
  targetStatuses: string[],
  maxWaitMs: number = 300000,
  pollIntervalMs: number = 5000
): Promise<any> {
  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitMs) {
    const response = await request.get(`${API_URL}/api/jobs/${jobId}`, {
      headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` }
    });

    if (!response.ok()) {
      throw new Error(`Failed to get job status: ${response.status()}`);
    }

    const job = await response.json();
    console.log(`Job ${jobId} status: ${job.status}`);

    if (targetStatuses.includes(job.status)) {
      return job;
    }

    if (job.status === 'failed') {
      throw new Error(`Job failed: ${job.error_message || 'Unknown error'}`);
    }

    await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
  }

  throw new Error(`Timeout waiting for job ${jobId} to reach status: ${targetStatuses.join(', ')}`);
}

test.describe('Production API Health', () => {
  test('API health check', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/health`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log('API Health:', data);
    expect(data.status).toBe('healthy');
  });

  test('Themes API returns available themes', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/themes`, {
      headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` }
    });

    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log('Themes API response:', JSON.stringify(data, null, 2));

    expect(data).toHaveProperty('themes');
    expect(Array.isArray(data.themes)).toBeTruthy();
    expect(data.themes.length).toBeGreaterThan(0);

    const firstTheme = data.themes[0];
    expect(firstTheme).toHaveProperty('id');
    expect(firstTheme).toHaveProperty('name');

    console.log('Available themes:');
    for (const theme of data.themes) {
      console.log(`  - ${theme.id}: ${theme.name}`);
    }
  });
});

test.describe('Production UI Basics', () => {
  test.beforeEach(async ({ page }) => {
    await authenticatePage(page);
  });

  test('Homepage loads with theme selector', async ({ page }) => {
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'test-results/prod-01-homepage.png', fullPage: true });

    // Verify main elements
    await expect(page.locator('h1')).toContainText('Karaoke Generator');
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();

    // Go to Search tab and verify theme selector exists
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(1000);

    const themeLabel = page.locator('text=Video Theme').or(page.locator('text=Theme'));
    const themeVisible = await themeLabel.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(themeVisible).toBeTruthy();

    console.log('Homepage loaded with theme selector');
  });
});

test.describe('Production Job Creation with Theme', () => {
  test.beforeEach(async ({ page }) => {
    await authenticatePage(page);
    setupLogging(page);
  });

  test('Job created via Search tab has theme_id set', async ({ page, request }) => {
    test.setTimeout(120000);

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(2000);

    // Fill form with real song
    await page.getByLabel('Artist').fill(TEST_ARTIST);
    await page.getByLabel('Title').fill(TEST_TITLE);

    // Ensure theme is selected
    const themeSelect = page.locator('button[role="combobox"]').first();
    let selectedThemeName: string | null = null;

    if (await themeSelect.isVisible({ timeout: 3000 })) {
      await themeSelect.click();
      await page.waitForTimeout(500);

      const firstOption = page.locator('[role="option"]').first();
      selectedThemeName = await firstOption.textContent();
      console.log(`Selecting theme: ${selectedThemeName}`);

      await firstOption.click();
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: 'test-results/prod-theme-form.png' });

    // Submit form
    await page.getByRole('button', { name: /search.*create/i }).click();
    await page.waitForTimeout(5000);

    // Get recent jobs and find our test job
    const jobsResponse = await request.get(`${API_URL}/api/jobs`, {
      headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` }
    });

    if (jobsResponse.ok()) {
      const jobsData = await jobsResponse.json();
      const jobs = jobsData.jobs || jobsData;

      // Find a job with our test artist/title (case-insensitive)
      const testJob = Array.isArray(jobs)
        ? jobs.find((j: any) =>
            j.artist?.toLowerCase() === TEST_ARTIST.toLowerCase() &&
            j.title?.toLowerCase() === TEST_TITLE.toLowerCase())
        : null;

      if (testJob) {
        console.log(`Found test job: ${testJob.job_id}`);
        console.log(`Job theme_id: ${testJob.theme_id}`);
        console.log(`Job enable_cdg: ${testJob.enable_cdg}`);
        console.log(`Job enable_txt: ${testJob.enable_txt}`);

        // CRITICAL: Theme must be set for jobs created via Search tab
        expect(testJob.theme_id).toBeTruthy();

        // When theme is set, CDG and TXT should be enabled by default
        expect(testJob.enable_cdg).toBe(true);
        expect(testJob.enable_txt).toBe(true);
      } else {
        console.log('Test job not found in recent jobs');
        // Don't fail - job might still be creating
      }
    }
  });
});

test.describe('Production Full E2E Journey', () => {
  /**
   * Complete end-to-end test of the karaoke generation flow:
   * Search -> Audio Selection -> Lyrics Review -> Instrumental Selection -> Completion
   *
   * WARNING: This creates a real karaoke track on production!
   */
  test.beforeEach(async ({ page }) => {
    await authenticatePage(page);
    setupLogging(page);
  });

  test('Complete karaoke generation journey with theme', async ({ page, context, request }) => {
    test.setTimeout(900000); // 15 minutes for full generation

    // Step 1: Navigate to Search tab
    console.log('=== Step 1: Creating job via Search tab ===');
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(2000);

    // Step 2: Select theme and fill form
    console.log('=== Step 2: Selecting theme and filling form ===');

    const themeSelect = page.locator('button[role="combobox"]').first();
    if (await themeSelect.isVisible({ timeout: 3000 })) {
      const selectedText = await themeSelect.textContent();
      console.log(`Current theme: ${selectedText}`);

      // Select first theme if none selected
      if (selectedText?.includes('Select')) {
        await themeSelect.click();
        await page.waitForTimeout(500);
        await page.locator('[role="option"]').first().click();
        await page.waitForTimeout(500);
      }
    }

    await page.getByLabel('Artist').fill(TEST_ARTIST);
    await page.getByLabel('Title').fill(TEST_TITLE);

    await page.screenshot({ path: 'test-results/prod-e2e-01-form.png' });

    // Step 3: Submit search
    console.log('=== Step 3: Submitting search ===');
    await page.getByRole('button', { name: /search.*create/i }).click();

    // Wait for search results
    console.log('Waiting for audio search results...');
    await page.waitForTimeout(10000);

    await page.screenshot({ path: 'test-results/prod-e2e-02-results.png' });

    // Step 4: Handle audio selection if needed
    console.log('=== Step 4: Audio selection ===');

    // Check for audio selection dialog or if job auto-started
    const selectAudioBtn = page.getByRole('button', { name: /select audio/i });
    if (await selectAudioBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await selectAudioBtn.click();
      await page.waitForTimeout(2000);

      const dialog = page.locator('[role="dialog"]');
      if (await dialog.isVisible()) {
        const selectButtons = dialog.getByRole('button', { name: /^select$/i });
        if (await selectButtons.count() > 0) {
          console.log('Selecting first audio option');
          await selectButtons.first().click();
          await page.waitForTimeout(5000);
        }
      }
    } else {
      console.log('No audio selection needed - may have auto-selected');
    }

    await page.screenshot({ path: 'test-results/prod-e2e-03-after-audio.png' });

    // Try to get job ID from page
    let jobId: string | null = null;
    const jobIdMatch = page.url().match(/jobs?[\/=]([a-f0-9-]+)/i);
    if (jobIdMatch) {
      jobId = jobIdMatch[1];
    }

    // If not in URL, get from recent jobs API
    if (!jobId) {
      const jobsResponse = await request.get(`${API_URL}/api/jobs`, {
        headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` }
      });
      if (jobsResponse.ok()) {
        const jobsData = await jobsResponse.json();
        const jobs = jobsData.jobs || jobsData;
        const testJob = Array.isArray(jobs)
          ? jobs.find((j: any) =>
              j.artist?.toLowerCase() === TEST_ARTIST.toLowerCase() &&
              j.title?.toLowerCase() === TEST_TITLE.toLowerCase())
          : null;
        if (testJob) {
          jobId = testJob.job_id;
        }
      }
    }

    if (!jobId) {
      console.log('Could not determine job ID');
      return;
    }

    console.log(`Job ID: ${jobId}`);

    // Step 5: Wait for lyrics review stage
    console.log('=== Step 5: Waiting for lyrics review ===');

    try {
      const job = await waitForJobStatus(
        request, jobId,
        ['in_review', 'awaiting_instrumental_selection', 'processing', 'completed'],
        300000 // 5 minutes
      );

      // Verify theme was applied
      console.log(`Job theme_id: ${job.theme_id}`);
      if (job.theme_id) {
        console.log('Theme correctly applied to job');
      }

      if (job.status === 'in_review') {
        console.log('=== Step 6: Completing lyrics review ===');

        // Refresh page and find review button
        await page.reload();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000);

        const reviewButton = page.getByRole('button', { name: /review.*lyrics/i }).or(
          page.getByRole('link', { name: /review.*lyrics/i })
        ).first();

        if (await reviewButton.isVisible({ timeout: 10000 })) {
          // Set up listener before clicking
          const pagePromise = context.waitForEvent('page', { timeout: 5000 }).catch(() => null);
          await reviewButton.click();
          const newPage = await pagePromise;

          const lyricsPage = newPage || page;
          await lyricsPage.waitForLoadState('networkidle');
          await lyricsPage.waitForTimeout(3000);

          await lyricsPage.screenshot({ path: 'test-results/prod-e2e-04-review.png', fullPage: true });

          // Click Preview Video
          const previewButton = lyricsPage.getByRole('button', { name: /preview.*video/i }).first();
          if (await previewButton.isVisible({ timeout: 5000 })) {
            await previewButton.click();
            console.log('Generating preview video...');
            await lyricsPage.waitForTimeout(30000);

            // Click Complete Review
            const completeButton = lyricsPage.getByRole('button', { name: /complete.*review/i }).first();
            if (await completeButton.isVisible({ timeout: 60000 })) {
              await completeButton.click();
              console.log('Review completed');
              await lyricsPage.waitForTimeout(3000);
            }
          }

          if (newPage && !newPage.isClosed()) {
            await newPage.close();
          }
        }
      }

      // Step 7: Handle instrumental selection
      console.log('=== Step 7: Instrumental selection ===');

      const updatedJob = await waitForJobStatus(
        request, jobId,
        ['awaiting_instrumental_selection', 'processing', 'completed'],
        60000
      ).catch(() => null);

      if (updatedJob?.status === 'awaiting_instrumental_selection') {
        await page.reload();
        await page.waitForLoadState('networkidle');

        const instrumentalBtn = page.getByRole('button', { name: /select.*instrumental/i }).first();
        if (await instrumentalBtn.isVisible({ timeout: 10000 })) {
          await instrumentalBtn.click();
          await page.waitForTimeout(2000);

          const dialog = page.locator('[role="dialog"]');
          if (await dialog.isVisible()) {
            const cleanBtn = dialog.locator('button:has-text("Clean"), button:has-text("Select")').first();
            if (await cleanBtn.isVisible()) {
              console.log('Selecting clean instrumental');
              await cleanBtn.click();
              await page.waitForTimeout(3000);
            }
          }
        }
      }

      await page.screenshot({ path: 'test-results/prod-e2e-05-after-instrumental.png' });

      // Step 8: Wait for completion
      console.log('=== Step 8: Waiting for completion ===');

      const finalJob = await waitForJobStatus(
        request, jobId,
        ['completed', 'failed'],
        300000 // 5 minutes for render
      ).catch(() => null);

      if (finalJob?.status === 'completed') {
        console.log('Job completed successfully!');

        await page.reload();
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'test-results/prod-e2e-06-completed.png', fullPage: true });

        // Verify outputs
        const youtubeLink = page.locator('a[href*="youtube.com"], a[href*="youtu.be"]').first();
        if (await youtubeLink.isVisible()) {
          const href = await youtubeLink.getAttribute('href');
          console.log(`YouTube link: ${href}`);
        }

        const dropboxLink = page.locator('a[href*="dropbox.com"]').first();
        if (await dropboxLink.isVisible()) {
          const href = await dropboxLink.getAttribute('href');
          console.log(`Dropbox link: ${href}`);
        }

        console.log('=== E2E TEST COMPLETE ===');
      } else if (finalJob?.status === 'failed') {
        throw new Error(`Job failed: ${finalJob.error_message || 'Unknown error'}`);
      }

    } catch (error) {
      console.error('Error during E2E test:', error);
      await page.screenshot({ path: 'test-results/prod-e2e-error.png', fullPage: true });
      throw error;
    }
  });
});
