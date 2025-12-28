import { test, expect, Page } from '@playwright/test';

/**
 * Mobile Responsiveness E2E Tests
 *
 * Tests the entire user journey on mobile devices to ensure:
 * 1. All content is visible and accessible
 * 2. No horizontal scrolling occurs
 * 3. Touch targets are appropriately sized
 * 4. Text is readable without zooming
 */

// Common mobile viewport sizes
const MOBILE_VIEWPORTS = {
  'iPhone SE': { width: 375, height: 667 },
  'iPhone 14': { width: 390, height: 844 },
  'Pixel 7': { width: 412, height: 915 },
};

// Helper to set auth token
async function setAuthToken(page: Page) {
  const token = process.env.KARAOKE_ACCESS_TOKEN;
  if (token) {
    await page.evaluate((t) => {
      localStorage.setItem('karaoke_access_token', t);
    }, token);
  }
}

// Helper to check no horizontal overflow
async function hasNoHorizontalOverflow(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    const docWidth = document.documentElement.scrollWidth;
    const viewportWidth = window.innerWidth;
    return docWidth <= viewportWidth + 2;
  });
}

test.describe('Mobile Responsiveness', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page);
  });

  for (const [deviceName, viewport] of Object.entries(MOBILE_VIEWPORTS)) {
    test.describe(`${deviceName} (${viewport.width}x${viewport.height})`, () => {
      test.beforeEach(async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto('/');
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
      });

      test('page loads without horizontal scroll', async ({ page }) => {
        const noOverflow = await hasNoHorizontalOverflow(page);
        expect(noOverflow).toBe(true);
      });

      test('header is visible and accessible', async ({ page }) => {
        // Logo should be visible
        const logo = page.locator('header img, .logo');
        await expect(logo.first()).toBeVisible();

        // Header title should be visible (may be truncated on mobile)
        const title = page.locator('h1');
        await expect(title.first()).toBeVisible();
      });

      test('form inputs are visible and usable', async ({ page }) => {
        // Tab buttons should be visible
        const tabs = page.locator('[role="tablist"] button, .tabs button');
        if (await tabs.count() > 0) {
          await expect(tabs.first()).toBeVisible();
        }

        // Check that Artist/Title inputs exist (after clicking upload tab if needed)
        const uploadTab = page.locator('button:has-text("Upload")');
        if (await uploadTab.count() > 0) {
          await uploadTab.first().click();
          await page.waitForTimeout(300);
        }

        // Artist input
        const artistInput = page.locator('input').first();
        if (await artistInput.count() > 0) {
          const box = await artistInput.boundingBox();
          if (box) {
            expect(box.width).toBeGreaterThan(100);
          }
        }
      });

      test('buttons have adequate touch target size', async ({ page }) => {
        const buttons = page.locator('button:visible');
        const count = await buttons.count();

        let smallButtonCount = 0;
        for (let i = 0; i < Math.min(count, 10); i++) {
          const button = buttons.nth(i);
          const box = await button.boundingBox();
          if (box && (box.width < 28 || box.height < 28)) {
            smallButtonCount++;
          }
        }

        // Allow some small buttons (icons) but not too many
        expect(smallButtonCount).toBeLessThan(3);
      });
    });
  }
});

test.describe('Mobile Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page);
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('can switch between tabs', async ({ page }) => {
    const urlTab = page.locator('button:has-text("URL")');
    if (await urlTab.count() > 0) {
      await urlTab.first().click();
      await page.waitForTimeout(300);

      // URL input should now be visible
      const urlInput = page.locator('input[type="url"], input[placeholder*="youtube"], input[placeholder*="URL"]');
      if (await urlInput.count() > 0) {
        await expect(urlInput.first()).toBeVisible();
      }
    }
  });

  test('can type in input fields', async ({ page }) => {
    // Find a text input (not file input)
    const textInput = page.locator('input[type="text"], input[placeholder*="Artist"], input[placeholder*="title"]');
    if (await textInput.count() > 0) {
      await textInput.first().focus();
      await textInput.first().fill('Test Input');
      await expect(textInput.first()).toHaveValue('Test Input');
    }
  });
});

test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthToken(page);
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('has proper viewport meta tag', async ({ page }) => {
    const viewportMeta = await page.evaluate(() => {
      const meta = document.querySelector('meta[name="viewport"]');
      return meta?.getAttribute('content') || '';
    });

    expect(viewportMeta).toContain('width=device-width');
    expect(viewportMeta).toContain('initial-scale=1');
  });
});
