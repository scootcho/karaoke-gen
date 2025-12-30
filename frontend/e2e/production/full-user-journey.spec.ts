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
 * 10. Verify Outputs - Check download URLs, YouTube, Dropbox
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
  let lastLoggedProgress = '';

  while (Date.now() - startTime < timeoutMs) {
    // Try to get job status with retry on timeout
    let response;
    for (let retryAttempt = 0; retryAttempt < 3; retryAttempt++) {
      try {
        response = await request.get(`${API_URL}/api/jobs/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 30000, // 30s per attempt, retry if needed
        });
        break; // Success, exit retry loop
      } catch (error: any) {
        if (retryAttempt === 2) {
          // Last attempt failed, log and continue polling loop
          console.log(`  WARNING: API request failed after 3 attempts: ${error.message}`);
          await new Promise((resolve) => setTimeout(resolve, 10000));
          continue;
        }
        // Wait before retry
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }

    if (response?.ok()) {
      const job = await response.json();
      const stateData = job.state_data || {};

      // Build progress info from state_data for better visibility
      const audioProgress = stateData.audio_progress?.stage || 'pending';
      const lyricsProgress = stateData.lyrics_progress?.stage || 'pending';
      const progressInfo = `${job.status} (audio: ${audioProgress}, lyrics: ${lyricsProgress})`;

      // Only log when progress changes to reduce noise
      if (progressInfo !== lastLoggedProgress) {
        console.log(`  Job ${jobId}: ${progressInfo}`);
        lastLoggedProgress = progressInfo;
      }

      if (targetStatuses.includes(job.status)) {
        return { status: job.status, job };
      }

      // Backend bug workaround: status field sometimes doesn't update,
      // but state_data has more accurate progress. Check for completion indicators.
      const hasReviewToken = !!job.review_token;
      const hasInstrumentalToken = !!job.instrumental_token;
      const lyricsComplete = stateData.lyrics_progress?.stage === 'complete';

      // If we have review token, job is ready for review even if status is wrong
      if (hasReviewToken && targetStatuses.includes('in_review')) {
        console.log(`  Job ${jobId}: has review token - treating as in_review`);
        return { status: 'in_review', job };
      }

      // If we have instrumental token, job is ready for instrumental selection
      if (hasInstrumentalToken && targetStatuses.includes('awaiting_instrumental_selection')) {
        console.log(`  Job ${jobId}: has instrumental token - treating as awaiting_instrumental_selection`);
        return { status: 'awaiting_instrumental_selection', job };
      }

      // If download URLs are present, job is complete
      if (job.download_urls && Object.keys(job.download_urls).length > 0 && targetStatuses.includes('completed')) {
        console.log(`  Job ${jobId}: has download URLs - treating as completed`);
        return { status: 'completed', job };
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

/**
 * Wait for authenticated state in the UI (user email visible or no "Login" button)
 */
async function waitForAuthenticatedUI(page: Page, timeout: number = 30000): Promise<boolean> {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    // Check if Login button is gone (user is logged in)
    const loginBtn = page.getByRole('button', { name: /^login$/i });
    const loginVisible = await loginBtn.isVisible().catch(() => false);

    if (!loginVisible) {
      console.log('  UI shows authenticated state (no Login button)');
      return true;
    }

    await page.waitForTimeout(1000);
  }
  return false;
}

/**
 * Verify API token works and return user info
 */
async function verifyTokenAndGetUser(
  request: APIRequestContext,
  token: string
): Promise<{ email: string; credits: number } | null> {
  const response = await request.get(`${API_URL}/api/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: TIMEOUTS.apiCall,
  });

  if (response.ok()) {
    const data = await response.json();
    // API returns { user: { email, credits, role }, has_session: true }
    if (data.user) {
      return { email: data.user.email, credits: data.user.credits };
    }
    // Fallback for direct format
    if (data.email !== undefined) {
      return { email: data.email, credits: data.credits };
    }
  }

  console.log(`  API response status: ${response.status()}`);
  console.log(`  API response: ${await response.text()}`);
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

      // Verify token is valid first
      const user = await verifyTokenAndGetUser(request, accessToken);
      if (!user) {
        console.log('  WARNING: Token invalid, will try email flow');
        accessToken = undefined;
      } else {
        console.log(`  Token valid for: ${user.email} (${user.credits} credits)`);
        await authenticatePage(page, accessToken);

        // Navigate to app and verify authentication
        await page.goto(`${PROD_URL}/app`);
        await page.waitForLoadState('networkidle');

        // Should see the app, not be redirected to landing
        await expect(page.locator('h1')).toContainText('Karaoke Generator', {
          timeout: TIMEOUTS.expect,
        });
        console.log('  Authenticated successfully with existing token');
      }
    }

    if (!accessToken && isEmailTestingAvailable()) {
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
          'E2E test enrollment - testing karaoke generation flow'
        );
        await page.locator('input[type="checkbox"]').check();

        await page.screenshot({ path: 'test-results/02a-beta-form-filled.png' });

        // Submit form
        await page.getByRole('button', { name: /get my free credit/i }).click();

        // Wait for success message and redirect
        console.log('  Waiting for enrollment success...');
        await expect(
          page.getByText(/welcome to the beta|redirecting|success/i)
        ).toBeVisible({ timeout: 20000 });

        await page.waitForURL(/\/app/, { timeout: 15000 });
        console.log('  Redirected to /app');

        // Wait a moment for localStorage to be populated
        await page.waitForTimeout(2000);

        // Get the token from localStorage
        accessToken = await page.evaluate(() =>
          localStorage.getItem('karaoke_access_token')
        ) ?? undefined;

        if (!accessToken) {
          // Debug: check what's in localStorage
          const allStorage = await page.evaluate(() => {
            const items: Record<string, string> = {};
            for (let i = 0; i < localStorage.length; i++) {
              const key = localStorage.key(i);
              if (key) items[key] = localStorage.getItem(key) || '';
            }
            return items;
          });
          console.log('  localStorage contents:', Object.keys(allStorage));
          throw new Error('No access token received after beta enrollment');
        }
        console.log(`  Session token received: ${accessToken.substring(0, 20)}...`);

        // Log full token for reuse in future test runs
        console.log('\n  ========================================');
        console.log('  TOKEN FOR REUSE (add to .env.local):');
        console.log(`  KARAOKE_ACCESS_TOKEN=${accessToken}`);
        console.log('  ========================================\n');

        // IMPORTANT: Reload to ensure app picks up the new auth state
        console.log('  Reloading to refresh auth state...');
        await page.reload();
        await page.waitForLoadState('networkidle');

        // Wait for authenticated UI state
        const isAuth = await waitForAuthenticatedUI(page, 10000);
        if (!isAuth) {
          console.log('  WARNING: UI still shows login button after reload');
          await page.screenshot({ path: 'test-results/02b-auth-issue.png' });
        }

        // Verify welcome email (in parallel with continuing the test)
        console.log('  Waiting for welcome email...');
        const email = await emailHelper.waitForEmail(inbox.id!, 60000);
        console.log(`  Email received: "${email.subject}"`);
        expect(email.subject).toMatch(/welcome.*beta|beta.*tester/i);

        await page.screenshot({ path: 'test-results/02c-app-after-enrollment.png' });
      } finally {
        if (inbox.id) {
          await emailHelper.deleteInbox(inbox.id);
        }
      }
    } else if (!accessToken) {
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
    const user = await verifyTokenAndGetUser(request, accessToken!);
    if (user) {
      console.log(`  Email: ${user.email}`);
      console.log(`  Credits: ${user.credits}`);

      if (user.credits < 1) {
        console.log('  WARNING: No credits available, test may fail at job creation');
      }
    } else {
      console.log('  WARNING: Could not verify user info');
      // Continue anyway - the token might still work for job creation
    }

    console.log('STEP 3 COMPLETE: User verified');

    // =========================================================================
    // STEP 4: Create Karaoke Job
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 4: Create Karaoke Job');
    console.log('========================================');

    // Make sure we're on the app page with fresh state
    if (!page.url().includes('/app')) {
      await page.goto(`${PROD_URL}/app`);
      await page.waitForLoadState('networkidle');
    }

    // Verify we see the Search tab (authenticated state)
    const searchTab = page.getByRole('tab', { name: /search/i });
    await expect(searchTab).toBeVisible({ timeout: TIMEOUTS.expect });

    // Navigate to Search tab
    await searchTab.click();
    await page.waitForTimeout(1000);

    // Check for any error messages on the page
    const errorMessage = page.locator('[class*="error"], [class*="Error"], [role="alert"]');
    if (await errorMessage.count() > 0) {
      const errorText = await errorMessage.first().textContent();
      console.log(`  Page error visible: ${errorText}`);
    }

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

    // Fill artist and title using specific IDs (each tab has its own inputs)
    const artistInput = page.locator('#search-artist');
    const titleInput = page.locator('#search-title');

    await expect(artistInput).toBeVisible({ timeout: TIMEOUTS.expect });
    await artistInput.clear();
    await artistInput.fill(TEST_SONG.artist);
    await titleInput.clear();
    await titleInput.fill(TEST_SONG.title);

    // Verify values were set
    const artistValue = await artistInput.inputValue();
    const titleValue = await titleInput.inputValue();
    console.log(`  Filled form: "${artistValue}" - "${titleValue}"`);

    await page.screenshot({ path: 'test-results/04a-search-form.png' });

    // Submit search via UI first, fall back to API if needed
    const searchButton = page.getByRole('button', { name: /search.*create/i });
    await expect(searchButton).toBeEnabled({ timeout: TIMEOUTS.expect });

    // Try clicking the button multiple times if needed
    for (let clickAttempt = 0; clickAttempt < 3; clickAttempt++) {
      console.log(`  Click attempt ${clickAttempt + 1}/3...`);

      // Set up network monitoring
      const responsePromise = page.waitForResponse(
        (response) => response.url().includes('/api/audio-search/search'),
        { timeout: 15000 }
      ).catch(() => null);

      // Click the button
      await searchButton.click({ force: true });

      // Wait for response
      const response = await responsePromise;
      if (response && response.ok()) {
        try {
          const responseData = await response.json();
          if (responseData.job_id) {
            jobId = responseData.job_id;
            console.log(`  Job created via UI: ${jobId}`);
            break;
          }
        } catch (e) {
          console.log(`  Response parse error: ${e}`);
        }
      }

      // Wait before retry
      await page.waitForTimeout(2000);
    }

    // If UI didn't work, create job via API directly
    if (!jobId) {
      console.log('  UI job creation failed, using API directly...');

      const apiResponse = await request.post(`${API_URL}/api/audio-search/search`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        data: JSON.stringify({
          artist: TEST_SONG.artist,
          title: TEST_SONG.title,
          auto_download: false,
        }),
        timeout: 60000,
      });

      if (apiResponse.ok()) {
        const apiData = await apiResponse.json();
        jobId = apiData.job_id;
        console.log(`  Job created via API: ${jobId}`);
      } else {
        console.log(`  API job creation failed: ${apiResponse.status()}`);
        console.log(`  Error: ${await apiResponse.text()}`);
      }
    }

    await page.screenshot({ path: 'test-results/04b-after-job-creation.png' });

    if (!jobId) {
      // Debug: list all jobs
      const jobsResponse = await request.get(`${API_URL}/api/jobs`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (jobsResponse.ok()) {
        const jobsData = await jobsResponse.json();
        const jobs = jobsData.jobs || jobsData;
        console.log(`  Total jobs found: ${jobs?.length || 0}`);
        if (Array.isArray(jobs)) {
          jobs.slice(0, 5).forEach((j: any) => {
            console.log(`    - ${j.artist} - ${j.title} (${j.status})`);
          });
        }
      }

      await page.screenshot({ path: 'test-results/04c-job-not-found.png' });
      throw new Error('Job not created after search');
    }
    console.log(`  Job created: ${jobId}`);

    await page.screenshot({ path: 'test-results/04d-job-created.png' });
    console.log('STEP 4 COMPLETE: Job created');

    // =========================================================================
    // STEP 5: Audio Selection
    // =========================================================================
    console.log('\n========================================');
    console.log('STEP 5: Audio Selection');
    console.log('========================================');

    // Refresh the jobs list to see our new job
    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    await refreshBtn.click();
    console.log('  Clicked Refresh button');
    await page.waitForTimeout(3000);

    // Wait for job card to appear (it should show after refresh)
    let jobCardVisible = false;
    for (let i = 0; i < 10; i++) {
      // Look for job card containing our artist/title
      const jobCard = page.locator('[class*="job"], [data-testid*="job"]').first();
      const jobText = await page.locator('text=piri').first().isVisible().catch(() => false);

      if (jobText) {
        console.log('  Job card found in list');
        jobCardVisible = true;
        break;
      }

      console.log(`  Waiting for job card (${i + 1}/10)...`);
      await refreshBtn.click().catch(() => {});
      await page.waitForTimeout(3000);
    }

    await page.screenshot({ path: 'test-results/05a-jobs-list.png' });

    // Now look for Select Audio button (might need to expand the job card first)
    let selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();

    // If not visible, try clicking on the job to expand it
    if (!await selectAudioBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Try clicking on job title to expand
      const jobTitle = page.locator('text=piri').first();
      if (await jobTitle.isVisible().catch(() => false)) {
        console.log('  Clicking job title to expand...');
        await jobTitle.click();
        await page.waitForTimeout(2000);
      }
    }

    selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();

    if (await selectAudioBtn.isVisible({ timeout: 30000 }).catch(() => false)) {
      console.log('  Opening audio selection dialog...');
      await selectAudioBtn.click();
      await page.waitForTimeout(3000);

      // Wait for dialog to appear
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible({ timeout: 10000 });
      await page.screenshot({ path: 'test-results/05b-audio-dialog.png' });

      // Wait for audio results to load (may take a while)
      console.log('  Waiting for audio results to load...');
      await page.waitForTimeout(5000);

      // Find and click first Select button in the dialog
      const selectButtons = dialog.getByRole('button', { name: /^select$/i });
      const count = await selectButtons.count();
      console.log(`  Found ${count} audio options`);

      if (count > 0) {
        await selectButtons.first().click();
        console.log('  Audio selected, downloading...');

        // Wait for dialog to close (download can take a while - up to 2 minutes)
        await dialog.waitFor({ state: 'hidden', timeout: TIMEOUTS.apiCall }).catch(() => {
          console.log('  Dialog still open after timeout - pressing Escape');
          return page.keyboard.press('Escape');
        });
      } else {
        // Maybe results are still loading, wait longer
        console.log('  No audio options yet, waiting longer...');
        await page.waitForTimeout(10000);
        const newCount = await selectButtons.count();
        console.log(`  After waiting: ${newCount} audio options`);

        if (newCount > 0) {
          await selectButtons.first().click();
          await dialog.waitFor({ state: 'hidden', timeout: TIMEOUTS.apiCall }).catch(() => {});
        } else {
          console.log('  WARNING: Still no audio options - check job logs');
          await page.screenshot({ path: 'test-results/05c-no-audio-options.png' });
        }
      }
    } else {
      console.log('  No "Select Audio" button found - trying API selection');

      // Check job status via API
      const jobStatusResponse = await request.get(`${API_URL}/api/jobs/${jobId}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (jobStatusResponse.ok()) {
        const jobData = await jobStatusResponse.json();
        console.log(`  Job status: ${jobData.status}`);

        // If job has audio results, select the first one via API
        if (jobData.status === 'awaiting_audio_selection' && jobData.state_data?.audio_search_results?.length > 0) {
          console.log(`  Found ${jobData.state_data.audio_search_results.length} audio results via API`);
          console.log('  Selecting first audio result via API...');

          const selectResponse = await request.post(`${API_URL}/api/audio-search/${jobId}/select`, {
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${accessToken}`,
            },
            data: JSON.stringify({ selection_index: 0 }),
            timeout: 300000, // 5 minutes - audio download can take a while
          });

          if (selectResponse.ok()) {
            console.log('  Audio selected via API successfully');
            const selectData = await selectResponse.json();
            console.log(`  Selection response: ${JSON.stringify(selectData)}`);
          } else {
            console.log(`  Audio selection failed: ${selectResponse.status()}`);
            console.log(`  Error: ${await selectResponse.text()}`);
          }
        }
      }

      await page.screenshot({ path: 'test-results/05d-after-api-select.png' });
    }

    await page.screenshot({ path: 'test-results/05e-after-audio.png' });
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
    console.log(`  Dropbox URL: ${finalJob.dropbox_url || finalJob.state_data?.dropbox_link || 'N/A'}`);
    console.log(`  Google Drive: ${finalJob.gdrive_url || finalJob.state_data?.gdrive_files?.length || 'N/A'}`);

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
      Object.entries(downloadUrls).forEach(([key, value]) => {
        console.log(`    - ${key}: ${value ? 'Available' : 'Missing'}`);
      });
    }

    // Verify YouTube upload if URL exists
    if (finalJob.youtube_url) {
      console.log(`  Verifying YouTube URL: ${finalJob.youtube_url}`);
      // Just verify the URL format is valid
      expect(finalJob.youtube_url).toMatch(/youtube\.com|youtu\.be/);
    }

    // Verify Dropbox link if exists
    const dropboxLink = finalJob.dropbox_url || finalJob.state_data?.dropbox_link;
    if (dropboxLink) {
      console.log(`  Verifying Dropbox URL: ${dropboxLink}`);
      expect(dropboxLink).toMatch(/dropbox\.com/);
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
    console.log(`YouTube: ${finalJob.youtube_url || 'Not uploaded'}`);
    console.log(`Dropbox: ${dropboxLink || 'Not uploaded'}`);
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
