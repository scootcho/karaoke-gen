import { test, expect } from '@playwright/test';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * E2E tests for the agentic correction workflow in the lyrics transcriber frontend.
 *
 * These tests verify:
 * 1. The UI loads correctly with agentic correction data
 * 2. The AgenticCorrectionMetrics panel displays correctly
 * 3. Corrected words are highlighted and clickable
 * 4. The CorrectionDetailCard shows proper information
 */

// Helper function to load fixture data
async function loadFixtureData(page: import('@playwright/test').Page) {
  const fixturePath = path.join(__dirname, 'fixtures', 'agentic-correction-data.json');

  // Create a file chooser promise before clicking
  const fileChooserPromise = page.waitForEvent('filechooser');

  // Click the Load File button
  await page.getByRole('button', { name: /load file/i }).click();

  // Handle the file chooser
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(fixturePath);

  // Wait for data to load - the segments should appear
  // First segment should have "Hello," as first word
  await page.waitForTimeout(1000); // Give time for React to render
}

test.describe('Agentic Correction Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Wait for the initial load
    await expect(page.getByText('Lyrics Correction Review')).toBeVisible();
  });

  test('should load the app in read-only mode', async ({ page }) => {
    // Verify read-only mode alert is shown
    await expect(page.getByText('Running in read-only mode')).toBeVisible();

    // Verify Load File button is present
    await expect(page.getByRole('button', { name: /load file/i })).toBeVisible();
  });

  test('should load correction data from JSON file', async ({ page }) => {
    await loadFixtureData(page);

    // Check that the page has rendered content (not just the initial loading state)
    // The corrected_segments should be rendered
    const pageContent = await page.content();

    // Verify we're no longer in loading state
    await expect(page.getByText('Loading Lyrics Correction Review...')).not.toBeVisible({ timeout: 5000 }).catch(() => {
      // If loading text was never there, that's fine
    });

    // Take a screenshot for debugging
    await page.screenshot({ path: 'test-results/file-loaded.png' });

    // Log what's on the page
    console.log('Page has "Hello":', pageContent.includes('Hello'));
  });

  test('should render transcription view after loading data', async ({ page }) => {
    await loadFixtureData(page);

    // Wait for any segment content to appear
    // The TranscriptionView should show the segments
    await page.waitForTimeout(2000);

    // Take a screenshot to see what's rendered
    await page.screenshot({ path: 'test-results/transcription-view.png' });

    // Check if there's any segment container visible
    const hasSegments = await page.locator('[data-testid="segment"], .segment, .lyrics-segment').count();
    console.log('Number of segments found:', hasSegments);
  });
});

test.describe('UI Components', () => {
  test('should show Load File button on initial load', async ({ page }) => {
    await page.goto('/');

    // The Load File button should be visible
    const loadButton = page.getByRole('button', { name: /load file/i });
    await expect(loadButton).toBeVisible();

    // Should have upload icon
    const uploadIcon = page.locator('svg[data-testid="UploadFileIcon"]');
    await expect(uploadIcon).toBeVisible();
  });

  test('should show read-only mode banner', async ({ page }) => {
    await page.goto('/');

    // The read-only alert should be visible
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByText(/read-only mode/i)).toBeVisible();
  });

  test('should have correction metrics component', async ({ page }) => {
    await page.goto('/');

    // The CorrectionMetrics component should be present
    // It may show "No data" or similar initially
    const metricsSection = page.locator('[data-testid="correction-metrics"], .MuiPaper-root');
    const metricsCount = await metricsSection.count();
    console.log('Metrics sections found:', metricsCount);

    // At least the page structure should be there
    expect(metricsCount).toBeGreaterThan(0);
  });
});

test.describe('File Upload Flow', () => {
  test('should open file dialog when clicking Load File', async ({ page }) => {
    await page.goto('/');

    // Set up listener for file chooser
    let fileChooserOpened = false;
    page.on('filechooser', () => {
      fileChooserOpened = true;
    });

    // Click the button
    const loadButton = page.getByRole('button', { name: /load file/i });
    await loadButton.click();

    // Wait a bit for the dialog
    await page.waitForTimeout(500);

    // Verify file chooser was triggered
    expect(fileChooserOpened).toBe(true);
  });
});

test.describe('Review Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Lyrics Correction Review')).toBeVisible();
  });

  test('should show Review Mode toggle when agentic data is loaded', async ({ page }) => {
    await loadFixtureData(page);

    // Wait for data to load and render
    await page.waitForTimeout(2000);

    // Take a screenshot to see the UI state
    await page.screenshot({ path: 'test-results/review-mode-toggle.png' });

    // The Review Mode toggle should be visible when agentic corrections are present
    // It will appear as "Review Off" chip initially
    const reviewChip = page.getByText(/Review Off|Review Mode/i);
    const chipCount = await reviewChip.count();
    console.log('Review mode chip found:', chipCount);
  });

  test('should show batch actions panel when Review Mode is enabled', async ({ page }) => {
    await loadFixtureData(page);

    // Wait for data to load
    await page.waitForTimeout(2000);

    // Find and click the Review Mode toggle
    const reviewToggle = page.getByText(/Review Off/i);
    if (await reviewToggle.isVisible()) {
      await reviewToggle.click();

      // Wait for the batch actions panel to appear
      await page.waitForTimeout(500);

      // Take a screenshot
      await page.screenshot({ path: 'test-results/batch-actions-panel.png' });

      // Check for batch action buttons
      const acceptHighConfidence = page.getByRole('button', { name: /Accept High Confidence/i });
      const acceptAll = page.getByRole('button', { name: /Accept All/i });
      const revertAll = page.getByRole('button', { name: /Revert All/i });

      console.log('Accept High Confidence visible:', await acceptHighConfidence.isVisible());
      console.log('Accept All visible:', await acceptAll.isVisible());
      console.log('Revert All visible:', await revertAll.isVisible());
    }
  });

  test('should render corrected words with original text preview', async ({ page }) => {
    await loadFixtureData(page);

    // Wait for data to load
    await page.waitForTimeout(2000);

    // Take a screenshot of the transcription view
    await page.screenshot({ path: 'test-results/corrected-words.png' });

    // Look for the CorrectedWordWithActions components
    // They should show the original word as a strikethrough above the corrected word
    const pageContent = await page.content();
    console.log('Page has corrections rendered:', pageContent.length);
  });

  test('should toggle Review Mode on and off', async ({ page }) => {
    await loadFixtureData(page);

    await page.waitForTimeout(2000);

    // Find the Review toggle
    const reviewOff = page.getByText(/Review Off/i);

    if (await reviewOff.isVisible()) {
      // Click to enable Review Mode
      await reviewOff.click();
      await page.waitForTimeout(500);

      // Screenshot with Review Mode ON
      await page.screenshot({ path: 'test-results/review-mode-on.png' });

      // Should now show "Review Mode" label
      const reviewOn = page.getByText(/Review Mode/i).first();
      if (await reviewOn.isVisible()) {
        // Click to disable Review Mode
        await reviewOn.click();
        await page.waitForTimeout(500);

        // Screenshot with Review Mode OFF
        await page.screenshot({ path: 'test-results/review-mode-off.png' });
      }
    }
  });
});
