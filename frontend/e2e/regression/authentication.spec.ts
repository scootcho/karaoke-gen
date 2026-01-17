import { test, expect } from '@playwright/test';
import { setupApiFixtures, setAuthToken, clearAuthToken } from '../fixtures/test-helper';

/**
 * Regression Tests - Authentication
 *
 * Tests authentication flows using mocked API responses.
 * These tests run offline in CI without hitting production.
 */

test.describe('Authentication - Magic Link', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuthToken(page);
  });

  test('magic link dialog opens from sign in button', async ({ page }) => {
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /sign in/i }).click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Enter your email to receive a sign-in link')).toBeVisible();
  });

  test('magic link dialog validates email format', async ({ page }) => {
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /sign in/i }).click();

    const dialog = page.locator('[role="dialog"]');
    const emailInput = dialog.locator('input[type="email"]');

    // Fill invalid email
    await emailInput.fill('invalid');

    // Try to submit
    await dialog.getByRole('button', { name: /send/i }).click();

    // Should not close dialog (validation failed)
    await expect(dialog).toBeVisible();
  });

  test('magic link request succeeds with valid email', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'POST',
          path: '/api/users/auth/magic-link',
          response: {
            status: 200,
            body: { success: true, message: 'Magic link sent' },
          },
        },
      ],
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /sign in/i }).click();

    const dialog = page.locator('[role="dialog"]');
    await dialog.locator('input[type="email"]').fill('test@example.com');
    await dialog.getByRole('button', { name: /send/i }).click();

    // Should show success message
    await expect(page.getByText(/check your email|magic link sent/i)).toBeVisible({
      timeout: 10000,
    });
  });
});

test.describe('Authentication - Beta Enrollment', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuthToken(page);
  });

  test('beta form opens when clicking join button', async ({ page }) => {
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /join beta program/i }).click();

    await expect(page.locator('#beta-email')).toBeVisible();
    await expect(page.getByRole('button', { name: /get my free credit/i })).toBeVisible();
  });

  test('beta form validates required fields', async ({ page }) => {
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /join beta program/i }).click();
    await expect(page.locator('#beta-email')).toBeVisible();

    // Fill email but not checkbox
    await page.locator('#beta-email').fill('test@example.com');
    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should show validation error
    await expect(page.getByText(/please accept/i)).toBeVisible();
  });

  test('beta form validates feedback promise length', async ({ page }) => {
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /join beta program/i }).click();

    // Fill form with short promise
    await page.locator('#beta-email').fill('test@example.com');
    await page.locator('input[type="checkbox"]').check();
    await page.locator('#beta-promise').fill('ok');

    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should show validation error
    await expect(page.getByText(/please write a sentence/i)).toBeVisible();
  });

  test('beta enrollment success redirects to app', async ({ page }) => {
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'POST',
          path: '/api/users/beta/enroll',
          response: {
            status: 200,
            body: {
              success: true,
              session_token: 'mock-session-token-123',
              credits: 2,
            },
          },
        },
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /join beta program/i }).click();

    // Fill valid form
    await page.locator('#beta-email').fill('test@example.com');
    await page.locator('#beta-promise').fill(
      'I want to create karaoke videos for my favorite songs!'
    );
    await page.locator('input[type="checkbox"]').check();

    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should redirect to app
    await page.waitForURL(/\/app/, { timeout: 10000 });
    expect(page.url()).toContain('/app');
  });

  test('beta enrollment shows credits after redirect to app', async ({ page }) => {
    // This test verifies that after beta enrollment, the /app page
    // correctly fetches and displays user data including credits.
    // This catches the bug where client-side navigation didn't trigger fetchUser().
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'POST',
          path: '/api/users/beta/enroll',
          response: {
            status: 200,
            body: {
              status: 'success',
              message: 'Enrolled in beta',
              credits_granted: 1,
              session_token: 'mock-session-token-456',
            },
          },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: {
            status: 200,
            body: {
              user: {
                email: 'beta-tester@example.com',
                credits: 1,
                role: 'user',
                display_name: null,
                total_jobs_created: 0,
                total_jobs_completed: 0,
              },
              has_session: true,
            },
          },
        },
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Complete beta enrollment
    await page.getByRole('button', { name: /join beta program/i }).click();
    await page.locator('#beta-email').fill('beta-tester@example.com');
    await page.locator('#beta-promise').fill(
      'I want to create a karaoke video for my favorite song!'
    );
    await page.locator('input[type="checkbox"]').check();
    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Wait for redirect to /app
    await page.waitForURL(/\/app/, { timeout: 10000 });

    // Verify credits are displayed in the UI
    // The AuthStatus component should show "1 credit" after fetchUser() completes
    await expect(page.getByText(/1 credit/i)).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Authentication - Token Persistence', () => {
  test('localStorage can store and retrieve tokens', async ({ page }) => {
    // This tests the browser's localStorage functionality
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Set a token
    await page.evaluate(() => {
      localStorage.setItem('test_token', 'my-test-value');
    });

    // Retrieve the token
    const token = await page.evaluate(() => localStorage.getItem('test_token'));
    expect(token).toBe('my-test-value');

    // Token survives navigation
    await page.goto('/#pricing');
    await page.waitForLoadState('networkidle');

    const tokenAfter = await page.evaluate(() => localStorage.getItem('test_token'));
    expect(tokenAfter).toBe('my-test-value');
  });
});
