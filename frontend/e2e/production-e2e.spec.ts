import { test, expect, Page } from '@playwright/test';

/**
 * Production E2E test - Single complete karaoke generation flow.
 *
 * This test runs against gen.nomadkaraoke.com and creates a REAL karaoke video.
 *
 * Run with:
 *   npx playwright test --config=playwright.production.config.ts --headed
 *
 * The test follows the complete user journey:
 * 1. Select a theme
 * 2. Enter artist/title and search
 * 3. Select an audio source
 * 4. Wait for processing
 * 5. Complete lyrics review
 * 6. Select instrumental
 * 7. Wait for final render
 * 8. Verify completion
 */

const ACCESS_TOKEN = process.env.KARAOKE_ACCESS_TOKEN;
const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Real song - uses cached flacfetch results
const TEST_ARTIST = 'piri';
const TEST_TITLE = 'dog';

async function authenticatePage(page: Page) {
  if (!ACCESS_TOKEN) {
    throw new Error('KARAOKE_ACCESS_TOKEN environment variable is required');
  }
  await page.addInitScript((token) => {
    localStorage.setItem('karaoke_access_token', token);
  }, ACCESS_TOKEN);
}

test.describe('Production E2E', () => {
  test('Complete karaoke generation flow', async ({ page, request }) => {
    test.setTimeout(900000); // 15 minutes

    await authenticatePage(page);

    // ========== STEP 1: Go to homepage ==========
    console.log('\n=== STEP 1: Loading homepage ===');
    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toContainText('Karaoke Generator');
    console.log('Homepage loaded');

    // ========== STEP 2: Go to Search tab and select theme ==========
    console.log('\n=== STEP 2: Search tab + theme selection ===');
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(1000);

    // Select theme (first one in dropdown)
    const themeSelect = page.locator('button[role="combobox"]').first();
    if (await themeSelect.isVisible({ timeout: 3000 })) {
      const currentTheme = await themeSelect.textContent();
      console.log(`Current theme: ${currentTheme}`);

      if (currentTheme?.toLowerCase().includes('select')) {
        await themeSelect.click();
        await page.waitForTimeout(500);
        await page.locator('[role="option"]').first().click();
        await page.waitForTimeout(500);
        console.log('Selected first theme');
      }
    }

    // ========== STEP 3: Fill in artist/title and search ==========
    console.log('\n=== STEP 3: Filling form and searching ===');
    await page.getByLabel('Artist').fill(TEST_ARTIST);
    await page.getByLabel('Title').fill(TEST_TITLE);
    console.log(`Searching for: ${TEST_ARTIST} - ${TEST_TITLE}`);

    await page.screenshot({ path: 'test-results/step3-before-search.png' });

    await page.getByRole('button', { name: /search.*create/i }).click();

    // Wait for search to complete (loading spinner -> results)
    console.log('Waiting for search results...');
    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'test-results/step3-after-search.png' });

    // ========== STEP 4: Select audio source ==========
    console.log('\n=== STEP 4: Selecting audio source ===');

    // The search creates a job and shows audio options
    // Look for "Select Audio" button on the job card
    const selectAudioBtn = page.getByRole('button', { name: /select audio/i }).first();

    if (await selectAudioBtn.isVisible({ timeout: 30000 })) {
      console.log('Found "Select Audio" button, clicking...');
      await selectAudioBtn.click();
      await page.waitForTimeout(2000);

      // A dialog should open with audio options
      const dialog = page.locator('[role="dialog"]');
      if (await dialog.isVisible({ timeout: 5000 })) {
        await page.screenshot({ path: 'test-results/step4-audio-dialog.png' });

        // Find all "Select" buttons in the dialog
        const selectButtons = dialog.getByRole('button', { name: /^select$/i });
        const count = await selectButtons.count();
        console.log(`Found ${count} audio options`);

        if (count > 0) {
          console.log('Clicking first audio option...');
          await selectButtons.first().click();

          // Wait for dialog to close and download to start
          await page.waitForTimeout(5000);
          console.log('Audio selected, download should start');
        } else {
          console.log('ERROR: No Select buttons found in dialog');
          const dialogContent = await dialog.textContent();
          console.log('Dialog content:', dialogContent?.substring(0, 500));
        }
      } else {
        console.log('ERROR: Dialog did not open');
      }
    } else {
      console.log('ERROR: "Select Audio" button not found');
      // Maybe job auto-started? Check job status
      const pageContent = await page.locator('body').textContent();
      console.log('Page contains:', pageContent?.substring(0, 500));
    }

    await page.screenshot({ path: 'test-results/step4-after-audio-select.png' });

    // ========== STEP 5: Wait for processing and lyrics review ==========
    console.log('\n=== STEP 5: Waiting for job to reach review stage ===');

    // Poll the jobs API to check status
    let jobId: string | null = null;
    let jobStatus: string | null = null;

    for (let i = 0; i < 60; i++) { // 5 minutes of polling
      const response = await request.get(`${API_URL}/api/jobs`, {
        headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        timeout: 120000 // 2 minute timeout for API calls
      });

      if (response.ok()) {
        const data = await response.json();
        const jobs = data.jobs || data;

        // Find our job
        const ourJob = Array.isArray(jobs)
          ? jobs.find((j: any) =>
              j.artist?.toLowerCase() === TEST_ARTIST.toLowerCase() &&
              j.title?.toLowerCase() === TEST_TITLE.toLowerCase())
          : null;

        if (ourJob) {
          jobId = ourJob.job_id;
          jobStatus = ourJob.status;
          console.log(`Job ${jobId}: ${jobStatus}`);

          // Check if we've reached a milestone
          if (jobStatus === 'in_review') {
            console.log('Job reached lyrics review stage!');
            break;
          } else if (jobStatus === 'awaiting_instrumental_selection') {
            console.log('Job skipped review, at instrumental selection');
            break;
          } else if (jobStatus === 'completed') {
            console.log('Job already completed!');
            break;
          } else if (jobStatus === 'failed') {
            throw new Error(`Job failed: ${ourJob.error_message || 'Unknown error'}`);
          }
        }
      }

      // Refresh the page periodically
      if (i % 6 === 0) {
        await page.getByRole('button', { name: /refresh/i }).click().catch(() => {});
      }

      await page.waitForTimeout(5000);
    }

    if (!jobId) {
      throw new Error('Could not find our job after 5 minutes');
    }

    await page.screenshot({ path: 'test-results/step5-job-status.png' });

    // ========== STEP 6: Complete lyrics review (if needed) ==========
    if (jobStatus === 'in_review') {
      console.log('\n=== STEP 6: Completing lyrics review ===');

      await page.reload();
      await page.waitForLoadState('networkidle');

      const reviewBtn = page.getByRole('button', { name: /review.*lyrics/i }).first();

      if (await reviewBtn.isVisible({ timeout: 10000 })) {
        console.log('Opening lyrics review...');

        // This opens a new tab
        const [popup] = await Promise.all([
          page.context().waitForEvent('page', { timeout: 15000 }).catch(() => null),
          reviewBtn.click()
        ]);

        if (popup) {
          await popup.waitForLoadState('networkidle');
          await popup.waitForTimeout(5000);
          await popup.screenshot({ path: 'test-results/step6-review-ui.png', fullPage: true });

          // Click Preview Video
          const previewBtn = popup.getByRole('button', { name: /preview.*video/i }).first();
          if (await previewBtn.isVisible({ timeout: 5000 })) {
            console.log('Clicking Preview Video...');
            await previewBtn.click();
            await popup.waitForTimeout(30000); // Wait for preview to generate

            // Click Complete Review
            const completeBtn = popup.getByRole('button', { name: /complete.*review/i }).first();
            if (await completeBtn.isVisible({ timeout: 60000 })) {
              console.log('Clicking Complete Review...');
              await completeBtn.click();
              await popup.waitForTimeout(3000);
            }
          }

          if (!popup.isClosed()) {
            await popup.close();
          }
        }
      }
    }

    // ========== STEP 7: Handle instrumental selection (if needed) ==========
    console.log('\n=== STEP 7: Checking for instrumental selection ===');

    // Wait and check status
    for (let i = 0; i < 12; i++) { // 1 minute
      const response = await request.get(`${API_URL}/api/jobs/${jobId}`, {
        headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        timeout: 120000
      });

      if (response.ok()) {
        const job = await response.json();
        console.log(`Job status: ${job.status}`);

        if (job.status === 'awaiting_instrumental_selection') {
          console.log('Handling instrumental selection...');

          await page.reload();
          await page.waitForLoadState('networkidle');

          const instrumentalBtn = page.getByRole('button', { name: /select.*instrumental/i }).first();
          if (await instrumentalBtn.isVisible({ timeout: 10000 })) {
            await instrumentalBtn.click();
            await page.waitForTimeout(2000);

            const dialog = page.locator('[role="dialog"]');
            if (await dialog.isVisible()) {
              await page.screenshot({ path: 'test-results/step7-instrumental.png' });

              // Select clean instrumental
              const cleanBtn = dialog.getByRole('button').first();
              await cleanBtn.click();
              await page.waitForTimeout(3000);
              console.log('Selected instrumental');
            }
          }
          break;
        } else if (job.status === 'completed' || job.status === 'processing') {
          break;
        }
      }

      await page.waitForTimeout(5000);
    }

    // ========== STEP 8: Wait for completion ==========
    console.log('\n=== STEP 8: Waiting for completion ===');

    for (let i = 0; i < 60; i++) { // 5 minutes
      const response = await request.get(`${API_URL}/api/jobs/${jobId}`, {
        headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        timeout: 120000
      });

      if (response.ok()) {
        const job = await response.json();
        console.log(`Job status: ${job.status}`);

        if (job.status === 'completed') {
          console.log('\n🎉 JOB COMPLETED SUCCESSFULLY!');
          console.log(`Theme ID: ${job.theme_id}`);
          console.log(`YouTube URL: ${job.youtube_url || 'N/A'}`);
          console.log(`Dropbox URL: ${job.dropbox_url || 'N/A'}`);

          // Final verification
          expect(job.theme_id).toBeTruthy();

          await page.reload();
          await page.screenshot({ path: 'test-results/step8-completed.png', fullPage: true });
          return; // SUCCESS
        } else if (job.status === 'failed') {
          throw new Error(`Job failed: ${job.error_message || 'Unknown error'}`);
        }
      }

      await page.waitForTimeout(5000);
    }

    throw new Error('Job did not complete within timeout');
  });
});
