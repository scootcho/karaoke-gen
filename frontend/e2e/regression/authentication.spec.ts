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
    await page.locator('textarea').fill('ok');

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
    await page.locator('textarea').fill(
      'I want to create karaoke videos for my favorite songs!'
    );
    await page.locator('input[type="checkbox"]').check();

    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should redirect to app
    await page.waitForURL(/\/app/, { timeout: 10000 });
    expect(page.url()).toContain('/app');
  });
});

test.describe('Authentication - Token Persistence', () => {
  test('token persists across page navigation', async ({ page }) => {
    await setAuthToken(page, 'persistent-test-token');

    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
      ],
    });

    // Navigate to app
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Check token is set
    const token = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));
    expect(token).toBe('persistent-test-token');

    // Navigate to another page section and back
    await page.goto('/');
    await page.waitForURL(/\/app/, { timeout: 5000 }); // Should redirect back

    // Token should still be there
    const tokenAfter = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));
    expect(tokenAfter).toBe('persistent-test-token');
  });

  test('unauthenticated users redirect to landing', async ({ page }) => {
    await clearAuthToken(page);
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/app');

    // Should redirect to landing
    await page.waitForURL(/^\/$|gen\.nomadkaraoke\.com\/?$/, { timeout: 5000 });
  });
});
