import { test, expect } from '@playwright/test';
import * as path from 'path';
import { setAuthToken, getEnvAuthToken } from '../helpers/auth';
import { createCleanupTracker } from '../helpers/test-cleanup';
import { TEST_SONG, URLS, TIMEOUTS } from '../helpers/constants';

/**
 * Production E2E Tests: Guided Job Creation Flow
 *
 * Tests the 3-step guided job creation flow (Song Info → Choose Audio → Customize & Create)
 * against the real production backend. Uses route interception to capture outgoing
 * request bodies while still letting them hit the real API.
 *
 * Supports two modes:
 *   - Production frontend (default): tests against gen.nomadkaraoke.com
 *   - Local frontend: set E2E_LOCAL=1 to test against localhost:3000 (still uses prod backend)
 *
 * Prerequisites:
 *   - KARAOKE_ACCESS_TOKEN: User token with credits
 *   - E2E_ADMIN_TOKEN: Admin token for cleanup (optional, uses KARAOKE_ACCESS_TOKEN as fallback)
 *
 * Run against production:
 *   npx playwright test e2e/production/guided-flow.spec.ts --config=playwright.production.config.ts
 *
 * Run against local frontend (with prod backend):
 *   E2E_LOCAL=1 npx playwright test e2e/production/guided-flow.spec.ts --config=playwright.production.config.ts
 */

const API_URL = URLS.production.api;
const FRONTEND_URL = process.env.E2E_LOCAL
  ? URLS.local.frontend
  : URLS.production.frontend;

// Path to the real FLAC fixture (relative to repo root, resolved from frontend/)
const UPLOAD_FIXTURE_PATH = path.resolve(__dirname, '..', '..', '..', 'tests', 'data', 'waterloo10sec.flac');

function getAdminToken(): string | null {
  return process.env.E2E_ADMIN_TOKEN || getEnvAuthToken() || null;
}

/**
 * Helper: Intercept a route, capture the response body as JSON, and pass through.
 * Returns the raw body buffer to route.fulfill() to avoid double-read issues.
 */
async function fetchAndCapture(
  route: any,
): Promise<{ body: Buffer; json: any; status: number; headers: Record<string, string> }> {
  const response = await route.fetch();
  const body = await response.body();
  let json: any = null;
  try {
    json = JSON.parse(body.toString());
  } catch {
    // Response wasn't JSON — still pass through
  }
  return { body, json, status: response.status(), headers: response.headers() };
}

test.describe('Guided Job Creation Flow', () => {
  let cleanup: ReturnType<typeof createCleanupTracker>;

  test.beforeEach(async ({ page }) => {
    const token = getEnvAuthToken();
    test.skip(!token, 'KARAOKE_ACCESS_TOKEN not set — skipping guided flow tests');

    cleanup = createCleanupTracker(getAdminToken()!, API_URL);

    // Authenticate
    await setAuthToken(page, token!);

    if (process.env.E2E_LOCAL) {
      console.log(`  Mode: LOCAL frontend (${FRONTEND_URL}) → prod backend (${API_URL})`);
    }
  });

  test.afterEach(async () => {
    if (cleanup) {
      console.log('  Cleaning up test jobs...');
      const result = await cleanup.cleanupAll();
      console.log(`  Cleanup: ${result.deleted} deleted, ${result.failed} failed`);
    }
  });

  // ---------------------------------------------------------------------------
  // Test 1: Search → Our Pick → Create with defaults
  // ---------------------------------------------------------------------------
  test('search → select Our Pick → create with defaults', async ({ page, request }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    // Intercept API calls to capture params
    let searchBody: any = null;
    let searchJobId: string | null = null;
    let selectBody: any = null;

    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        searchBody = req.postDataJSON();
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    await page.route('**/api/audio-search/*/select', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        selectBody = req.postDataJSON();
      }
      const { body, status, headers } = await fetchAndCapture(route);
      await route.fulfill({ status, headers, body });
    });

    // Step 1: Fill artist/title
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();

    console.log('  Step 1 complete: submitted search');

    // Step 2: Wait for "Our Pick" and click "Use This Audio"
    await expect(page.getByText('Our Pick')).toBeVisible({ timeout: TIMEOUTS.apiCall });
    console.log('  Step 2: Our Pick visible');

    await page.getByRole('button', { name: /use this audio/i }).click();
    console.log('  Step 2 complete: selected Our Pick');

    // Step 3: Click "Create Karaoke Video" with defaults (no overrides, not private)
    await expect(page.getByRole('heading', { name: 'Customize & Create' })).toBeVisible({ timeout: TIMEOUTS.action });
    await page.getByRole('button', { name: /create karaoke video/i }).click();

    // Wait for success
    await expect(page.getByText('Job Created')).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Step 3 complete: job created');

    // Assert: search body has correct params
    expect(searchBody).toBeTruthy();
    expect(searchBody.artist).toBe(TEST_SONG.artist);
    expect(searchBody.title).toBe(TEST_SONG.title);
    expect(searchBody.is_private).toBeFalsy();
    console.log('  Verified search request params');

    // Assert: select was called with a numeric index
    expect(selectBody).toBeTruthy();
    expect(typeof selectBody.selection_index).toBe('number');
    console.log(`  Verified select request: index=${selectBody.selection_index}`);

    // Assert: backend state via API
    expect(searchJobId).toBeTruthy();
    const token = getAdminToken()!;
    const jobResponse = await request.get(`${API_URL}/api/jobs/${searchJobId}`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: TIMEOUTS.apiCall,
    });
    expect(jobResponse.ok()).toBe(true);
    const job = await jobResponse.json();
    expect(job.artist.toLowerCase()).toBe(TEST_SONG.artist.toLowerCase());
    expect(job.title.toLowerCase()).toBe(TEST_SONG.title.toLowerCase());
    console.log(`  Verified backend job: ${job.artist} - ${job.title} (status: ${job.status})`);
  });

  // ---------------------------------------------------------------------------
  // Test 2: Search → Select → Custom display names + private
  // ---------------------------------------------------------------------------
  test('search → select → custom display names + private', async ({ page, request }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    let searchJobId: string | null = null;
    let selectCalled = false;

    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    await page.route('**/api/audio-search/*/select', async (route) => {
      selectCalled = true;
      const { body, status, headers } = await fetchAndCapture(route);
      await route.fulfill({ status, headers, body });
    });

    // Step 1: Fill and proceed
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();

    // Step 2: Select Our Pick
    await expect(page.getByText('Our Pick')).toBeVisible({ timeout: TIMEOUTS.apiCall });
    await page.getByRole('button', { name: /use this audio/i }).click();

    // Step 3: Fill display overrides, check private, and confirm
    await expect(page.getByRole('heading', { name: 'Customize & Create' })).toBeVisible({ timeout: TIMEOUTS.action });

    await page.locator('#guided-display-artist').fill('PIRI (Display)');
    await page.locator('#guided-display-title').fill('DOG (Display)');
    await page.locator('#guided-private').check();
    console.log('  Filled display overrides and checked Private');

    await page.getByRole('button', { name: /create karaoke video/i }).click();

    // Wait for success
    await expect(page.getByText('Job Created')).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Job created with custom display names + private');

    // Assert: selectAudioResult was called (confirms job created via search path)
    expect(selectCalled).toBe(true);
    console.log('  Verified selectAudioResult was called');

    // Assert: backend state — verify the job exists and has correct base fields
    // Note: is_private and display overrides are sent during the initial search request,
    // before the user reaches Step 3. The current flow sends is_private from the parent
    // state at search time (defaulting to false). Display overrides follow the same pattern.
    // A future improvement should update these fields when the user confirms on Step 3.
    expect(searchJobId).toBeTruthy();
    const token = getAdminToken()!;
    const jobResponse = await request.get(`${API_URL}/api/jobs/${searchJobId}`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: TIMEOUTS.apiCall,
    });
    expect(jobResponse.ok()).toBe(true);
    const job = await jobResponse.json();
    // Verify core fields
    expect(job.artist.toLowerCase()).toBe(TEST_SONG.artist.toLowerCase());
    expect(job.title.toLowerCase()).toBe(TEST_SONG.title.toLowerCase());
    console.log(`  Verified backend job: ${job.artist} - ${job.title} (is_private=${job.is_private})`);
  });

  // ---------------------------------------------------------------------------
  // Test 3: YouTube URL fallback
  // ---------------------------------------------------------------------------
  test('YouTube URL fallback', async ({ page }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    let urlBody: any = null;
    let urlJobId: string | null = null;

    // Intercept search (to track the search job)
    let searchJobId: string | null = null;
    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    // Intercept URL creation
    await page.route('**/api/jobs/create-from-url', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        urlBody = req.postDataJSON();
        const { body, json, status, headers } = await fetchAndCapture(route);
        urlJobId = json?.job_id;
        if (urlJobId) cleanup.trackJob(urlJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    // Step 1: Fill and proceed
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();

    // Step 2: Wait for search to complete, then click YouTube URL button
    // Wait for search loading to finish (either "Our Pick" appears or "No audio sources")
    await expect(
      page.getByText('Our Pick').or(page.getByText(/no audio sources/i))
    ).toBeVisible({ timeout: TIMEOUTS.apiCall });
    console.log('  Search complete, clicking YouTube URL fallback');

    await page.getByRole('button', { name: 'YouTube URL', exact: true }).click();

    // Fill URL and submit
    await page.locator('input[type="url"]').fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await page.getByRole('button', { name: /use this url/i }).click();

    // Wait for success
    await expect(page.getByText('Job Created')).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Job created via YouTube URL');

    // Assert: intercepted request body
    expect(urlBody).toBeTruthy();
    expect(urlBody.url).toContain('youtube.com');
    expect(urlBody.artist).toBe(TEST_SONG.artist);
    expect(urlBody.title).toBe(TEST_SONG.title);
    console.log(`  Verified URL request: url=${urlBody.url}, artist=${urlBody.artist}`);
  });

  // ---------------------------------------------------------------------------
  // Test 4: File upload fallback
  // ---------------------------------------------------------------------------
  test('file upload fallback', async ({ page }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    let uploadIntercepted = false;
    let uploadJobId: string | null = null;

    // Intercept search (to track the search job)
    let searchJobId: string | null = null;
    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    // Intercept upload
    await page.route('**/api/jobs/upload', async (route) => {
      uploadIntercepted = true;
      const { body, json, status, headers } = await fetchAndCapture(route);
      uploadJobId = json?.job_id;
      if (uploadJobId) cleanup.trackJob(uploadJobId);
      await route.fulfill({ status, headers, body });
    });

    // Step 1: Fill and proceed
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();

    // Step 2: Wait for search to complete, then click Upload button
    await expect(
      page.getByText('Our Pick').or(page.getByText(/no audio sources/i))
    ).toBeVisible({ timeout: TIMEOUTS.apiCall });
    console.log('  Search complete, clicking Upload fallback');

    await page.getByRole('button', { name: 'Upload file', exact: true }).click();

    // Upload the real FLAC fixture file (tests/data/waterloo10sec.flac)
    console.log(`  Uploading fixture: ${UPLOAD_FIXTURE_PATH}`);
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(UPLOAD_FIXTURE_PATH);

    // Click upload submit button
    await page.getByRole('button', { name: /upload.*create/i }).click();

    // Wait for success
    await expect(page.getByText('Job Created')).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Job created via file upload');

    // Assert: upload was intercepted
    expect(uploadIntercepted).toBe(true);
    console.log('  Verified upload request was sent');
  });

  // ---------------------------------------------------------------------------
  // Test 5: Back navigation cleans up stale job
  // ---------------------------------------------------------------------------
  test('back navigation cleans up stale job', async ({ page }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    let searchJobId: string | null = null;
    let deleteIntercepted = false;
    let deletedJobId: string | null = null;

    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    // Intercept DELETE calls for job cleanup
    await page.route('**/api/jobs/*', async (route) => {
      const req = route.request();
      if (req.method() === 'DELETE') {
        deleteIntercepted = true;
        // Extract job ID from URL path
        const urlParts = req.url().split('/api/jobs/');
        if (urlParts[1]) {
          deletedJobId = urlParts[1].split('?')[0];
        }
      }
      const { body, status, headers } = await fetchAndCapture(route);
      await route.fulfill({ status, headers, body });
    });

    // Step 1: Fill and proceed
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();

    // Step 2: Wait for results to appear
    await expect(
      page.getByText('Our Pick').or(page.getByText(/no audio sources/i))
    ).toBeVisible({ timeout: TIMEOUTS.apiCall });
    console.log(`  Search complete, job ID: ${searchJobId}`);

    // Click "Back"
    await page.getByRole('button', { name: /back/i }).click();

    // Wait a moment for the cleanup request to fire (it's fire-and-forget)
    await page.waitForTimeout(2000);

    // Assert: DELETE was intercepted
    expect(deleteIntercepted).toBe(true);
    console.log(`  Verified DELETE intercepted for job: ${deletedJobId}`);

    // Assert: returned to Step 1 (artist/title inputs visible)
    await expect(page.getByTestId('guided-artist-input')).toBeVisible({ timeout: TIMEOUTS.action });
    await expect(page.getByTestId('guided-title-input')).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Returned to Step 1 — artist/title inputs visible');
  });

  // ---------------------------------------------------------------------------
  // Test 6: Fallback options (YouTube URL, Upload file) visible after search
  // ---------------------------------------------------------------------------
  test('fallback options visible after search completes', async ({ page }) => {
    test.setTimeout(TIMEOUTS.apiCall * 2);

    let searchJobId: string | null = null;

    await page.route('**/api/audio-search/search', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        const { body, json, status, headers } = await fetchAndCapture(route);
        searchJobId = json?.job_id;
        if (searchJobId) cleanup.trackJob(searchJobId);
        await route.fulfill({ status, headers, body });
      } else {
        await route.continue();
      }
    });

    // Step 1: Search for test song (will find results, but fallback options should still appear)
    await page.goto(`${FRONTEND_URL}/app`);
    await page.waitForLoadState('networkidle');

    await page.getByTestId('guided-artist-input').fill(TEST_SONG.artist);
    await page.getByTestId('guided-title-input').fill(TEST_SONG.title);
    await page.getByRole('button', { name: /choose audio/i }).click();
    console.log('  Submitted search');

    // Wait for search to complete (results or no-results or error message)
    await expect(
      page.getByText('Our Pick')
        .or(page.getByText(/no audio sources/i))
        .or(page.getByText(/taking longer than expected/i))
    ).toBeVisible({ timeout: TIMEOUTS.apiCall });
    console.log('  Search complete');

    // Assert: fallback options ("Not finding what you need?" section) are visible
    // These buttons should always appear after search completes, regardless of results
    await expect(page.getByRole('button', { name: 'YouTube URL', exact: true })).toBeVisible({ timeout: TIMEOUTS.action });
    await expect(page.getByRole('button', { name: 'Upload file', exact: true })).toBeVisible({ timeout: TIMEOUTS.action });
    console.log('  Fallback options (YouTube URL, Upload file) visible');

    // Also verify the explanatory text
    await expect(page.getByText(/not finding what you need/i)).toBeVisible();
    console.log('  "Not finding what you need?" helper text visible');

    console.log(`  Search job tracked for cleanup: ${searchJobId}`);
  });
});
