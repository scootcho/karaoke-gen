import { test, expect } from '@playwright/test';
import { setupApiFixtures, setAuthToken, clearAuthToken } from '../fixtures/test-helper';

/**
 * Smoke Tests - Quick CI validation (~2 min max)
 *
 * These tests run on every PR to catch critical regressions fast.
 * For comprehensive E2E tests, add the 'e2e' label to the PR.
 */

test.describe('Smoke Tests', () => {
  test('landing page loads and shows hero', async ({ page }) => {
    await clearAuthToken(page);
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Hero section visible
    await expect(page.locator('h1')).toContainText('Karaoke');
    await expect(page.locator('nav')).toBeVisible();
  });

  test('sign in dialog opens', async ({ page }) => {
    await clearAuthToken(page);
    await setupApiFixtures(page, { mocks: [] });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /sign in/i }).click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('input[type="email"]')).toBeVisible();
  });

  test('app page loads for authenticated user', async ({ page }) => {
    await setAuthToken(page, 'test-token');
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: { body: { email: 'test@example.com', credits: 5 } },
        },
        {
          method: 'GET',
          path: '/api/themes',
          response: { body: { themes: [] } },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // App content visible - tabs should be present
    await expect(page.getByRole('tab', { name: /search/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /upload/i })).toBeVisible();
  });

  test('search form is functional', async ({ page }) => {
    await setAuthToken(page, 'test-token');
    await setupApiFixtures(page, {
      mocks: [
        {
          method: 'GET',
          path: '/api/jobs',
          response: { body: [] },
        },
        {
          method: 'GET',
          path: '/api/users/me',
          response: { body: { email: 'test@example.com', credits: 5 } },
        },
        {
          method: 'GET',
          path: '/api/themes',
          response: { body: { themes: [] } },
        },
      ],
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    await page.getByRole('tab', { name: /search/i }).click();

    // Form inputs visible and functional
    const artistInput = page.getByLabel('Artist');
    const titleInput = page.getByLabel('Title');

    await expect(artistInput).toBeVisible();
    await expect(titleInput).toBeVisible();

    await artistInput.fill('Test Artist');
    await titleInput.fill('Test Song');

    await expect(artistInput).toHaveValue('Test Artist');
    await expect(titleInput).toHaveValue('Test Song');
  });
});
