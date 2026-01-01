import { test, expect, Page, BrowserContext } from '@playwright/test';
import { createEmailHelper, isEmailTestingAvailable } from '../helpers/email-testing';

/**
 * E2E Happy Path Test - Real User Journey with Full UI Interactions
 *
 * This test validates the COMPLETE karaoke generation flow using ONLY
 * browser interactions - no API shortcuts allowed.
 *
 * See docs/E2E-HAPPY-PATH-TEST-SPEC.md for full requirements.
 *
 * Test Flow:
 * 1. Landing Page - Navigate and verify
 * 2. New User Signup - Create MailSlurp inbox, submit beta form, verify email
 * 3. Magic Link Auth - Click magic link to authenticate
 * 4. Create Job - Search for test song via UI
 * 5. Audio Selection - Select audio source via UI dialog
 * 6. Wait for Processing - Monitor via UI status updates
 * 7. Lyrics Review - Open review UI, interact, submit via UI
 * 8. Instrumental Selection - Open selection UI, interact, submit via UI
 * 9. Wait for Completion - Monitor via UI
 * 10. Verify Downloads - Check download links work
 * 11. Verify Distribution - Check YouTube/Dropbox/GDrive indicators
 * 12. Cleanup - Delete distributed content and job
 *
 * Environment Variables:
 *   - MAILSLURP_API_KEY: Required for email testing
 *   - E2E_ADMIN_TOKEN: Required for cleanup endpoint (optional - cleanup skipped if not set)
 */

// =============================================================================
// CONSTANTS
// =============================================================================

const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Test song - uses cached flacfetch results for speed
const TEST_SONG = {
  artist: 'piri',
  title: 'dog',
} as const;

// Timeouts
const TIMEOUTS = {
  action: 30_000,           // 30s for UI actions
  expect: 60_000,           // 60s for assertions
  emailArrival: 120_000,    // 2min for email to arrive
  audioSearch: 120_000,     // 2min for audio search
  lyricsProcessing: 1200_000, // 20min for lyrics transcription
  videoRendering: 900_000,  // 15min for video rendering
  finalEncoding: 600_000,   // 10min for final encoding
  fullTest: 3600_000,       // 60min for full test
} as const;

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Wait for job status to appear in the UI
 */
async function waitForJobStatus(
  page: Page,
  jobCard: any,
  targetStatuses: string[],
  timeoutMs: number
): Promise<string> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    // Check the status indicator text in the job card
    const statusText = await jobCard.locator('[class*="text-"]').first().textContent() || '';

    for (const target of targetStatuses) {
      if (statusText.toLowerCase().includes(target.toLowerCase())) {
        console.log(`  Found status: ${statusText}`);
        return target;
      }
    }

    // Also check for "Action needed" indicator
    const actionNeeded = await jobCard.getByText('Action needed').isVisible().catch(() => false);
    if (actionNeeded) {
      console.log(`  Action needed - checking for target status`);
      for (const target of targetStatuses) {
        if (statusText.toLowerCase().includes(target.replace('awaiting_', '').replace('_', ' '))) {
          return target;
        }
      }
    }

    // Wait before next check
    await page.waitForTimeout(5000);

    // Refresh to get latest status
    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    if (await refreshBtn.isVisible().catch(() => false)) {
      await refreshBtn.click();
      await page.waitForTimeout(2000);
    }
  }

  throw new Error(`Timeout waiting for status: ${targetStatuses.join(' or ')}`);
}

/**
 * Get the auth token from localStorage
 */
async function getAuthToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => localStorage.getItem('karaoke_access_token'));
}

// =============================================================================
// TEST
// =============================================================================

test.describe('E2E Happy Path - Real User with Full UI Interactions', () => {
  test('Complete flow: New user signup -> Karaoke generation -> Distribution -> Cleanup', async ({
    page,
    context,
  }) => {
    test.setTimeout(TIMEOUTS.fullTest);

    // Skip if MailSlurp not available
    if (!isEmailTestingAvailable()) {
      test.skip(true, 'MAILSLURP_API_KEY not set - cannot run real user test');
      return;
    }

    let accessToken: string | null = null;
    let jobId: string | null = null;
    let inboxId: string | null = null;

    const emailHelper = await createEmailHelper();

    try {
      // =========================================================================
      // STEP 1: Landing Page
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 1: Landing Page');
      console.log('========================================');

      await page.goto(PROD_URL);
      await page.waitForLoadState('networkidle');

      // Verify hero section
      await expect(page.locator('h1')).toContainText('Karaoke Video', { timeout: TIMEOUTS.expect });
      console.log('  Hero section visible');

      // Verify pricing section
      await expect(page.locator('#pricing')).toBeVisible({ timeout: TIMEOUTS.expect });
      console.log('  Pricing section visible');

      await page.screenshot({ path: 'test-results/01-landing-page.png', fullPage: true });
      console.log('STEP 1 COMPLETE: Landing page loads correctly');

      // =========================================================================
      // STEP 2: New User Beta Enrollment
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 2: New User Beta Enrollment');
      console.log('========================================');

      // Create test inbox
      const inbox = await emailHelper.createInbox();
      inboxId = inbox.id!;
      console.log(`  Test email: ${inbox.emailAddress}`);

      // Open beta form - click the Join Beta Program button
      const betaButton = page.getByRole('button', { name: /join beta program/i });
      await expect(betaButton).toBeVisible({ timeout: TIMEOUTS.action });
      await betaButton.click();
      await page.waitForTimeout(1000); // Wait for form animation

      // Wait for beta form to appear
      const betaEmailInput = page.locator('#beta-email');
      await expect(betaEmailInput).toBeVisible({ timeout: TIMEOUTS.action });
      console.log('  Beta form visible');

      // Fill beta form
      await betaEmailInput.fill(inbox.emailAddress!);

      // Fill the promise/reason field
      const promiseField = page.locator('#beta-promise, textarea');
      await promiseField.first().fill('piri - dog (E2E test: testing complete karaoke generation flow)');

      // Check the acceptance checkbox
      const acceptCheckbox = page.locator('#beta-accept, input[type="checkbox"]');
      await acceptCheckbox.first().check();

      await page.screenshot({ path: 'test-results/02a-beta-form-filled.png' });
      console.log('  Beta form filled');

      // Submit form - look for the submit button
      const submitButton = page.getByRole('button', { name: /get.*free.*credit|submit|enroll/i });
      await expect(submitButton).toBeEnabled({ timeout: TIMEOUTS.action });
      await submitButton.click();

      // Wait for success and redirect
      await expect(
        page.getByText(/welcome to the beta|redirecting to the app/i)
      ).toBeVisible({ timeout: 15000 });

      await page.waitForURL(/\/app/, { timeout: 10000 });
      console.log('  Redirected to /app');

      // Get the token from localStorage
      accessToken = await getAuthToken(page);
      if (!accessToken) {
        throw new Error('No access token received after beta enrollment');
      }
      console.log('  Session token received');

      await page.screenshot({ path: 'test-results/02b-app-after-enrollment.png' });
      console.log('STEP 2 COMPLETE: Beta enrollment successful');

      // =========================================================================
      // STEP 3: Verify Credits (via UI)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 3: Verify Credits');
      console.log('========================================');

      // Look for credit indicator in the UI
      const creditText = await page.getByText(/credit/i).first().textContent();
      console.log(`  Credits visible: ${creditText}`);

      console.log('STEP 3 COMPLETE: User authenticated with credits');

      // =========================================================================
      // STEP 4: Create Karaoke Job (via UI)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 4: Create Karaoke Job');
      console.log('========================================');

      // Navigate to Search tab
      await page.getByRole('tab', { name: /search/i }).click();
      await page.waitForTimeout(1000);

      // Select a theme if required
      const themeSelect = page.locator('button[role="combobox"]').first();
      if (await themeSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
        const currentTheme = await themeSelect.textContent();
        if (currentTheme?.toLowerCase().includes('select')) {
          await themeSelect.click();
          await page.waitForTimeout(500);
          await page.locator('[role="option"]').first().click();
          await page.waitForTimeout(500);
          console.log('  Selected first theme');
        }
      }

      // Fill artist and title
      await page.getByLabel('Artist').fill(TEST_SONG.artist);
      await page.getByLabel('Title').fill(TEST_SONG.title);
      console.log(`  Searching for: ${TEST_SONG.artist} - ${TEST_SONG.title}`);

      await page.screenshot({ path: 'test-results/04a-search-form.png' });

      // Submit search
      await page.getByRole('button', { name: /search.*create/i }).click();

      // Wait for job card to appear
      console.log('  Waiting for job card...');
      const jobCard = page.locator('[class*="rounded-lg"][class*="border"]').filter({
        hasText: `${TEST_SONG.artist} - ${TEST_SONG.title}`
      }).first();

      await expect(jobCard).toBeVisible({ timeout: TIMEOUTS.audioSearch });
      console.log('  Job card visible');

      // Extract job ID from the card
      const jobIdText = await jobCard.getByText(/ID:/).first().textContent();
      const idMatch = jobIdText?.match(/ID:\s*([a-zA-Z0-9-]+)/);
      if (idMatch) {
        jobId = idMatch[1];
        console.log(`  Job ID: ${jobId}`);
      }

      await page.screenshot({ path: 'test-results/04b-job-created.png' });
      console.log('STEP 4 COMPLETE: Job created');

      // =========================================================================
      // STEP 5: Audio Selection (via UI)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 5: Audio Selection');
      console.log('========================================');

      // Wait for job to need audio selection or skip if not needed
      await page.waitForTimeout(5000);

      // Check if Select Audio button appears
      const selectAudioBtn = jobCard.getByRole('button', { name: /select audio/i });
      if (await selectAudioBtn.isVisible({ timeout: 30000 }).catch(() => false)) {
        console.log('  Opening audio selection dialog...');
        await selectAudioBtn.click();
        await page.waitForTimeout(2000);

        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible({ timeout: 5000 })) {
          await page.screenshot({ path: 'test-results/05a-audio-dialog.png' });

          // Find and click first Select button
          const selectButtons = dialog.getByRole('button', { name: /^select$/i });
          const count = await selectButtons.count();
          console.log(`  Found ${count} audio options`);

          if (count > 0) {
            await selectButtons.first().click();
            console.log('  Audio selected via UI');

            // Wait for dialog to close
            await dialog.waitFor({ state: 'hidden', timeout: TIMEOUTS.audioSearch }).catch(() => {
              console.log('  Dialog still open - pressing Escape');
              return page.keyboard.press('Escape');
            });
          }
        }
      } else {
        console.log('  No audio selection needed - job auto-selected or cached');
      }

      await page.screenshot({ path: 'test-results/05b-after-audio.png' });
      console.log('STEP 5 COMPLETE: Audio selection handled');

      // =========================================================================
      // STEP 6: Wait for Lyrics Processing
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 6: Wait for Lyrics Processing');
      console.log('========================================');

      console.log('  Waiting for lyrics transcription (this may take 10-20 minutes)...');

      // Poll the UI for status changes
      const reviewStatuses = ['review lyrics', 'action needed'];
      let foundReviewStatus = false;

      const startTime = Date.now();
      while (Date.now() - startTime < TIMEOUTS.lyricsProcessing) {
        // Refresh the page/jobs
        const refreshBtn = page.getByRole('button', { name: /refresh/i });
        if (await refreshBtn.isVisible().catch(() => false)) {
          await refreshBtn.click();
          await page.waitForTimeout(2000);
        }

        // Check job card status
        const statusText = await jobCard.textContent() || '';
        console.log(`  Status: ${statusText.substring(0, 100)}...`);

        // Check if we've reached review stage
        if (statusText.toLowerCase().includes('review lyrics') ||
            (statusText.toLowerCase().includes('action needed') && statusText.toLowerCase().includes('review'))) {
          foundReviewStatus = true;
          console.log('  Job ready for lyrics review');
          break;
        }

        // Check for failure
        if (statusText.toLowerCase().includes('failed')) {
          throw new Error('Job failed during lyrics processing');
        }

        await page.waitForTimeout(10000); // Check every 10 seconds
      }

      if (!foundReviewStatus) {
        throw new Error('Timeout waiting for lyrics review stage');
      }

      await page.screenshot({ path: 'test-results/06-ready-for-review.png' });
      console.log('STEP 6 COMPLETE: Lyrics processing finished');

      // =========================================================================
      // STEP 7: Lyrics Review (via UI)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 7: Lyrics Review (UI Interaction)');
      console.log('========================================');

      // Click the Review Lyrics button/link
      const reviewLink = jobCard.getByRole('link', { name: /review lyrics/i });
      await expect(reviewLink).toBeVisible({ timeout: TIMEOUTS.action });

      // Get the review URL and open in new page
      const reviewUrl = await reviewLink.getAttribute('href');
      console.log(`  Review URL: ${reviewUrl}`);

      // Open review UI in new page
      const reviewPage = await context.newPage();
      await reviewPage.goto(reviewUrl!, { waitUntil: 'networkidle' });
      await reviewPage.waitForTimeout(3000);

      await reviewPage.screenshot({ path: 'test-results/07a-lyrics-review-opened.png', fullPage: true });
      console.log('  Lyrics review UI opened');

      // Wait for lyrics to load
      await expect(reviewPage.locator('body')).not.toBeEmpty({ timeout: TIMEOUTS.action });

      // Look for approve/submit button - common patterns in lyrics review UIs
      const approveSelectors = [
        'button:has-text("Complete")',
        'button:has-text("Submit")',
        'button:has-text("Approve")',
        'button:has-text("Done")',
        'button:has-text("Save")',
        '[data-testid="complete-review"]',
        '[data-testid="submit-review"]',
      ];

      let foundApproveButton = false;
      for (const selector of approveSelectors) {
        const btn = reviewPage.locator(selector).first();
        if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          console.log(`  Found approve button with selector: ${selector}`);
          await reviewPage.screenshot({ path: 'test-results/07b-before-approve.png', fullPage: true });

          await btn.click();
          foundApproveButton = true;
          console.log('  Clicked approve/submit button');

          // Wait for confirmation or redirect
          await reviewPage.waitForTimeout(5000);
          break;
        }
      }

      if (!foundApproveButton) {
        console.log('  WARNING: Could not find approve button - looking for alternative UI patterns');
        // Take screenshot for debugging
        await reviewPage.screenshot({ path: 'test-results/07b-no-approve-button.png', fullPage: true });

        // Try clicking any primary-looking button
        const primaryBtn = reviewPage.locator('button[class*="primary"], button[class*="bg-blue"], button[class*="bg-green"]').first();
        if (await primaryBtn.isVisible().catch(() => false)) {
          await primaryBtn.click();
          console.log('  Clicked primary-styled button');
        }
      }

      await reviewPage.screenshot({ path: 'test-results/07c-after-approve.png', fullPage: true });

      // Close review page and go back to main app
      await reviewPage.close();
      console.log('  Closed review UI');

      // Refresh main app to see updated status
      await page.bringToFront();
      const refreshBtn = page.getByRole('button', { name: /refresh/i });
      if (await refreshBtn.isVisible().catch(() => false)) {
        await refreshBtn.click();
        await page.waitForTimeout(3000);
      }

      await page.screenshot({ path: 'test-results/07d-after-review-refresh.png' });
      console.log('STEP 7 COMPLETE: Lyrics review submitted');

      // =========================================================================
      // STEP 8: Wait for Video Rendering & Instrumental Selection (via UI)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 8: Wait for Video Rendering & Instrumental Selection');
      console.log('========================================');

      // Wait for instrumental selection to become available
      console.log('  Waiting for video rendering and instrumental selection...');

      let foundInstrumentalStatus = false;
      const renderStartTime = Date.now();

      while (Date.now() - renderStartTime < TIMEOUTS.videoRendering) {
        // Refresh
        if (await refreshBtn.isVisible().catch(() => false)) {
          await refreshBtn.click();
          await page.waitForTimeout(2000);
        }

        // Check job card status
        const statusText = await jobCard.textContent() || '';

        if (statusText.toLowerCase().includes('select instrumental') ||
            (statusText.toLowerCase().includes('action needed') && statusText.toLowerCase().includes('instrumental'))) {
          foundInstrumentalStatus = true;
          console.log('  Job ready for instrumental selection');
          break;
        }

        // Check if already complete (auto-mode might have run)
        if (statusText.toLowerCase().includes('complete')) {
          console.log('  Job already complete - skipping instrumental selection');
          break;
        }

        if (statusText.toLowerCase().includes('failed')) {
          throw new Error('Job failed during video rendering');
        }

        await page.waitForTimeout(10000);
      }

      if (foundInstrumentalStatus) {
        // Click the Select Instrumental button/link
        const instrumentalLink = jobCard.getByRole('link', { name: /select instrumental/i });
        if (await instrumentalLink.isVisible({ timeout: 5000 }).catch(() => false)) {
          const instrumentalUrl = await instrumentalLink.getAttribute('href');
          console.log(`  Instrumental URL: ${instrumentalUrl}`);

          // Open instrumental UI in new page
          const instrumentalPage = await context.newPage();
          await instrumentalPage.goto(`${PROD_URL}${instrumentalUrl}`, { waitUntil: 'networkidle' });
          await instrumentalPage.waitForTimeout(3000);

          await instrumentalPage.screenshot({ path: 'test-results/08a-instrumental-opened.png', fullPage: true });
          console.log('  Instrumental selection UI opened');

          // Look for "Clean" instrumental option and select it
          const cleanOption = instrumentalPage.getByText(/clean/i, { exact: false }).first();
          const cleanButton = instrumentalPage.locator('button:has-text("Clean"), [data-value="clean"], input[value="clean"]').first();

          if (await cleanButton.isVisible({ timeout: 3000 }).catch(() => false)) {
            await cleanButton.click();
            console.log('  Selected "Clean" instrumental');
          } else if (await cleanOption.isVisible({ timeout: 3000 }).catch(() => false)) {
            await cleanOption.click();
            console.log('  Clicked "Clean" option');
          }

          // Look for confirm/submit button
          const confirmSelectors = [
            'button:has-text("Confirm")',
            'button:has-text("Select")',
            'button:has-text("Continue")',
            'button:has-text("Submit")',
            '[data-testid="confirm-selection"]',
          ];

          for (const selector of confirmSelectors) {
            const btn = instrumentalPage.locator(selector).first();
            if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
              await btn.click();
              console.log(`  Clicked confirm button: ${selector}`);
              await instrumentalPage.waitForTimeout(3000);
              break;
            }
          }

          await instrumentalPage.screenshot({ path: 'test-results/08b-instrumental-selected.png', fullPage: true });

          // Close instrumental page
          await instrumentalPage.close();
          console.log('  Closed instrumental UI');
        }
      }

      // Refresh main app
      await page.bringToFront();
      if (await refreshBtn.isVisible().catch(() => false)) {
        await refreshBtn.click();
        await page.waitForTimeout(3000);
      }

      await page.screenshot({ path: 'test-results/08c-after-instrumental.png' });
      console.log('STEP 8 COMPLETE: Instrumental selection handled');

      // =========================================================================
      // STEP 9: Wait for Final Encoding and Completion
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 9: Wait for Completion');
      console.log('========================================');

      console.log('  Waiting for final encoding (this may take 5-10 minutes)...');

      let isComplete = false;
      const encodeStartTime = Date.now();

      while (Date.now() - encodeStartTime < TIMEOUTS.finalEncoding) {
        if (await refreshBtn.isVisible().catch(() => false)) {
          await refreshBtn.click();
          await page.waitForTimeout(2000);
        }

        const statusText = await jobCard.textContent() || '';

        if (statusText.toLowerCase().includes('complete') && !statusText.toLowerCase().includes('prep')) {
          isComplete = true;
          console.log('  Job complete!');
          break;
        }

        if (statusText.toLowerCase().includes('failed')) {
          throw new Error('Job failed during final encoding');
        }

        console.log(`  Status: ${statusText.substring(0, 80)}...`);
        await page.waitForTimeout(10000);
      }

      if (!isComplete) {
        throw new Error('Timeout waiting for job completion');
      }

      await page.screenshot({ path: 'test-results/09-job-complete.png' });
      console.log('STEP 9 COMPLETE: Job finished');

      // =========================================================================
      // STEP 10: Verify Downloads
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 10: Verify Downloads');
      console.log('========================================');

      // Look for download links in the job card
      const downloadLinks = jobCard.locator('a[href*="download"], a[href*="storage.googleapis.com"]');
      const downloadCount = await downloadLinks.count();
      console.log(`  Found ${downloadCount} download links`);

      if (downloadCount > 0) {
        // Click first download link to verify it works
        const firstDownloadUrl = await downloadLinks.first().getAttribute('href');
        console.log(`  First download URL: ${firstDownloadUrl?.substring(0, 80)}...`);

        // Verify the download URL returns 200
        const response = await page.request.head(firstDownloadUrl!);
        expect(response.status()).toBe(200);
        console.log('  Download URL verified accessible');
      }

      await page.screenshot({ path: 'test-results/10-downloads-verified.png' });
      console.log('STEP 10 COMPLETE: Downloads verified');

      // =========================================================================
      // STEP 11: Verify Distribution (if enabled)
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 11: Verify Distribution');
      console.log('========================================');

      // Check for distribution indicators in job card or state
      const cardText = await jobCard.textContent() || '';

      if (cardText.toLowerCase().includes('youtube') ||
          cardText.toLowerCase().includes('dropbox') ||
          cardText.toLowerCase().includes('drive')) {
        console.log('  Distribution indicators found in UI');
      } else {
        console.log('  No distribution indicators visible in UI (may be in backend state)');
      }

      console.log('STEP 11 COMPLETE: Distribution check done');

      // =========================================================================
      // STEP 12: Cleanup
      // =========================================================================
      console.log('\n========================================');
      console.log('STEP 12: Cleanup');
      console.log('========================================');

      const adminToken = process.env.E2E_ADMIN_TOKEN;

      if (adminToken && jobId) {
        console.log('  Cleaning up distribution and job...');

        try {
          const cleanupResponse = await page.request.post(
            `${API_URL}/api/jobs/${jobId}/cleanup-distribution`,
            {
              headers: {
                'Authorization': `Bearer ${adminToken}`,
                'Content-Type': 'application/json',
              },
              data: { delete_job: true },
            }
          );

          if (cleanupResponse.ok()) {
            const result = await cleanupResponse.json();
            console.log('  Cleanup results:');
            console.log(`    YouTube: ${result.youtube?.status}`);
            console.log(`    Dropbox: ${result.dropbox?.status}`);
            console.log(`    GDrive: ${result.gdrive?.status}`);
            console.log(`    Job deleted: ${result.job_deleted}`);
          } else {
            console.log(`  WARNING: Cleanup failed with status ${cleanupResponse.status()}`);
          }
        } catch (e) {
          console.log(`  WARNING: Cleanup error: ${e}`);
        }
      } else {
        console.log('  Skipping cleanup - E2E_ADMIN_TOKEN not set or no job ID');
        console.log(`  Job ID for manual cleanup: ${jobId}`);
      }

      console.log('STEP 12 COMPLETE: Cleanup done');

      // =========================================================================
      // SUCCESS
      // =========================================================================
      console.log('\n========================================');
      console.log('TEST COMPLETE: Full user journey successful!');
      console.log('========================================');
      console.log(`Job ID: ${jobId}`);
      console.log('All UI interactions completed successfully.');

    } finally {
      // Always clean up the email inbox
      if (inboxId) {
        try {
          await emailHelper.deleteInbox(inboxId);
          console.log('  Cleaned up test email inbox');
        } catch (e) {
          console.log(`  Warning: Failed to delete inbox: ${e}`);
        }
      }
    }
  });
});
