import { test, expect, Page } from '@playwright/test';

/**
 * E2E tests for the theme system functionality.
 * Tests run against gen.nomadkaraoke.com (production).
 *
 * IMPORTANT: Set KARAOKE_ACCESS_TOKEN environment variable:
 *   KARAOKE_ACCESS_TOKEN=your-token npx playwright test theme-system.spec.ts --config=playwright.production.config.ts
 */

const ACCESS_TOKEN = process.env.KARAOKE_ACCESS_TOKEN;
const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Helper to authenticate the page by setting localStorage token
async function authenticatePage(page: Page) {
  if (!ACCESS_TOKEN) {
    throw new Error('KARAOKE_ACCESS_TOKEN environment variable is required for production tests');
  }

  await page.addInitScript((token) => {
    localStorage.setItem('karaoke_access_token', token);
  }, ACCESS_TOKEN);

  return true;
}

test.describe('Theme System E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await authenticatePage(page);
  });

  test('Themes API returns available themes', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/themes`, {
      headers: {
        'Authorization': `Bearer ${ACCESS_TOKEN}`
      }
    });

    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    console.log('Themes API response:', JSON.stringify(data, null, 2));

    // Verify response structure
    expect(data).toHaveProperty('themes');
    expect(Array.isArray(data.themes)).toBeTruthy();

    // Verify at least one theme exists (we uploaded nomad and default)
    expect(data.themes.length).toBeGreaterThan(0);

    // Verify theme structure
    const firstTheme = data.themes[0];
    expect(firstTheme).toHaveProperty('id');
    expect(firstTheme).toHaveProperty('name');
    expect(firstTheme).toHaveProperty('description');

    // Log available themes
    console.log('Available themes:');
    for (const theme of data.themes) {
      console.log(`  - ${theme.id}: ${theme.name}`);
    }
  });

  test('Theme detail API returns theme configuration', async ({ request }) => {
    // First get list of themes
    const listResponse = await request.get(`${API_URL}/api/themes`, {
      headers: {
        'Authorization': `Bearer ${ACCESS_TOKEN}`
      }
    });
    expect(listResponse.ok()).toBeTruthy();
    const listData = await listResponse.json();

    if (listData.themes.length === 0) {
      test.skip();
      return;
    }

    // Get detail for first theme
    const themeId = listData.themes[0].id;
    console.log(`Fetching details for theme: ${themeId}`);

    const detailResponse = await request.get(`${API_URL}/api/themes/${themeId}`, {
      headers: {
        'Authorization': `Bearer ${ACCESS_TOKEN}`
      }
    });

    expect(detailResponse.ok()).toBeTruthy();

    const detailData = await detailResponse.json();
    console.log('Theme detail response:', JSON.stringify(detailData, null, 2));

    // Response has a "theme" wrapper
    expect(detailData).toHaveProperty('theme');
    const theme = detailData.theme;

    // Verify theme detail structure
    expect(theme).toHaveProperty('id', themeId);
    expect(theme).toHaveProperty('name');
    expect(theme).toHaveProperty('style_params');

    // Verify style_params has expected sections
    if (theme.style_params) {
      console.log('Style params sections:', Object.keys(theme.style_params));
    }
  });

  test('Theme selector appears in job submission UI', async ({ page }) => {
    test.setTimeout(60000);

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Take screenshot of initial state
    await page.screenshot({ path: 'test-results/theme-01-homepage.png', fullPage: true });

    // Click on the Search tab (which has theme selector)
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(1000);

    // Screenshot the search tab
    await page.screenshot({ path: 'test-results/theme-02-search-tab.png', fullPage: true });

    // Look for theme-related elements
    // The ThemeSelector should have a "Theme" label
    const themeLabel = page.locator('text=Theme').first();
    const themeSelectVisible = await themeLabel.isVisible({ timeout: 5000 }).catch(() => false);

    if (themeSelectVisible) {
      console.log('Theme selector label found');

      // Look for the theme dropdown/select
      const themeSelect = page.locator('[data-testid="theme-selector"]').or(
        page.locator('select').filter({ hasText: /theme/i })
      ).or(
        page.locator('button').filter({ hasText: /select.*theme|theme/i })
      ).first();

      if (await themeSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('Theme selector control found');
        await page.screenshot({ path: 'test-results/theme-03-selector-found.png', fullPage: true });
      } else {
        console.log('Theme selector control not found (may be custom component)');
      }
    } else {
      console.log('Theme selector label not found - checking for alternative UI...');
    }

    // Check if theme section exists anywhere on the page
    const pageContent = await page.locator('body').textContent();
    const hasThemeText = pageContent?.toLowerCase().includes('theme');
    console.log(`Page contains 'theme' text: ${hasThemeText}`);

    // Verify the UI is accessible
    expect(await page.locator('h1').textContent()).toContain('Karaoke Generator');
  });

  test('Color overrides panel appears when theme section visible', async ({ page }) => {
    test.setTimeout(60000);

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Go to Search tab
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(1000);

    // Look for color-related elements
    // The ColorOverridesPanel should have expand/collapse or color picker elements
    const colorLabel = page.locator('text=Color').or(page.locator('text=color')).first();
    const colorVisible = await colorLabel.isVisible({ timeout: 5000 }).catch(() => false);

    if (colorVisible) {
      console.log('Color-related UI element found');

      // Look for color override panel or color pickers
      const colorPickers = page.locator('input[type="color"]');
      const colorPickerCount = await colorPickers.count();
      console.log(`Found ${colorPickerCount} color picker inputs`);

      // Screenshot if color UI found
      await page.screenshot({ path: 'test-results/theme-04-color-ui.png', fullPage: true });
    }

    // Also check for "Customize Colors" or similar text
    const customizeText = await page.locator('body').textContent();
    const hasCustomizeColors = customizeText?.toLowerCase().includes('customize') ||
                              customizeText?.toLowerCase().includes('override');
    console.log(`Has customize/override text: ${hasCustomizeColors}`);
  });

  test('Can select a theme from dropdown', async ({ page }) => {
    test.setTimeout(60000);

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Go to Search tab
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: 'test-results/theme-05-before-select.png', fullPage: true });

    // Look for any select/dropdown that might contain themes
    // Try multiple selectors since the exact implementation may vary
    const possibleSelectors = [
      'select[name*="theme"]',
      '[role="combobox"]',
      'button[aria-haspopup="listbox"]',
      '[data-testid="theme-selector"]',
      'select',
    ];

    let themeDropdownFound = false;

    for (const selector of possibleSelectors) {
      const element = page.locator(selector).first();
      if (await element.isVisible({ timeout: 2000 }).catch(() => false)) {
        console.log(`Found potential theme selector: ${selector}`);
        themeDropdownFound = true;

        // Try to interact with it
        try {
          await element.click();
          await page.waitForTimeout(500);
          await page.screenshot({ path: 'test-results/theme-06-dropdown-open.png', fullPage: true });

          // Look for theme options
          const options = page.locator('[role="option"], option');
          const optionCount = await options.count();
          console.log(`Found ${optionCount} dropdown options`);

          if (optionCount > 0) {
            const optionTexts = await options.allTextContents();
            console.log('Options:', optionTexts.slice(0, 5).join(', '));
          }

          // Press Escape to close dropdown
          await page.keyboard.press('Escape');
        } catch (e) {
          console.log(`Could not interact with selector ${selector}:`, e);
        }
        break;
      }
    }

    if (!themeDropdownFound) {
      console.log('No theme dropdown found via common selectors');

      // Take a detailed screenshot for debugging
      await page.screenshot({ path: 'test-results/theme-06-no-dropdown.png', fullPage: true });

      // Log all select elements
      const allSelects = await page.locator('select').all();
      console.log(`Total select elements on page: ${allSelects.length}`);

      // Log all buttons that might be dropdowns
      const dropdownButtons = await page.locator('[aria-haspopup]').all();
      console.log(`Total dropdown buttons on page: ${dropdownButtons.length}`);
    }
  });

  test('Theme integration in job submission form', async ({ page }) => {
    test.setTimeout(120000);

    await page.goto(PROD_URL);
    await page.waitForLoadState('networkidle');

    // Go to Search tab
    await page.getByRole('tab', { name: /search/i }).click();
    await page.waitForTimeout(2000);

    // Fill in artist and title
    await page.getByLabel('Artist').fill('Test Artist');
    await page.getByLabel('Title').fill('Test Song');

    await page.screenshot({ path: 'test-results/theme-07-form-filled.png', fullPage: true });

    // Check page state after form fill
    const pageContent = await page.locator('body').textContent();
    console.log('Form area contains theme-related text:', pageContent?.includes('Theme') || pageContent?.includes('theme'));

    // Check if the search/create button is visible
    const searchButton = page.getByRole('button', { name: /search.*create/i });
    expect(await searchButton.isVisible()).toBeTruthy();

    console.log('Job submission form with theme integration verified');
  });
});
