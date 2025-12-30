/**
 * Helper script to capture a valid token by logging in manually.
 *
 * Run this when MailSlurp rate limits are reached:
 *   npx playwright test --config=playwright.production.config.ts -g "capture token" --headed
 *
 * This will open a browser where you can:
 * 1. Complete beta enrollment manually (use your real email)
 * 2. Or log in if you already have an account
 *
 * The script will capture and display the token for you to add to .env.local
 */

import { test, expect } from '@playwright/test';

const PROD_URL = 'https://gen.nomadkaraoke.com';

test.describe('Token Capture Helper', () => {
  test('capture token - manually log in and capture token', async ({ page }) => {
    // This test is designed for manual login, so give plenty of time
    test.setTimeout(300000); // 5 minutes

    console.log('\n========================================');
    console.log('TOKEN CAPTURE HELPER');
    console.log('========================================');
    console.log('');
    console.log('Instructions:');
    console.log('1. A browser window will open to gen.nomadkaraoke.com');
    console.log('2. Complete beta enrollment or log in with an existing account');
    console.log('3. Once you see the app page, the script will capture your token');
    console.log('');
    console.log('Starting browser...');
    console.log('');

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Wait for user to complete login (they should end up on /app)
    console.log('Waiting for you to log in...');
    console.log('(Complete beta enrollment or log in, then wait for /app page)');
    console.log('');

    // Poll for login completion - user should end up on /app
    let loggedIn = false;
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes at 1s intervals

    while (!loggedIn && attempts < maxAttempts) {
      const url = page.url();

      if (url.includes('/app')) {
        // Check if token is in localStorage
        const token = await page.evaluate(() =>
          localStorage.getItem('karaoke_access_token')
        );

        if (token) {
          loggedIn = true;

          console.log('========================================');
          console.log('TOKEN CAPTURED SUCCESSFULLY!');
          console.log('========================================');
          console.log('');
          console.log('Add this to your .env.local file:');
          console.log('');
          console.log(`KARAOKE_ACCESS_TOKEN=${token}`);
          console.log('');
          console.log('========================================');

          // Verify the token works
          const response = await page.request.get('https://api.nomadkaraoke.com/api/users/me', {
            headers: { Authorization: `Bearer ${token}` }
          });

          if (response.ok()) {
            const data = await response.json();
            const user = data.user || data;
            console.log(`Token verified for: ${user.email}`);
            console.log(`Credits available: ${user.credits}`);
          } else {
            console.log('Warning: Token verification failed, but it may still work');
          }

          expect(token).toBeTruthy();
          break;
        }
      }

      await page.waitForTimeout(1000);
      attempts++;

      if (attempts % 30 === 0) {
        console.log(`Still waiting... (${Math.round(attempts / 60)} min elapsed)`);
      }
    }

    if (!loggedIn) {
      console.log('');
      console.log('Timeout - no token captured.');
      console.log('Make sure you completed login and reached the /app page.');
      expect(loggedIn).toBe(true);
    }
  });
});
