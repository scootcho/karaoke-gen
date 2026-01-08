/**
 * Screenshot capture script for PR documentation.
 * Run with: npm run test:e2e -- tests/take-screenshots.spec.ts
 */

import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const SCREENSHOT_DIR = path.join(__dirname, '..', '..', 'public', 'screenshots');

test.describe('PR Screenshots', () => {
  test.beforeAll(async () => {
    // Ensure screenshot directory exists
    if (!fs.existsSync(SCREENSHOT_DIR)) {
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }
  });

  test('capture homepage', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('https://gen.nomadkaraoke.com', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    // Hero section
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'homepage-hero.png'),
    });

    // Full page
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'homepage-full.png'),
      fullPage: true,
    });
  });

  test('capture lyrics review UI', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    const lyricsUrl = 'http://localhost:8766?baseApiUrl=http%3A%2F%2Flocalhost%3A8766%2Fapi';

    try {
      await page.goto(lyricsUrl, { waitUntil: 'networkidle', timeout: 10000 });
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'lyrics-review.png'),
      });
    } catch (e) {
      console.log('Warning: Could not capture lyrics review UI. Make sure test-lyrics-review.py is running.');
    }
  });

  test('capture email templates', async ({ page }) => {
    await page.setViewportSize({ width: 700, height: 900 });

    const emailDir = '/tmp/email-previews';
    const emails = ['job_completion', 'action_reminder', 'beta_welcome'];

    for (const emailName of emails) {
      const emailPath = path.join(emailDir, `${emailName}.html`);
      if (fs.existsSync(emailPath)) {
        await page.goto(`file://${emailPath}`, { waitUntil: 'load' });
        await page.waitForTimeout(300);

        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, `email-${emailName}.png`),
        });
      }
    }
  });
});
