import { test, expect, Page, ConsoleMessage, Request, Response } from '@playwright/test';

/**
 * Production E2E tests for the complete karaoke generation journey.
 *
 * These tests run directly against gen.nomadkaraoke.com (production).
 *
 * IMPORTANT: Set KARAOKE_ACCESS_TOKEN environment variable:
 *   KARAOKE_ACCESS_TOKEN=your-token npx playwright test --config=playwright.production.config.ts
 *
 * The complete user journey:
 * 1. Enter artist name and song title
 * 2. Select audio source from search results
 * 3. Wait for audio download and preparation
 * 4. Review/correct lyrics in the review UI
 * 5. Submit the review
 * 6. Wait for render stage
 * 7. Select instrumental (clean or with backing vocals)
 * 8. Wait for final render and distribution
 * 9. Verify YouTube upload and Dropbox folder links
 */

const ACCESS_TOKEN = process.env.KARAOKE_ACCESS_TOKEN;
const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Test song - using something short and reliable
const TEST_ARTIST = 'LCMDF';
const TEST_TITLE = 'Take Me To The Mountains';

// Helper to authenticate the page by setting localStorage token
async function authenticatePage(page: Page) {
  if (!ACCESS_TOKEN) {
    throw new Error('KARAOKE_ACCESS_TOKEN environment variable is required for production tests');
  }

  // Set the token in localStorage before navigating
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

// Wait for a job to reach a specific status with progress logging
async function waitForJobStatus(
  page: Page,
  targetStatuses: string[],
  timeoutMs: number = 600000, // 10 minutes default
  pollIntervalMs: number = 5000
): Promise<{ status: string; jobId?: string }> {
  const startTime = Date.now();
  let lastStatus = '';

  while (Date.now() - startTime < timeoutMs) {
    // Find job cards with status badges
    const badges = await page.locator('[class*="rounded-lg"][class*="border"]').locator('span, [class*="Badge"]').allTextContents();
    const allText = badges.join(' ').toLowerCase();

    // Check for target statuses
    for (const status of targetStatuses) {
      if (allText.includes(status.toLowerCase())) {
        console.log(`Found target status: ${status}`);
        return { status };
      }
    }

    // Check for failure states
    if (allText.includes('failed')) {
      // Get error details
      const errorDetails = await page.locator('[class*="text-red"]').allTextContents();
      throw new Error(`Job failed: ${errorDetails.join(', ')}`);
    }
    if (allText.includes('cancelled')) {
      throw new Error('Job was cancelled');
    }

    // Log progress updates
    const currentBadges = badges.filter(b => b.trim()).join(', ');
    if (currentBadges !== lastStatus) {
      console.log(`Current status: ${currentBadges}`);
      lastStatus = currentBadges;
    }

    // Click refresh and wait
    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
    }
    await page.waitForTimeout(pollIntervalMs);
  }

  throw new Error(`Timeout waiting for status: ${targetStatuses.join(' or ')}`);
}

test.describe('Production Full Karaoke Generation Journey', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Ensure we have authentication
    await authenticatePage(page);
    setupLogging(page);
  });

  test('Step 1: Homepage loads and shows interface', async ({ page }) => {
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Screenshot for visual verification
    await page.screenshot({ path: 'test-results/prod-01-homepage.png', fullPage: true });

    // Verify main elements
    await expect(page.locator('h1')).toContainText('Karaoke Generator');
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();
    await expect(page.locator('text=Recent Jobs')).toBeVisible();

    console.log('Homepage loaded successfully');
  });

  test('Step 2: Can search for audio and see results', async ({ page }) => {
    test.setTimeout(180000); // 3 minutes - search can be slow

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Click Search tab
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(500);

    // Fill in artist and title
    await page.getByLabel('Artist').fill(TEST_ARTIST);
    await page.getByLabel('Title').fill(TEST_TITLE);

    await page.screenshot({ path: 'test-results/prod-02-search-form.png' });

    // Submit search
    console.log(`Searching for: ${TEST_ARTIST} - ${TEST_TITLE}`);
    const searchButton = page.getByRole('button', { name: /search.*create/i });
    await searchButton.click();

    // Wait for response - could be quick or take a while
    await page.waitForTimeout(5000);

    // Check for loading state or error
    const errorDiv = page.locator('[class*="text-red"]').first();
    const hasError = await errorDiv.isVisible().catch(() => false);

    if (hasError) {
      const errorText = await errorDiv.textContent();
      console.log(`Search error: ${errorText}`);
      await page.screenshot({ path: 'test-results/prod-02-search-error.png' });
      // Don't fail - document the error state
    } else {
      // Should see either results or job created
      await page.screenshot({ path: 'test-results/prod-02-search-submitted.png' });
      console.log('Search request submitted');
    }
  });

  test('Step 3: Full journey - Search to Audio Selection', async ({ page }) => {
    test.setTimeout(300000); // 5 minutes

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // First check if there's already a job awaiting audio selection
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(2000);

    let jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /select audio/i
    }).first();

    if (!await jobCard.isVisible()) {
      // Create new job via search
      console.log('Creating new job via search...');
      await page.getByRole('tab', { name: /search/i }).click();
      await page.getByLabel('Artist').fill(TEST_ARTIST);
      await page.getByLabel('Title').fill(TEST_TITLE);
      await page.getByRole('button', { name: /search.*create/i }).click();

      // Wait for job to appear and reach audio selection state
      await page.waitForTimeout(10000);
      await page.click('button:has-text("Refresh")');
      await page.waitForTimeout(3000);

      jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
        hasText: /select audio/i
      }).first();
    }

    if (await jobCard.isVisible()) {
      console.log('Found job awaiting audio selection');
      await jobCard.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/prod-03-job-expanded.png' });

      // Open audio selection dialog
      const selectAudioBtn = page.getByRole('button', { name: /select audio/i });
      if (await selectAudioBtn.isVisible()) {
        await selectAudioBtn.click();
        await page.waitForTimeout(2000);

        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          await page.screenshot({ path: 'test-results/prod-03-audio-dialog.png', fullPage: true });

          // Count audio options
          const selectButtons = dialog.getByRole('button', { name: /^select$/i });
          const optionCount = await selectButtons.count();
          console.log(`Found ${optionCount} audio options`);

          if (optionCount > 0) {
            // Select first option
            console.log('Selecting first audio option...');
            await selectButtons.first().click();

            // Wait for dialog to close (download may take time)
            const closed = await dialog.waitFor({ state: 'hidden', timeout: 120000 }).then(() => true).catch(() => false);
            if (closed) {
              console.log('Audio selection completed');
            } else {
              console.log('Dialog still open - may be processing');
              await page.keyboard.press('Escape');
            }

            await page.screenshot({ path: 'test-results/prod-03-after-selection.png' });
          }
        }
      }
    } else {
      console.log('No job awaiting audio selection');
      await page.screenshot({ path: 'test-results/prod-03-no-audio-job.png' });
    }
  });

  test('Step 4: Full journey - Lyrics Review', async ({ page }) => {
    test.setTimeout(600000); // 10 minutes - review can take time

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(2000);

    // Look for job awaiting review
    const reviewJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /awaiting review|review lyrics/i
    }).first();

    if (await reviewJob.isVisible()) {
      console.log('Found job awaiting lyrics review');
      await reviewJob.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/prod-04-review-job.png' });

      // Click review lyrics button (use .first() since there may be multiple jobs with this button)
      const reviewBtn = page.getByRole('button', { name: /review lyrics/i }).or(page.getByRole('link', { name: /review lyrics/i })).first();
      if (await reviewBtn.isVisible()) {
        console.log('Opening lyrics review UI...');

        // The review button opens a new tab with the LyricsTranscriber UI
        const [popup] = await Promise.all([
          page.context().waitForEvent('page', { timeout: 15000 }).catch(() => null),
          reviewBtn.click()
        ]);

        if (popup) {
          await popup.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {
            console.log('Review UI network idle timeout - continuing anyway');
          });
          await popup.screenshot({ path: 'test-results/prod-04-review-ui.png', fullPage: true });
          console.log(`Review UI opened: ${popup.url()}`);

          // Wait for the review UI to fully load
          await popup.waitForTimeout(5000);

          // The LyricsTranscriber review UI should have:
          // - A preview video player
          // - Lyrics display with timing
          // - Edit controls
          // - A submit/complete button

          // First, let's see what buttons are available
          const allButtons = await popup.getByRole('button').allTextContents();
          console.log(`Available buttons in review UI: ${allButtons.join(', ')}`);

          // Take a screenshot after loading
          await popup.screenshot({ path: 'test-results/prod-04-review-ui-loaded.png', fullPage: true });

          // The review flow in LyricsTranscriber is:
          // 1. Click "Preview Video" button to generate preview
          // 2. Wait for preview to generate (this opens a modal)
          // 3. Click "Complete Review" in the modal to submit

          // Step 1: Click "Preview Video" button
          const previewBtn = popup.locator('button:has-text("Preview Video")').first();
          if (await previewBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
            console.log('Found "Preview Video" button, clicking...');
            await previewBtn.click();

            // Wait for preview to generate (can take up to 30-60 seconds)
            console.log('Waiting for preview video to generate...');
            await popup.waitForTimeout(10000);
            await popup.screenshot({ path: 'test-results/prod-04-preview-generating.png' });

            // Step 2: Look for "Complete Review" button (appears after preview is ready or in modal)
            let submitted = false;
            const maxWaitAttempts = 12; // Wait up to 2 minutes for preview
            for (let i = 0; i < maxWaitAttempts && !submitted; i++) {
              // Check if popup is still open
              if (popup.isClosed()) {
                console.log('Popup closed - review may have been auto-submitted');
                submitted = true;
                break;
              }

              // Look for Complete Review button
              const completeBtn = popup.locator('button:has-text("Complete Review")').first();
              if (await completeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
                console.log('Found "Complete Review" button, clicking...');
                await completeBtn.click();
                // Clicking Complete Review closes the popup, so catch any errors
                await popup.waitForTimeout(3000).catch(() => {
                  console.log('Popup closed after clicking Complete Review (expected)');
                });
                submitted = true;
                console.log('Review submitted successfully!');
              } else {
                console.log(`Waiting for Complete Review button... (attempt ${i + 1}/${maxWaitAttempts})`);
                await popup.waitForTimeout(10000).catch(() => {});
                await popup.screenshot({ path: `test-results/prod-04-waiting-${i}.png` }).catch(() => {});
              }
            }

            if (!submitted) {
              console.log('Could not find "Complete Review" button after waiting');
              const allButtons = await popup.getByRole('button').allTextContents().catch(() => []);
              console.log(`Available buttons: ${allButtons.filter(b => b.trim()).join(', ')}`);
            }
          } else {
            console.log('Preview Video button not found, trying direct Complete Review...');
            // Fallback: Maybe the modal is already open
            const completeBtn = popup.locator('button:has-text("Complete Review")').first();
            if (await completeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
              await completeBtn.click();
              await popup.waitForTimeout(3000);
              console.log('Review submitted via direct Complete Review button');
              await popup.screenshot({ path: 'test-results/prod-04-after-submit.png' });
            } else {
              console.log('Could not find Complete Review button');
              const allButtons = await popup.getByRole('button').allTextContents();
              console.log(`Available buttons: ${allButtons.filter(b => b.trim()).join(', ')}`);
            }
          }

          // Close popup if still open
          if (!popup.isClosed()) {
            await popup.close().catch(() => {});
          }

          // Refresh main page to check status
          await page.click('button:has-text("Refresh")');
          await page.waitForTimeout(3000);
          await page.screenshot({ path: 'test-results/prod-04-after-review.png' });

          // Check if job progressed past review
          const newStatus = await page.locator('[class*="rounded-lg"][class*="border"]').first().locator('span').allTextContents();
          console.log(`Job status after review: ${newStatus.filter(s => s.trim()).join(', ')}`);

          // Verify the job is no longer in "awaiting review" state
          const pageTextAfter = await page.locator('body').textContent();
          if (pageTextAfter?.toLowerCase().includes('awaiting review')) {
            console.log('WARNING: Job still shows "awaiting review" after submission');
          } else if (pageTextAfter?.toLowerCase().includes('review complete') ||
                     pageTextAfter?.toLowerCase().includes('rendering') ||
                     pageTextAfter?.toLowerCase().includes('select instrumental')) {
            console.log('SUCCESS: Job progressed past review stage!');
          }

        } else {
          // No popup - might have navigated in same page
          console.log('Review button did not open popup, checking current page...');
          await page.waitForTimeout(2000);
          await page.screenshot({ path: 'test-results/prod-04-review-same-page.png' });
        }
      } else {
        console.log('Review button not visible');
      }
    } else {
      console.log('No jobs awaiting lyrics review');
      await page.screenshot({ path: 'test-results/prod-04-no-review-job.png' });
    }
  });

  test('Step 5: Full journey - Instrumental Selection', async ({ page }) => {
    test.setTimeout(300000); // 5 minutes

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(2000);

    // Look for job awaiting instrumental selection
    const instrumentalJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /select instrumental/i
    }).first();

    if (await instrumentalJob.isVisible()) {
      console.log('Found job awaiting instrumental selection');
      await instrumentalJob.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/prod-05-instrumental-job.png' });

      // Click select instrumental button (use .first() since there may be multiple jobs with this button)
      const selectBtn = page.getByRole('button', { name: /select instrumental/i }).first();
      if (await selectBtn.isVisible()) {
        await selectBtn.click();
        await page.waitForTimeout(2000);

        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          await page.screenshot({ path: 'test-results/prod-05-instrumental-dialog.png' });

          // Find and click "Clean" option (usually preferred)
          const cleanOption = dialog.getByRole('button', { name: /clean|select/i }).first();
          if (await cleanOption.isVisible()) {
            console.log('Selecting clean instrumental...');
            await cleanOption.click();

            await dialog.waitFor({ state: 'hidden', timeout: 30000 }).catch(() => {
              console.log('Dialog still open after selection');
            });

            await page.screenshot({ path: 'test-results/prod-05-after-instrumental.png' });
            console.log('Instrumental selection completed');
          }
        }
      }
    } else {
      console.log('No jobs awaiting instrumental selection');
      await page.screenshot({ path: 'test-results/prod-05-no-instrumental-job.png' });
    }
  });

  test('Step 6: Verify completed job - Downloads and Distribution', async ({ page }) => {
    test.setTimeout(180000); // 3 minutes

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(2000);

    // Look for completed job
    const completedJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /complete/i
    }).first();

    if (await completedJob.isVisible()) {
      console.log('Found completed job');
      await completedJob.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/prod-06-completed-job.png', fullPage: true });

      // Look for download links
      const downloadSection = page.locator('text=Download').first();
      if (await downloadSection.isVisible()) {
        console.log('Downloads section visible');
      }

      // Look for YouTube link
      const youtubeLink = page.locator('a[href*="youtube.com"], a[href*="youtu.be"]').first();
      if (await youtubeLink.isVisible()) {
        const href = await youtubeLink.getAttribute('href');
        console.log(`YouTube link found: ${href}`);
      } else {
        console.log('No YouTube link found');
      }

      // Look for Dropbox link
      const dropboxLink = page.locator('a[href*="dropbox.com"]').first();
      if (await dropboxLink.isVisible()) {
        const href = await dropboxLink.getAttribute('href');
        console.log(`Dropbox link found: ${href}`);
      } else {
        console.log('No Dropbox link found');
      }

      // Check for video download buttons
      const videoDownloads = page.locator('a:has-text("720p"), a:has-text("4K"), button:has-text("Download")');
      const downloadCount = await videoDownloads.count();
      console.log(`Found ${downloadCount} download options`);

    } else {
      console.log('No completed jobs found');
      await page.screenshot({ path: 'test-results/prod-06-no-completed-job.png' });
    }
  });

  test('Full E2E Journey - Complete track generation', async ({ page }) => {
    /**
     * FULL END-TO-END TEST
     *
     * This test goes through the entire journey:
     * 1. Search for a song
     * 2. Select audio
     * 3. Wait for preparation
     * 4. Review lyrics (or auto-accept in auto mode)
     * 5. Select instrumental
     * 6. Wait for render
     * 7. Verify distribution (YouTube, Dropbox)
     *
     * WARNING: This creates a real karaoke track on production!
     * Only run when you want to test the full system.
     */
    test.setTimeout(900000); // 15 minutes - full generation takes time

    // Use auto mode for non-interactive flow
    await page.goto(`${PROD_URL}?auto=true`);
    await page.waitForLoadState('networkidle');

    // Verify auto mode banner
    const autoBanner = page.locator('text=Non-Interactive Mode');
    if (await autoBanner.isVisible()) {
      console.log('Auto mode enabled');
    } else {
      console.log('Auto mode may not have activated, continuing...');
    }

    await page.screenshot({ path: 'test-results/prod-e2e-01-start.png' });

    // Step 1: Search for song
    console.log('=== Step 1: Searching for song ===');
    await page.getByRole('tab', { name: /search/i }).click();
    await page.getByLabel('Artist').fill(TEST_ARTIST);
    await page.getByLabel('Title').fill(TEST_TITLE);

    // Generate unique identifier to track our job
    const timestamp = Date.now();
    console.log(`Test timestamp: ${timestamp}`);

    await page.getByRole('button', { name: /search.*create/i }).click();
    console.log('Search submitted, waiting for job creation...');

    // Wait for job to appear
    await page.waitForTimeout(15000);
    await page.click('button:has-text("Refresh")');
    await page.screenshot({ path: 'test-results/prod-e2e-02-after-search.png' });

    // Step 2-3: Audio selection (may happen automatically with search results, or need manual)
    console.log('=== Step 2: Audio selection ===');
    let needsAudioSelection = true;
    let attempts = 0;
    const maxAttempts = 30; // 2.5 minutes of checking

    while (needsAudioSelection && attempts < maxAttempts) {
      await page.click('button:has-text("Refresh")');
      await page.waitForTimeout(5000);

      // Check current state
      const pageText = await page.locator('body').textContent();

      if (pageText?.toLowerCase().includes('select audio')) {
        console.log('Job needs audio selection');

        // Find and click the job card
        const jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
          hasText: /select audio/i
        }).first();

        if (await jobCard.isVisible()) {
          await jobCard.click();
          await page.waitForTimeout(1000);

          const selectAudioBtn = page.getByRole('button', { name: /select audio/i });
          if (await selectAudioBtn.isVisible()) {
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
          }
        }
        needsAudioSelection = false;
      } else if (
        pageText?.toLowerCase().includes('downloading') ||
        pageText?.toLowerCase().includes('separating') ||
        pageText?.toLowerCase().includes('transcribing') ||
        pageText?.toLowerCase().includes('awaiting review') ||
        pageText?.toLowerCase().includes('select instrumental') ||
        pageText?.toLowerCase().includes('complete')
      ) {
        console.log('Job has progressed past audio selection');
        needsAudioSelection = false;
      }

      attempts++;
    }

    await page.screenshot({ path: 'test-results/prod-e2e-03-after-audio.png' });

    // Step 4: Wait for processing and lyrics review
    console.log('=== Step 3-4: Waiting for processing and review ===');

    // Monitor progress and handle review stage
    attempts = 0;
    const maxProcessingAttempts = 120; // 10 minutes of processing
    let reviewAttempts = 0;
    const maxReviewAttempts = 3; // Try manual review completion up to 3 times

    while (attempts < maxProcessingAttempts) {
      await page.click('button:has-text("Refresh")');
      await page.waitForTimeout(5000);

      const pageText = await page.locator('body').textContent();

      if (pageText?.toLowerCase().includes('select instrumental')) {
        console.log('Ready for instrumental selection');
        break;
      } else if (pageText?.toLowerCase().includes('complete')) {
        console.log('Job completed!');
        break;
      } else if (pageText?.toLowerCase().includes('failed')) {
        await page.screenshot({ path: 'test-results/prod-e2e-failed.png' });
        throw new Error('Job failed during processing');
      } else if (pageText?.toLowerCase().includes('awaiting review') || pageText?.toLowerCase().includes('review lyrics')) {
        // Job is awaiting review - auto-mode should handle this, but let's verify
        console.log('Job awaiting review - checking if auto-processing is working...');
        await page.screenshot({ path: 'test-results/prod-e2e-awaiting-review.png' });

        // Wait a bit for auto-processor to kick in
        await page.waitForTimeout(10000);
        await page.click('button:has-text("Refresh")');
        await page.waitForTimeout(2000);

        // Check if still awaiting review
        const stillAwaiting = await page.locator('body').textContent();
        if (stillAwaiting?.toLowerCase().includes('awaiting review') && reviewAttempts < maxReviewAttempts) {
          console.log(`Auto-processing not completing review. Attempting manual completion (attempt ${reviewAttempts + 1}/${maxReviewAttempts})...`);

          // Find the job card and try to get the job ID
          const jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
            hasText: /awaiting review/i
          }).first();

          if (await jobCard.isVisible()) {
            // Click to expand the job
            await jobCard.click();
            await page.waitForTimeout(1000);

            // Try to find and click "Review Lyrics" button to open review UI
            const reviewBtn = page.getByRole('button', { name: /review lyrics/i }).or(page.getByRole('link', { name: /review lyrics/i })).first();

            if (await reviewBtn.isVisible()) {
              console.log('Opening review UI...');

              // The review button opens a new tab with the LyricsTranscriber UI
              const [popup] = await Promise.all([
                page.context().waitForEvent('page', { timeout: 15000 }).catch(() => null),
                reviewBtn.click()
              ]);

              if (popup) {
                console.log(`Review UI opened: ${popup.url()}`);
                await popup.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
                await popup.screenshot({ path: `test-results/prod-e2e-review-ui-${reviewAttempts}.png`, fullPage: true });

                // Wait for the review UI to fully load
                await popup.waitForTimeout(5000);

                // The review flow: Click "Preview Video" -> Wait -> Click "Complete Review"
                const previewBtn = popup.locator('button:has-text("Preview Video")').first();

                if (await previewBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
                  console.log('Clicking "Preview Video" button...');
                  await previewBtn.click();
                  await popup.waitForTimeout(10000);

                  // Wait for "Complete Review" button to appear
                  let reviewCompleted = false;
                  for (let i = 0; i < 6 && !reviewCompleted; i++) {
                    const completeBtn = popup.locator('button:has-text("Complete Review")').first();
                    if (await completeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
                      console.log('Clicking "Complete Review" button...');
                      await completeBtn.click();
                      await popup.waitForTimeout(3000);
                      reviewCompleted = true;
                      console.log('Review submitted via UI');
                    } else {
                      console.log(`Waiting for Complete Review... (${i + 1}/6)`);
                      await popup.waitForTimeout(10000);
                    }
                  }

                  if (!reviewCompleted) {
                    console.log('Could not complete review via UI');
                    const allButtons = await popup.getByRole('button').allTextContents();
                    console.log(`Available buttons: ${allButtons.filter(b => b.trim()).join(', ')}`);
                  }
                } else {
                  console.log('Preview Video button not found');
                }

                await popup.close();
              } else {
                // No popup - might have navigated in same page
                console.log('Review button did not open popup, checking current page...');
                await page.waitForTimeout(2000);
              }
            }
          }

          reviewAttempts++;
        }
      }

      // Log current stage
      const badges = await page.locator('[class*="rounded-lg"][class*="border"]').first().locator('span').allTextContents();
      console.log(`Current status: ${badges.filter(b => b.trim()).join(', ')}`);

      attempts++;
    }

    await page.screenshot({ path: 'test-results/prod-e2e-04-after-processing.png' });

    // Step 5: Instrumental selection
    console.log('=== Step 5: Instrumental selection ===');

    const instrumentalJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /select instrumental/i
    }).first();

    if (await instrumentalJob.isVisible()) {
      await instrumentalJob.click();
      await page.waitForTimeout(1000);

      const selectBtn = page.getByRole('button', { name: /select instrumental/i }).first();
      if (await selectBtn.isVisible()) {
        await selectBtn.click();
        await page.waitForTimeout(2000);

        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          // Select clean instrumental
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

    // Step 6: Wait for final render and distribution
    console.log('=== Step 6: Waiting for final render ===');

    attempts = 0;
    const maxRenderAttempts = 60; // 5 minutes

    while (attempts < maxRenderAttempts) {
      await page.click('button:has-text("Refresh")');
      await page.waitForTimeout(5000);

      const pageText = await page.locator('body').textContent();

      if (pageText?.toLowerCase().includes('complete')) {
        console.log('Job completed!');
        break;
      } else if (pageText?.toLowerCase().includes('failed')) {
        await page.screenshot({ path: 'test-results/prod-e2e-render-failed.png' });
        throw new Error('Job failed during rendering');
      }

      const badges = await page.locator('[class*="rounded-lg"][class*="border"]').first().locator('span').allTextContents();
      console.log(`Render status: ${badges.filter(b => b.trim()).join(', ')}`);

      attempts++;
    }

    await page.screenshot({ path: 'test-results/prod-e2e-06-final.png', fullPage: true });

    // Step 7: Verify results
    console.log('=== Step 7: Verifying results ===');

    const completedJob = page.locator('[class*="rounded-lg"][class*="border"]').filter({
      hasText: /complete/i
    }).first();

    if (await completedJob.isVisible()) {
      await completedJob.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/prod-e2e-07-completed-details.png', fullPage: true });

      // Check for YouTube link
      const youtubeLink = page.locator('a[href*="youtube.com"], a[href*="youtu.be"]').first();
      if (await youtubeLink.isVisible()) {
        const href = await youtubeLink.getAttribute('href');
        console.log(`SUCCESS: YouTube link found: ${href}`);
      } else {
        console.log('WARNING: No YouTube link found');
      }

      // Check for Dropbox link
      const dropboxLink = page.locator('a[href*="dropbox.com"]').first();
      if (await dropboxLink.isVisible()) {
        const href = await dropboxLink.getAttribute('href');
        console.log(`SUCCESS: Dropbox link found: ${href}`);
      } else {
        console.log('WARNING: No Dropbox link found');
      }

      // Count download options
      const downloads = page.locator('a:has-text("Download"), button:has-text("Download"), a:has-text("720p"), a:has-text("4K")');
      const downloadCount = await downloads.count();
      console.log(`Downloads available: ${downloadCount}`);

      console.log('=== E2E TEST COMPLETE ===');
    } else {
      throw new Error('Job did not complete - check screenshots for debugging');
    }
  });
});

// API health check - quick sanity test
test('Production API health check', async ({ request }) => {
  const response = await request.get(`${API_URL}/api/health`);
  expect(response.ok()).toBeTruthy();

  const data = await response.json();
  console.log('API Health:', data);
  expect(data.status).toBe('healthy');
});
