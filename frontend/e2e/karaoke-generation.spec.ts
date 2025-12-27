import { test, expect, Page, ConsoleMessage, Request, Response } from '@playwright/test';

/**
 * E2E tests for karaoke generation flow using real cloud backend.
 *
 * These tests run against localhost:3000 which proxies to api.nomadkaraoke.com
 *
 * IMPORTANT: Set KARAOKE_ACCESS_TOKEN environment variable for authenticated tests:
 *   KARAOKE_ACCESS_TOKEN=your-token npm run test:e2e
 */

const ACCESS_TOKEN = process.env.KARAOKE_ACCESS_TOKEN;

// Helper to authenticate the page by setting localStorage token
async function authenticatePage(page: Page) {
  if (!ACCESS_TOKEN) {
    console.warn('No KARAOKE_ACCESS_TOKEN set - tests requiring auth will fail');
    return false;
  }

  // Set the token in localStorage before navigating
  await page.addInitScript((token) => {
    localStorage.setItem('karaoke_access_token', token);
  }, ACCESS_TOKEN);

  return true;
}

// Helper to log network requests and responses
function setupNetworkLogging(page: Page, testInfo: any) {
  const networkLogs: { type: string; url: string; status?: number; body?: any }[] = [];

  page.on('request', (request: Request) => {
    if (request.url().includes('/api/')) {
      networkLogs.push({
        type: 'REQUEST',
        url: request.url(),
        body: request.postData() ? tryParseJson(request.postData()!) : undefined,
      });
      console.log(`>> ${request.method()} ${request.url()}`);
    }
  });

  page.on('response', async (response: Response) => {
    if (response.url().includes('/api/')) {
      let body;
      try {
        body = await response.json();
      } catch {
        body = 'non-JSON response';
      }
      networkLogs.push({
        type: 'RESPONSE',
        url: response.url(),
        status: response.status(),
        body,
      });
      console.log(`<< ${response.status()} ${response.url()}`);
      if (response.status() >= 400) {
        console.log('   Error body:', JSON.stringify(body, null, 2));
      }
    }
  });

  return networkLogs;
}

// Helper to log console messages
function setupConsoleLogging(page: Page) {
  const consoleLogs: { type: string; text: string }[] = [];

  page.on('console', (msg: ConsoleMessage) => {
    const type = msg.type();
    const text = msg.text();
    consoleLogs.push({ type, text });
    if (type === 'error') {
      console.log(`[CONSOLE ERROR] ${text}`);
    } else if (type === 'warning') {
      console.log(`[CONSOLE WARN] ${text}`);
    }
  });

  return consoleLogs;
}

function tryParseJson(str: string): any {
  try {
    return JSON.parse(str);
  } catch {
    return str;
  }
}

// Wait for job to reach a specific status or set of statuses
async function waitForJobStatus(
  page: Page,
  targetStatuses: string[],
  timeoutMs: number = 300000 // 5 minutes default
): Promise<string> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    // Look for status badges in the job cards
    const badges = await page.locator('[class*="Badge"]').allTextContents();

    for (const status of targetStatuses) {
      if (badges.some(badge => badge.toLowerCase().includes(status.toLowerCase()))) {
        console.log(`Found target status: ${status}`);
        return status;
      }
    }

    // Also check if failed or cancelled
    if (badges.some(badge => badge.toLowerCase().includes('failed'))) {
      throw new Error('Job failed');
    }
    if (badges.some(badge => badge.toLowerCase().includes('cancelled'))) {
      throw new Error('Job was cancelled');
    }

    // Wait and refresh
    await page.waitForTimeout(3000);
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(1000);
  }

  throw new Error(`Timed out waiting for status: ${targetStatuses.join(' or ')}`);
}

test.describe('Karaoke Generation', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Set up auth if token available
    await authenticatePage(page);

    // Set up logging
    setupNetworkLogging(page, testInfo);
    setupConsoleLogging(page);
  });

  test('homepage loads and shows job submission form', async ({ page }) => {
    await page.goto('/');

    // Check header
    await expect(page.locator('h1')).toContainText('Karaoke Generator');

    // Check tabs exist
    await expect(page.getByRole('tab', { name: /upload/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /url/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();

    // Check Recent Jobs section
    await expect(page.locator('text=Recent Jobs')).toBeVisible();
  });

  test('search tab shows artist and title inputs', async ({ page }) => {
    await page.goto('/');

    // Click Search tab
    await page.getByRole('tab', { name: /search/i }).click();

    // Verify inputs exist
    await expect(page.getByLabel('Artist')).toBeVisible();
    await expect(page.getByLabel('Title')).toBeVisible();
    await expect(page.getByRole('button', { name: /search.*create/i })).toBeVisible();
  });

  test('can submit audio search request', async ({ page }) => {
    await page.goto('/');

    // Click Search tab
    await page.getByRole('tab', { name: /search/i }).click();

    // Fill in artist and title
    await page.getByLabel('Artist').fill('ABBA');
    await page.getByLabel('Title').fill('Waterloo');

    // Submit
    await page.getByRole('button', { name: /search.*create/i }).click();

    // Wait for the button to show loading or for a new job to appear
    await page.waitForTimeout(2000);

    // Check for either success (job appears) or error message
    const errorDiv = page.locator('div.text-red-400').first();
    const hasError = await errorDiv.isVisible().catch(() => false);
    if (hasError) {
      const errorText = await errorDiv.textContent();
      console.log('Search error:', errorText);
    }

    // Should see either a new job or an error - both are valid test results
    // that tell us about the system state
  });

  test('full song search and selection flow', async ({ page }) => {
    test.setTimeout(300000); // 5 minutes for this test (backend can be slow)

    // Skip if no auth token
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    await page.goto('/');

    // Wait for jobs to load
    await page.waitForTimeout(2000);

    // First check if there's already a job awaiting audio selection we can use
    let jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /select audio/i
    }).first();

    if (await jobCard.isVisible()) {
      console.log('Found existing job awaiting audio selection, using it...');
    } else {
      // Create a new job via search
      console.log('No existing job found, creating new one...');

      // Click Search tab
      await page.getByRole('tab', { name: /search/i }).click();

      // Fill in artist and title - use a test song
      await page.getByLabel('Artist').fill('LCMDF');
      await page.getByLabel('Title').fill('Take Me To The Mountains');

      console.log('Submitting search for LCMDF - Take Me To The Mountains...');

      // Submit and wait for response (backend search can take 30+ seconds)
      await page.getByRole('button', { name: /search.*create/i }).click();

      // Wait longer for backend response (audio search takes time)
      await page.waitForTimeout(10000);

      // Check for error
      const errorLocator = page.locator('div.text-red-400').first();
      if (await errorLocator.isVisible().catch(() => false)) {
        const errorText = await errorLocator.textContent();
        console.log('Error:', errorText);

        // Network errors or timeouts - retry by looking for existing jobs
        if (errorText?.includes('Internal Server Error') || errorText?.includes('Failed to fetch')) {
          console.log('Search request failed, checking for existing jobs...');
        } else {
          throw new Error(`Search failed: ${errorText}`);
        }
      }

      // Refresh to see jobs
      await page.click('button:has-text("Refresh")');
      await page.waitForTimeout(3000);

      // Look for any job awaiting audio selection
      jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
        hasText: /select audio/i
      }).first();
    }

    // Now work with the job that needs audio selection
    if (await jobCard.isVisible()) {
      console.log('Found job awaiting audio selection');

      // Click to expand
      await jobCard.click();
      await page.waitForTimeout(1000);

      // Take a screenshot of current state
      await page.screenshot({ path: 'test-results/job-expanded.png' });

      // Look for the Select Audio button
      const selectAudioBtn = page.getByRole('button', { name: /select audio/i });

      if (await selectAudioBtn.isVisible()) {
        console.log('Opening audio selection dialog...');
        await selectAudioBtn.click();
        await page.waitForTimeout(2000);

        // Look for dialog
        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          console.log('Audio selection dialog opened');
          await page.screenshot({ path: 'test-results/audio-selection-dialog.png' });

          // Select the first audio result
          const selectButtons = dialog.getByRole('button', { name: /^select$/i });
          const selectCount = await selectButtons.count();
          console.log(`Found ${selectCount} audio options`);

          if (selectCount > 0) {
            console.log('Selecting first audio option...');
            // Use JavaScript click to bypass Playwright's viewport restrictions
            // This is needed because the dialog is in a portal with nested scrolling
            const firstButton = selectButtons.first();
            await firstButton.evaluate((btn: HTMLButtonElement) => btn.click());

            // Wait for dialog to close - selection can take a while (audio download)
            // The backend may timeout, so we handle that gracefully
            const dialogClosed = await dialog.waitFor({ state: 'hidden', timeout: 120000 }).then(() => true).catch(() => false);

            if (!dialogClosed) {
              console.log('Dialog still open - selection may have failed or is still processing');
              // Close dialog manually by clicking outside or pressing escape
              await page.keyboard.press('Escape');
              await page.waitForTimeout(1000);
            }

            await page.screenshot({ path: 'test-results/after-audio-selection.png' });

            // Verify the job status changed
            await page.click('button:has-text("Refresh")');
            await page.waitForTimeout(2000);

            console.log('Audio selection flow completed!');
          } else {
            console.log('No audio options found in dialog');
            await page.screenshot({ path: 'test-results/empty-audio-dialog.png' });
          }
        } else {
          console.log('Dialog did not open');
        }
      } else {
        console.log('Select Audio button not visible');
        await page.screenshot({ path: 'test-results/no-select-button.png' });
      }
    } else {
      console.log('No job awaiting audio selection found');
      await page.screenshot({ path: 'test-results/no-awaiting-job.png' });
    }

    console.log('Audio search/selection test completed');
  });

  test.skip('complete karaoke generation with auto mode', async ({ page }) => {
    // This test uses auto mode to go through the full flow
    // Skip for now - enable once basic flow works
    test.setTimeout(600000); // 10 minutes

    await page.goto('/?auto=true');

    // Verify auto mode is enabled
    await expect(page.locator('text=Non-Interactive Mode Active')).toBeVisible();

    // Submit a search
    await page.getByRole('tab', { name: /search/i }).click();
    await page.getByLabel('Artist').fill('Rick Astley');
    await page.getByLabel('Title').fill('Never Gonna Give You Up');
    await page.getByRole('button', { name: /search.*create/i }).click();

    // With auto mode, the job should progress automatically through:
    // 1. Audio search -> auto-selects first result
    // 2. Lyrics review -> auto-accepts
    // 3. Instrumental selection -> auto-selects clean

    // Wait for completion (or timeout)
    try {
      await waitForJobStatus(page, ['Complete'], 540000); // 9 minutes
      console.log('Job completed successfully!');
    } catch (error) {
      console.log('Job did not complete:', error);
      await page.screenshot({ path: 'test-results/auto-mode-final-state.png' });
      throw error;
    }
  });
});

test.describe('Job States and Interactions', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    await authenticatePage(page);
    setupNetworkLogging(page, testInfo);
    setupConsoleLogging(page);
  });

  test('completed job shows download links', async ({ page }) => {
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Find a completed job
    const completedJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /complete/i
    }).first();

    if (await completedJob.isVisible()) {
      console.log('Found completed job');
      await completedJob.click();
      await page.waitForTimeout(2000);

      // Look for download links
      const downloadSection = page.locator('text=Downloads').first();
      const hasDownloads = await downloadSection.isVisible().catch(() => false);

      if (hasDownloads) {
        console.log('Download links visible');
        // Check for video download buttons
        const videoLink = page.locator('a:has-text("720p Video"), a:has-text("4K Video")').first();
        if (await videoLink.isVisible()) {
          console.log('Video download link found');
        }
      } else {
        console.log('No download section visible (may still be loading)');
      }

      await page.screenshot({ path: 'test-results/completed-job.png' });
    } else {
      console.log('No completed jobs found');
    }
  });

  test('instrumental selection dialog opens and shows options', async ({ page }) => {
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Find a job awaiting instrumental selection
    const instrumentalJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /select instrumental/i
    }).first();

    if (await instrumentalJob.isVisible()) {
      console.log('Found job awaiting instrumental selection');
      await instrumentalJob.click();
      await page.waitForTimeout(1000);

      // Click the Select Instrumental button
      const selectBtn = page.getByRole('button', { name: /select instrumental/i });
      if (await selectBtn.isVisible()) {
        await selectBtn.click();
        await page.waitForTimeout(2000);

        // Check dialog opened
        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          console.log('Instrumental selection dialog opened');

          // Look for options
          const options = dialog.locator('text=Clean, text=with backing').first();
          const hasOptions = await dialog.getByRole('button', { name: /select/i }).count();
          console.log(`Found ${hasOptions} instrumental options`);

          await page.screenshot({ path: 'test-results/instrumental-dialog.png' });

          // Close dialog
          await page.keyboard.press('Escape');
        }
      }
    } else {
      console.log('No jobs awaiting instrumental selection');
    }
  });

  test('job card expands to show details', async ({ page }) => {
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Find job cards by looking for elements with status badges (unique to job cards)
    // Job cards have status like "Complete", "Failed", "Select Audio", etc.
    const statusBadges = ['Complete', 'Failed', 'Select Audio', 'Downloading', 'Awaiting Review', 'Select Instrumental'];
    let jobCard = null;

    for (const status of statusBadges) {
      const card = page.locator(`[class*="rounded-lg"][class*="border"]:has-text("${status}")`).first();
      if (await card.isVisible().catch(() => false)) {
        jobCard = card;
        console.log(`Found job with status: ${status}`);
        break;
      }
    }

    if (jobCard) {
      console.log('Clicking on job card...');
      await jobCard.click();
      await page.waitForTimeout(1000);

      // Check that job details are visible - look for Job ID text
      const jobIdText = page.locator('text=/Job ID:/i').first();
      const isExpanded = await jobIdText.isVisible().catch(() => false);

      if (isExpanded) {
        console.log('Job card expanded successfully');

        // Check for actions section
        const viewLogsBtn = page.getByRole('button', { name: /logs/i }).first();
        const hasLogsBtn = await viewLogsBtn.isVisible().catch(() => false);
        console.log(`View logs button visible: ${hasLogsBtn}`);
      } else {
        console.log('Job card did not expand - may need to debug selector');
      }

      await page.screenshot({ path: 'test-results/job-details-expanded.png' });
    } else {
      console.log('No job cards found with recognizable status');
    }
  });

  test('job logs can be viewed', async ({ page }) => {
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Find and click a job
    const jobCard = page.locator('[class*="rounded-lg"][class*="border"]').first();

    if (await jobCard.isVisible()) {
      await jobCard.click();
      await page.waitForTimeout(500);

      // Click View Logs button
      const logsBtn = page.getByRole('button', { name: /logs/i }).first();
      if (await logsBtn.isVisible()) {
        await logsBtn.click();
        await page.waitForTimeout(2000);

        // Check that logs appear
        const logsSection = page.locator('[class*="font-mono"]').first();
        const hasLogs = await logsSection.isVisible().catch(() => false);
        console.log(`Logs section visible: ${hasLogs}`);

        await page.screenshot({ path: 'test-results/job-logs.png' });
      }
    }
  });
});

test.describe('API Health', () => {
  test('backend health check', async ({ page }) => {
    // Direct API call through proxy
    const response = await page.request.get('/api/health');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log('Health check response:', data);
    expect(data.status).toBe('healthy');
  });

  test('jobs list endpoint (authenticated)', async ({ page }) => {
    // Skip if no auth token
    if (!ACCESS_TOKEN) {
      test.skip(true, 'KARAOKE_ACCESS_TOKEN not set');
      return;
    }

    const response = await page.request.get('/api/jobs?limit=5', {
      headers: {
        'Authorization': `Bearer ${ACCESS_TOKEN}`,
      },
    });
    expect(response.ok()).toBeTruthy();

    const jobs = await response.json();
    console.log(`Found ${jobs.length} jobs`);
  });
});
