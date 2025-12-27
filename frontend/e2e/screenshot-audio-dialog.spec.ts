import { test, expect } from '@playwright/test';

/**
 * Test to capture a screenshot of the Audio Search Dialog for visual review
 */
test.describe('Audio Search Dialog Screenshot', () => {
  test.beforeEach(async ({ page }) => {
    // Set the auth token before navigating
    const token = process.env.KARAOKE_ACCESS_TOKEN;
    if (!token) {
      throw new Error('KARAOKE_ACCESS_TOKEN environment variable is required - set in .env.local');
    }

    // Navigate to the app first
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Wait a bit for any dialogs to appear
    await page.waitForTimeout(1000);

    // Check if auth dialog is visible - try multiple selectors
    const authDialog = page.locator('[role="dialog"]').filter({ hasText: /authentication|access token/i });
    const authDialogAlt = page.locator('text=Authentication Required').locator('xpath=ancestor::div[contains(@class, "fixed")]');

    let authVisible = await authDialog.isVisible().catch(() => false);
    if (!authVisible) {
      authVisible = await authDialogAlt.isVisible().catch(() => false);
    }

    // Also check for auth input directly on page
    const authInput = page.locator('input[placeholder*="token" i], input[placeholder*="access" i]').first();
    if (!authVisible && await authInput.isVisible().catch(() => false)) {
      authVisible = true;
    }

    console.log('Auth dialog visible:', authVisible);

    if (authVisible) {
      console.log('Auth dialog detected, filling token...');

      // Find and fill the token input - try multiple strategies
      let tokenInputField = page.locator('input[placeholder*="token" i], input[placeholder*="access" i]').first();
      if (!await tokenInputField.isVisible().catch(() => false)) {
        tokenInputField = page.locator('[role="dialog"] input').first();
      }
      if (!await tokenInputField.isVisible().catch(() => false)) {
        tokenInputField = page.locator('input').first();
      }

      await tokenInputField.waitFor({ state: 'visible', timeout: 5000 });
      await tokenInputField.click();
      await tokenInputField.fill(token);
      console.log('Token filled in input');

      // Wait a moment for the button to become enabled
      await page.waitForTimeout(500);

      // Click the save/submit/authenticate button - look for any enabled button nearby
      const saveButton = page.locator('button:not([disabled])').filter({ hasText: /save|submit|authenticate|connect/i }).first();
      if (await saveButton.isVisible().catch(() => false)) {
        console.log('Clicking save button');
        await saveButton.click();
      } else {
        // Try clicking any enabled submit button
        const anyButton = page.locator('button[type="submit"]:not([disabled]), button:not([disabled])').first();
        console.log('Clicking any enabled button');
        await anyButton.click();
      }

      // Wait for the auth form to disappear
      await page.waitForTimeout(1000);
      console.log('Auth completed');
    } else {
      console.log('No auth dialog, setting token in localStorage');
      // Set the token in localStorage directly (must match key in lib/api.ts)
      await page.evaluate((t) => {
        localStorage.setItem('karaoke_access_token', t);
      }, token);
      await page.reload();
    }

    await page.waitForLoadState('networkidle');
  });

  test('capture audio search dialog screenshot', async ({ page }) => {
    // Set a larger viewport to see full dialog
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Wait for the page to fully load
    await page.waitForLoadState('networkidle');

    // Take screenshot of initial page state
    await page.screenshot({
      path: 'e2e/screenshots/01-initial-page.png',
      fullPage: true
    });

    // Find a job that's in awaiting_audio_selection state
    // First, let's check what jobs are visible
    const jobCards = await page.locator('[class*="border"][class*="rounded"]').filter({
      has: page.locator('text=/processing|pending|awaiting|completed|failed/i')
    }).all();

    console.log(`Found ${jobCards.length} job cards`);

    // Look for a job with "Select Audio" button - wait a bit for the page to fully load
    await page.waitForTimeout(2000);

    // Take a debug screenshot
    await page.screenshot({
      path: 'e2e/screenshots/02-debug-before-button-search.png',
      fullPage: true
    });

    // Log all buttons on the page
    const allButtons = await page.locator('button').all();
    console.log(`Found ${allButtons.length} buttons on page`);
    for (let i = 0; i < Math.min(allButtons.length, 10); i++) {
      const text = await allButtons[i].textContent().catch(() => 'N/A');
      const visible = await allButtons[i].isVisible().catch(() => false);
      console.log(`Button ${i}: "${text?.trim()}" visible=${visible}`);
    }

    // Try multiple selectors for the Select Audio Source button (cards are no longer collapsible)
    const selectAudioButton = page.locator('button').filter({ hasText: /Select Audio Source/i }).first();
    const selectAudioAlt = page.locator('button').filter({ hasText: /Select Audio/i }).first();
    const selectByColor = page.locator('button.bg-blue-600, button[class*="blue-600"]').first();

    let buttonFound = await selectAudioButton.isVisible().catch(() => false);
    console.log('selectAudioButton visible:', buttonFound);

    if (!buttonFound) {
      buttonFound = await selectAudioAlt.isVisible().catch(() => false);
      console.log('selectAudioAlt visible:', buttonFound);
    }

    if (!buttonFound) {
      buttonFound = await selectByColor.isVisible().catch(() => false);
      console.log('selectByColor visible:', buttonFound);
    }

    console.log('Select Audio button found:', buttonFound);

    if (buttonFound) {
      console.log('Found existing job with Select Audio Source button');

      // Take screenshot before clicking
      await page.screenshot({
        path: 'e2e/screenshots/03-before-select-audio.png',
        fullPage: true
      });

      // Click the Select Audio Source button directly (cards are no longer collapsible)
      const clickTarget = await selectAudioButton.isVisible().catch(() => false)
        ? selectAudioButton
        : selectAudioAlt;
      console.log('Clicking Select Audio Source button');
      await clickTarget.click();

      // Wait for dialog to appear
      await page.waitForSelector('[role="dialog"]', { timeout: 10000 });

      // Wait a bit for results to load
      await page.waitForTimeout(2000);

      // Take screenshot of the dialog
      await page.screenshot({
        path: 'e2e/screenshots/04-audio-dialog-full-page.png',
        fullPage: true
      });

      // Also capture just the dialog element
      const dialog = page.locator('[role="dialog"]');
      await dialog.screenshot({
        path: 'e2e/screenshots/05-audio-dialog-element.png'
      });

      // Log dialog dimensions
      const dialogBox = await dialog.boundingBox();
      console.log('Dialog bounding box:', dialogBox);

      // Log viewport size
      const viewport = page.viewportSize();
      console.log('Viewport size:', viewport);

      // Check if dialog is clipped
      if (dialogBox) {
        const isClippedTop = dialogBox.y < 0;
        const isClippedBottom = dialogBox.y + dialogBox.height > (viewport?.height || 0);
        const isClippedLeft = dialogBox.x < 0;
        const isClippedRight = dialogBox.x + dialogBox.width > (viewport?.width || 0);

        console.log('Dialog clipping status:', {
          clippedTop: isClippedTop,
          clippedBottom: isClippedBottom,
          clippedLeft: isClippedLeft,
          clippedRight: isClippedRight,
          dialogHeight: dialogBox.height,
          dialogWidth: dialogBox.width,
          viewportHeight: viewport?.height,
          viewportWidth: viewport?.width
        });
      }

      // Check scrollability of the dialog content
      const scrollableContent = dialog.locator('[class*="overflow"]').first();
      if (await scrollableContent.isVisible().catch(() => false)) {
        const scrollInfo = await scrollableContent.evaluate((el) => ({
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
          scrollTop: el.scrollTop,
          isScrollable: el.scrollHeight > el.clientHeight
        }));
        console.log('Scroll info:', scrollInfo);
      }

    } else {
      console.log('No Select Audio button found, creating a new job...');

      // The form is already visible on the page (not in a dialog)
      // Fill in the form - use a song that will return multiple results
      const artistInput = page.locator('input').filter({ has: page.locator('..', { hasText: /artist/i }) }).first();
      const titleInput = page.locator('input').filter({ has: page.locator('..', { hasText: /title/i }) }).first();

      // Try different selectors for artist/title inputs
      const artistField = page.locator('input[placeholder*="artist" i], input[name*="artist" i]').first();
      const titleField = page.locator('input[placeholder*="title" i], input[name*="title" i]').first();

      if (await artistField.isVisible().catch(() => false)) {
        await artistField.fill('Radiohead');
        await titleField.fill('Creep');
      } else {
        // Find by label
        await page.getByLabel(/artist/i).fill('Radiohead');
        await page.getByLabel(/title/i).fill('Creep');
      }

      await page.screenshot({
        path: 'e2e/screenshots/02-filled-form.png',
        fullPage: true
      });

      // Submit the job - look for the orange "Create Karaoke Video" button
      await page.locator('button:has-text("Create Karaoke Video"), button:has-text("Create"), button[type="submit"]').first().click();

      // Wait for job to be created and transition to audio selection
      console.log('Waiting for job to start audio search...');
      await page.waitForTimeout(5000);

      await page.screenshot({
        path: 'e2e/screenshots/03-after-submit.png',
        fullPage: true
      });

      // Now look for Select Audio Source button - wait up to 60 seconds for audio search to complete
      const newSelectButton = page.locator('button').filter({ hasText: /Select Audio Source/i }).first();
      console.log('Waiting for Select Audio Source button...');

      try {
        await newSelectButton.waitFor({ state: 'visible', timeout: 60000 });

        await page.screenshot({
          path: 'e2e/screenshots/04-job-awaiting-selection.png',
          fullPage: true
        });

        // Click it
        await newSelectButton.click();

        // Wait for dialog
        await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
        await page.waitForTimeout(2000);

        await page.screenshot({
          path: 'e2e/screenshots/05-audio-dialog-full-page.png',
          fullPage: true
        });

        const dialog = page.locator('[role="dialog"]');
        await dialog.screenshot({
          path: 'e2e/screenshots/06-audio-dialog-element.png'
        });

        const dialogBox = await dialog.boundingBox();
        console.log('Dialog bounding box:', dialogBox);
      } catch (err) {
        console.log('Could not find Select Audio button within timeout');
        await page.screenshot({
          path: 'e2e/screenshots/05-timeout-state.png',
          fullPage: true
        });
        throw err;
      }
    }
  });
});
