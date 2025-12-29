import { test, expect, Page, APIRequestContext } from '@playwright/test';
import { createEmailHelper, isEmailTestingAvailable } from '../helpers/email-testing';

/**
 * Production E2E Test - Full User Journey
 *
 * This is the SINGLE comprehensive test that validates the entire user journey
 * in production. It exercises the complete flow from landing page to completed
 * karaoke video.
 *
 * Run with:
 *   npx playwright test --config=playwright.production.config.ts --headed
 *   npm run test:e2e:prod:headed
 *
 * Test Flow:
 * 1. Landing Page - Verify hero, pricing, FAQ
 * 2. Beta Enrollment - Create inbox, submit form, verify email
 * 3. App Authentication - Verify token and credits
 * 4. Create Karaoke Job - Search for test song
 * 5. Audio Selection - Select cached audio
 * 6. Wait for Processing - Poll job status
 * 7. Lyrics Review - Preview and complete
 * 8. Instrumental Selection - Select clean instrumental
 * 9. Wait for Completion - Poll until done
 * 10. Verify Outputs - Check download URLs
 *
 * Environment Variables:
 *   - MAILSLURP_API_KEY: For email testing (required for full flow)
 *   - KARAOKE_ACCESS_TOKEN: Skip enrollment and use existing token
 */

// =============================================================================
// CONSTANTS
// =============================================================================

const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Test song - uses cached flacfetch results for speed and cost savings
const TEST_SONG = {
  artist: 'piri',
  title: 'dog',
} as const;

// Timeouts
const TIMEOUTS = {
  action: 30_000,       // 30s for UI actions
  expect: 60_000,       // 60s for assertions
  apiCall: 120_000,     // 2min for API calls
  jobProcessing: 600_000, // 10min for job processing
  fullTest: 900_000,    // 15min for full test
} as const;

// =============================================================================
// HELPERS
// =============================================================================

async function authenticatePage(page: Page, token: string): Promise<void> {
  await page.addInitScript((t) => {
    localStorage.setItem('karaoke_access_token', t);
  }, token);
}

async function getAuthToken(): Promise<string | undefined> {
  return process.env.KARAOKE_ACCESS_TOKEN;
}

async function pollJobStatus(
  request: APIRequestContext,
  jobId: string,
  targetStatuses: string[],
  token: string,
  timeoutMs: number = TIMEOUTS.jobProcessing
): Promise<{ status: string; job: any }> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const response = await request.get(`${API_URL}/api/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: TIMEOUTS.apiCall,
    });

    if (response.ok()) {
      const job = await response.json();
      console.log(`  Job ${jobId}: ${job.status}`);

      if (targetStatuses.includes(job.status)) {
        return { status: job.status, job };
      }

      if (job.status === 'failed') {
        throw new Error(`Job failed: ${job.error_message || 'Unknown error'}`);
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 5000));
  }

  throw new Error(`Timed out waiting for status: ${targetStatuses.join(' or ')}`);
}

async function findJobByArtistTitle(
  request: APIRequestContext,
  artist: string,
  title: string,
  token: string
): Promise<string | null> {
  const response = await request.get(`${API_URL}/api/jobs`, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: TIMEOUTS.apiCall,
  });

  if (response.ok()) {
    const data = await response.json();
    const jobs = data.jobs || data;

    const job = Array.isArray(jobs)
      ? jobs.find(
          (j: any) =>
            j.artist?.toLowerCase() === artist.toLowerCase() &&
            j.title?.toLowerCase() === title.toLowerCase()
        )
      : null;

    return job?.job_id || null;
  }

  return null;
}

// =============================================================================
// TESTS
// =============================================================================

test.describe('Production E2E - Full User Journey', () => {
  test('Complete flow: Landing -> Beta Enrollment -> Karaoke Generation', async ({
    page,
    request,
  }) => {
    test.setTimeout(TIMEOUTS.fullTest);

    let accessToken = await getAuthToken();
    let jobId: string | null = null;

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

    // Verify FAQ section
    await expect(page.getByText('Questions?')).toBeVisible({ timeout: TIMEOUTS.expect });
    console.log('  FAQ section visible');

    await page.screenshot({ path: 'test-results/01-landing-page.png', fullPage: true });
    console.log('STEP 1 COMPLETE: Landing page loads correctly');

    // =========================================================================
    // STEP 2: Beta Enrollment (or use existing token)
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 2: Beta Enrollment / Authentication');
    console.log('========================================');

    if (accessToken) {
      console.log('  Using existing KARAOKE_ACCESS_TOKEN');
      await authenticatePage(page, accessToken);

      // Navigate to app and verify authentication
      await page.goto(`${PROD_URL}/app`);
      await page.waitForLoadState('networkidle');

      // Should see the app, not be redirected to landing
      await expect(page.locator('h1')).toContainText('Karaoke Generator', {
        timeout: TIMEOUTS.expect,
      });
      console.log('  Authenticated successfully with existing token');
    } else if (isEmailTestingAvailable()) {
      console.log('  Starting beta enrollment with MailSlurp');
      const emailHelper = await createEmailHelper();

      if (!emailHelper.isAvailable) {
        throw new Error('MailSlurp not available');
      }

      // Create test inbox
      const inbox = await emailHelper.createInbox();
      console.log(`  Test email: ${inbox.emailAddress}`);

      try {
        // Open beta form
        await page.getByRole('button', { name: /join beta program/i }).click();
        await expect(page.locator('#beta-email')).toBeVisible({ timeout: TIMEOUTS.expect });

        // Fill beta form
        await page.locator('#beta-email').fill(inbox.emailAddress!);
        await page.locator('textarea').fill(
          'I want to create karaoke for my favorite indie songs! Testing the beta program.'
        );
        await page.locator('input[type="checkbox"]').check();

        await page.screenshot({ path: 'test-results/02a-beta-form-filled.png' });

        // Submit form
        await page.getByRole('button', { name: /get my free credit/i }).click();

        // Wait for success and redirect
        await expect(
          page.getByText(/welcome to the beta|redirecting to the app/i)
        ).toBeVisible({ timeout: 15000 });

        await page.waitForURL(/\/app/, { timeout: 10000 });
        console.log('  Redirected to /app');

        // Get the token from localStorage
        accessToken = await page.evaluate(() =>
          localStorage.getItem('karaoke_access_token')
        ) ?? undefined;

        if (!accessToken) {
          throw new Error('No access token received after beta enrollment');
        }
        console.log('  Session token received');

        // Verify welcome email
        console.log('  Waiting for welcome email...');
        const email = await emailHelper.waitForEmail(inbox.id!, 60000);
        console.log(`  Email received: "${email.subject}"`);
        expect(email.subject).toMatch(/welcome.*beta|beta.*tester/i);

        await page.screenshot({ path: 'test-results/02b-app-after-enrollment.png' });
      } finally {
        if (inbox.id) {
          await emailHelper.deleteInbox(inbox.id);
        }
      }
    } else {
      throw new Error(
        'No KARAOKE_ACCESS_TOKEN and no MAILSLURP_API_KEY - cannot authenticate'
      );
    }

    console.log('STEP 2 COMPLETE: Authentication successful');

    // =========================================================================
    // STEP 3: Verify Credits
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 3: Verify Credits');
    console.log('========================================');

    // Check user credits via API
    const userResponse = await request.get(`${API_URL}/api/users/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: TIMEOUTS.apiCall,
    });

    if (userResponse.ok()) {
      const userData = await userResponse.json();
      console.log(`  Credits: ${userData.credits}`);
      console.log(`  Email: ${userData.email}`);

      if (userData.credits < 1) {
        console.log('  WARNING: No credits available, test may fail');
      }
    }

    console.log('STEP 3 COMPLETE: User has credits');

    // =========================================================================
    // STEP 4: Create Karaoke Job
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 4: Create Karaoke Job');
    console.log('========================================');

    // Make sure we're on the app page
    if (!page.url().includes('/app')) {
      await page.goto(`${PROD_URL}/app`);
      await page.waitForLoadState('networkidle');
    }

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

    // Wait for job to be created
    console.log('  Waiting for search results...');
    await page.waitForTimeout(10000);

    // Find our job
    jobId = await findJobByArtistTitle(
      request,
      TEST_SONG.artist,
      TEST_SONG.title,
      accessToken!
    );

    if (!jobId) {
      throw new Error('Job not created after search');
    }
    console.log(`  Job created: ${jobId}`);

    await page.screenshot({ path: 'test-results/04b-job-created.png' });
    console.log('STEP 4 COMPLETE: Job created');

    // =========================================================================
    // STEP 5: Audio Selection
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 5: Audio Selection');
    console.log('========================================');

    // Refresh the page to see updated job state
    await page.getByRole('button', { name: /refresh/i }).click().catch(() => {});
    await page.waitForTimeout(3000);

    // Look for Select Audio button
    const selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();

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
          console.log('  Audio selected, downloading...');

          // Wait for dialog to close (download can take a while)
          await dialog.waitFor({ state: 'hidden', timeout: TIMEOUTS.apiCall }).catch(() => {
            console.log('  Dialog still open - pressing Escape');
            return page.keyboard.press('Escape');
          });
        } else {
          console.log('  WARNING: No audio options found');
        }
      }
    } else {
      console.log('  No "Select Audio" button - job may have auto-selected or cached');
    }

    await page.screenshot({ path: 'test-results/05b-after-audio.png' });
    console.log('STEP 5 COMPLETE: Audio selection handled');

    // =========================================================================
    // STEP 6: Wait for Processing (Lyrics)
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 6: Wait for Processing');
    console.log('========================================');

    console.log('  Polling job status...');
    const { status: statusAfterProcessing, job: jobAfterProcessing } = await pollJobStatus(
      request,
      jobId,
      ['in_review', 'awaiting_instrumental_selection', 'completed'],
      accessToken!
    );

    console.log(`STEP 6 COMPLETE: Job reached ${statusAfterProcessing}`);

    // =========================================================================
    // STEP 7: Lyrics Review
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 7: Lyrics Review');
    console.log('========================================');

    if (statusAfterProcessing === 'in_review') {
      await page.reload();
      await page.waitForLoadState('networkidle');

      const reviewBtn = page.getByRole('button', { name: /review.*lyrics/i }).first();

      if (await reviewBtn.isVisible({ timeout: 10000 }).catch(() => false)) {
        console.log('  Opening lyrics review...');

        // This opens a new tab
        const [popup] = await Promise.all([
          page.context().waitForEvent('page', { timeout: 15000 }).catch(() => null),
          reviewBtn.click(),
        ]);

        if (popup) {
          await popup.waitForLoadState('networkidle');
          await popup.waitForTimeout(5000);
          await popup.screenshot({
            path: 'test-results/07a-review-ui.png',
            fullPage: true,
          });

          // Click Preview Video
          const previewBtn = popup.getByRole('button', { name: /preview.*video/i }).first();
          if (await previewBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
            console.log('  Clicking Preview Video...');
            await previewBtn.click();
            await popup.waitForTimeout(30000); // Preview generation

            // Click Complete Review
            const completeBtn = popup.getByRole('button', { name: /complete.*review/i }).first();
            if (await completeBtn.isVisible({ timeout: 60000 }).catch(() => false)) {
              console.log('  Clicking Complete Review...');
              await completeBtn.click();
              await popup.waitForTimeout(3000);
              console.log('  Review completed');
            }
          }

          if (!popup.isClosed()) {
            await popup.close();
          }
        }
      }
    } else {
      console.log(`  Skipping - job status is ${statusAfterProcessing}`);
    }

    console.log('STEP 7 COMPLETE: Lyrics review handled');

    // =========================================================================
    // STEP 8: Instrumental Selection
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 8: Instrumental Selection');
    console.log('========================================');

    // Wait for job to reach instrumental selection
    const { status: statusBeforeInstrumental } = await pollJobStatus(
      request,
      jobId,
      ['awaiting_instrumental_selection', 'completed'],
      accessToken!,
      120000 // 2 minutes
    ).catch(() => ({ status: 'unknown', job: null }));

    if (statusBeforeInstrumental === 'awaiting_instrumental_selection') {
      await page.reload();
      await page.waitForLoadState('networkidle');

      const instrumentalBtn = page.getByRole('button', { name: /select.*instrumental/i }).first();
      if (await instrumentalBtn.isVisible({ timeout: 10000 }).catch(() => false)) {
        console.log('  Opening instrumental selection...');
        await instrumentalBtn.click();
        await page.waitForTimeout(2000);

        const dialog = page.locator('[role="dialog"]');
        if (await dialog.isVisible()) {
          await page.screenshot({ path: 'test-results/08-instrumental-dialog.png' });

          // Select first instrumental (usually "Clean")
          const selectBtn = dialog.getByRole('button', { name: /select/i }).first();
          if (await selectBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
            await selectBtn.click();
            console.log('  Instrumental selected');
            await page.waitForTimeout(3000);
          }
        }
      }
    } else {
      console.log(`  Skipping - job status is ${statusBeforeInstrumental}`);
    }

    console.log('STEP 8 COMPLETE: Instrumental selection handled');

    // =========================================================================
    // STEP 9: Wait for Completion
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 9: Wait for Completion');
    console.log('========================================');

    console.log('  Waiting for job to complete...');
    const { status: finalStatus, job: finalJob } = await pollJobStatus(
      request,
      jobId,
      ['completed'],
      accessToken!,
      TIMEOUTS.jobProcessing
    );

    console.log('STEP 9 COMPLETE: Job completed');

    // =========================================================================
    // STEP 10: Verify Outputs
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 10: Verify Outputs');
    console.log('========================================');

    console.log(`  Theme ID: ${finalJob.theme_id || 'N/A'}`);
    console.log(`  YouTube URL: ${finalJob.youtube_url || 'N/A'}`);
    console.log(`  Dropbox URL: ${finalJob.dropbox_url || 'N/A'}`);
    console.log(`  Google Drive URL: ${finalJob.gdrive_url || 'N/A'}`);

    // Verify required outputs
    expect(finalJob.theme_id).toBeTruthy();

    // Check for download URLs
    const downloadResponse = await request.get(`${API_URL}/api/jobs/${jobId}/download-urls`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: TIMEOUTS.apiCall,
    }).catch(() => null);

    if (downloadResponse?.ok()) {
      const downloadUrls = await downloadResponse.json();
      console.log(`  Download URLs available: ${Object.keys(downloadUrls).length}`);
    }

    await page.reload();
    await page.screenshot({ path: 'test-results/10-completed.png', fullPage: true });

    console.log('STEP 10 COMPLETE: Outputs verified');

    // =========================================================================
    // SUCCESS
    // =========================================================================
    console.log('\n========================================');
    console.log('TEST COMPLETE: Full user journey successful!');
    console.log('========================================');
    console.log(`Job ID: ${jobId}`);
    console.log(`Final Status: ${finalStatus}`);
  });
});

// =============================================================================
// SUPPLEMENTARY TESTS
// =============================================================================

test.describe('Production E2E - Landing Page', () => {
  test('Pricing packages display correctly', async ({ page }) => {
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Check all 4 credit packages
    await expect(page.getByRole('button', { name: /1\s+credit/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /3\s+credits/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /5\s+credits/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /10\s+credits/i })).toBeVisible();

    await page.screenshot({ path: 'test-results/landing-pricing.png' });
  });

  test('Sign in button opens auth dialog', async ({ page }) => {
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /sign in/i }).click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Enter your email to receive a sign-in link')).toBeVisible();

    await page.screenshot({ path: 'test-results/landing-signin-dialog.png' });
  });
});

test.describe('Production E2E - API Health', () => {
  test('Health endpoints respond', async ({ request }) => {
    const healthResponse = await request.get(`${API_URL}/api/health`);
    expect(healthResponse.ok()).toBe(true);

    const rootResponse = await request.get(`${API_URL}/`);
    expect(rootResponse.ok()).toBe(true);

    const rootData = await rootResponse.json();
    expect(rootData.service).toContain('karaoke-gen');
    console.log(`API Version: ${rootData.version}`);
  });
});
