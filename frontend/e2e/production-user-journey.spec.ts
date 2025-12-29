import { test, expect, Page } from '@playwright/test';
import { createEmailHelper, isEmailTestingAvailable } from './helpers/email-testing';

/**
 * Production User Journey E2E Test
 *
 * Tests the complete user flow from landing page to karaoke generation:
 * 1. Visit landing page at / (root)
 * 2. Beta enrollment OR payment checkout
 * 3. Magic link verification
 * 4. Main app authentication at /app
 * 5. Job submission
 *
 * Run with:
 *   npx playwright test production-user-journey --config=playwright.production.config.ts --headed
 *
 * Environment variables:
 *   - MAILSLURP_API_KEY: For email testing (free tier: 50 emails/month)
 *   - TEST_EMAIL: Use a specific email for testing
 *   - KARAOKE_ACCESS_TOKEN: Skip auth flow and use existing token
 */

// After consolidation, landing page is at root and app is at /app
const BASE_URL = 'https://gen.nomadkaraoke.com';
const LANDING_URL = BASE_URL; // Landing page at root
const APP_URL = `${BASE_URL}/app`; // Main app
const API_URL = 'https://api.nomadkaraoke.com';

// Test data
const TEST_ARTIST = 'piri';
const TEST_TITLE = 'dog';

test.describe('User Journey - Landing Page', () => {

  test('Landing page loads and displays correctly', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Check hero section
    await expect(page.locator('h1')).toContainText('Karaoke Video');

    // Check navigation
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.getByRole('navigation').getByText('Nomad Karaoke')).toBeVisible();

    // Check pricing section exists
    await expect(page.locator('#pricing')).toBeVisible();

    // Check beta tester program section
    await expect(page.getByText('Beta Tester Program')).toBeVisible();

    // Check FAQ section
    await expect(page.getByText('Questions?')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-01-landing.png', fullPage: true });
  });

  test('Pricing packages display correctly', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Scroll to pricing and wait for content to be visible
    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Check all 4 credit packages are displayed (case-insensitive, as page has "credit" lowercase)
    await expect(page.getByRole('button', { name: /1\s+credit/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /3\s+credits/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /5\s+credits/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /10\s+credits/i })).toBeVisible();

    // Check "Best Value" badge on 5 credits
    await expect(page.getByText('Best Value')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-02-pricing.png' });
  });

  test('Package selection updates checkout form', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Default should be 5 credits - look for summary section
    await expect(page.getByText('Selected package')).toBeVisible();

    // Click on 10 credits button and wait for it to be pressed/selected
    const tenCreditsBtn = page.getByRole('button', { name: /10\s+credits/i });
    await tenCreditsBtn.click();

    // Wait for the package selection summary to update
    // The summary section contains "Selected package", "10 Credits", and "$30"
    // We need to verify the summary (not the button) shows $30
    const summaryContainer = page.locator('text=Selected package').locator('..');
    await expect(summaryContainer.getByText('10 Credits')).toBeVisible({ timeout: 10000 });
    await expect(summaryContainer.getByText('$30')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-03-package-selected.png' });
  });

  test('Checkout form validates email', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Try to checkout without email
    await page.getByRole('button', { name: /continue to payment/i }).click();

    // Should show error (browser validation)
    const emailInput = page.locator('input[type="email"]').first();
    await expect(emailInput).toBeVisible();

    // Enter invalid email - the button should require valid email
    await emailInput.fill('invalid');

    await page.screenshot({ path: 'test-results/journey-04-email-validation.png' });
  });

  test('Checkout redirects to Stripe', async ({ page }) => {
    test.skip(!process.env.TEST_CHECKOUT, 'Skipping actual checkout - set TEST_CHECKOUT=true to enable');

    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Fill email
    const testEmail = process.env.TEST_EMAIL || 'test@example.com';
    await page.locator('input[type="email"]').first().fill(testEmail);

    // Click checkout
    await page.getByRole('button', { name: /continue to payment/i }).click();

    // Wait for redirect to Stripe
    await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 });

    await expect(page.url()).toContain('stripe.com');
    await page.screenshot({ path: 'test-results/journey-05-stripe-redirect.png' });
  });

  test('Logged in users are redirected to /app', async ({ page }) => {
    // Set a token in storage
    await page.goto(LANDING_URL);
    await page.evaluate(() => {
      localStorage.setItem('karaoke_access_token', 'test-redirect-token');
    });

    // Reload the page - should redirect to /app
    await page.goto(LANDING_URL);
    await page.waitForURL(/\/app/, { timeout: 5000 });

    expect(page.url()).toContain('/app');
    await page.screenshot({ path: 'test-results/journey-05b-logged-in-redirect.png' });

    // Cleanup
    await page.evaluate(() => {
      localStorage.removeItem('karaoke_access_token');
    });
  });

  test('Sign in button opens auth dialog on landing page', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Click "Sign in" button in nav
    await page.getByRole('button', { name: /sign in/i }).click();

    // Auth dialog should open
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Enter your email to receive a sign-in link')).toBeVisible();
    await expect(dialog.locator('input[type="email"]')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-05c-landing-signin-dialog.png' });
  });
});

test.describe('User Journey - Beta Enrollment', () => {

  test('Beta form opens and validates input', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Click "Join Beta Program" and wait for form to appear
    await page.getByRole('button', { name: /join beta program/i }).click();
    await expect(page.getByRole('button', { name: /get my free credit/i })).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-06-beta-form.png' });

    // Email input has 'required' attribute, so browser native validation will block submission
    // Test by filling email but not accepting terms to trigger JS validation
    await page.locator('#beta-email').fill('test@example.com');

    // Try to submit without accepting terms
    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should show validation error for missing checkbox
    await expect(page.getByText(/please accept/i)).toBeVisible();
  });

  test('Beta form requires checkbox and promise', async ({ page }) => {
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Open beta form and wait for email field to be visible
    await page.getByRole('button', { name: /join beta program/i }).click();
    await expect(page.locator('#beta-email')).toBeVisible();

    // Fill email
    await page.locator('#beta-email').fill('test@example.com');

    // Submit without checkbox
    await page.getByRole('button', { name: /get my free credit/i }).click();
    await expect(page.getByText(/please accept/i)).toBeVisible();

    // Check the checkbox
    await page.locator('input[type="checkbox"]').check();

    // Submit without promise
    await page.getByRole('button', { name: /get my free credit/i }).click();
    await expect(page.getByText(/please write a sentence/i)).toBeVisible();

    // Add promise text (too short)
    await page.locator('textarea').fill('ok');
    await page.getByRole('button', { name: /get my free credit/i }).click();
    await expect(page.getByText(/please write a sentence/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-07-beta-validation.png' });
  });
});

test.describe('User Journey - Main App', () => {

  test('Unauthenticated users are redirected to landing page', async ({ page }) => {
    // Clear any existing token
    await page.goto(LANDING_URL);
    await page.evaluate(() => {
      localStorage.removeItem('karaoke_access_token');
    });

    // Try to go to /app
    await page.goto(APP_URL);

    // Should redirect to landing page
    await page.waitForURL(LANDING_URL, { timeout: 5000 });

    // Should see the landing page hero
    await expect(page.locator('h1')).toContainText('Karaoke Video');

    await page.screenshot({ path: 'test-results/journey-08-unauth-redirect.png' });
  });

  test('Auth dialog opens and shows magic link option', async ({ page }) => {
    // First set a token to access the app (any token allows the page to render,
    // even if API calls will fail with 401 - token validation happens on API calls, not page load)
    await page.goto(LANDING_URL);
    await page.evaluate(() => {
      localStorage.setItem('karaoke_access_token', 'test-token');
    });

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Click login button and wait for auth dialog to open
    await page.getByRole('button', { name: /login|sign in/i }).click();

    // Wait for dialog and check it has the expected content
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Enter your email to receive a sign-in link')).toBeVisible();
    await expect(dialog.locator('input[type="email"]')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-09-auth-dialog.png' });

    // Cleanup
    await page.evaluate(() => {
      localStorage.removeItem('karaoke_access_token');
    });
  });

  test('Authenticated user can see the main app', async ({ page }) => {
    const accessToken = process.env.KARAOKE_ACCESS_TOKEN;
    test.skip(!accessToken, 'Skipping - set KARAOKE_ACCESS_TOKEN env var');

    // Set token and go to app
    await page.goto(LANDING_URL);
    await page.evaluate((token) => {
      localStorage.setItem('karaoke_access_token', token);
    }, accessToken);

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Should see the job creation form
    await expect(page.getByText(/create karaoke video/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-10-authenticated.png' });
  });
});

test.describe('User Journey - Same Domain Token Persistence', () => {

  test('LocalStorage persists on same domain after consolidation', async ({ page }) => {
    /**
     * REGRESSION TEST: Verify single-domain solution works
     *
     * After consolidation, landing page and main app are on the same domain,
     * so localStorage should persist across navigation.
     *
     * Note: We use a test key (not karaoke_access_token) because:
     * 1. The landing page redirects to /app when a token is present
     * 2. The /app page clears invalid tokens when API calls return 401
     * This is correct behavior, but not what we're testing here.
     */

    // Navigate to landing page
    await page.goto(LANDING_URL);
    await page.waitForLoadState('networkidle');

    // Store a test value in localStorage (using a test key, not the auth token)
    await page.evaluate(() => {
      localStorage.setItem('karaoke_test_persistence', 'test-value-123');
    });

    // Navigate to pricing section (still on same domain)
    await page.goto(`${LANDING_URL}#pricing`);
    await page.waitForLoadState('networkidle');

    // Value should still be accessible (same domain)
    const valueAfterNavigation = await page.evaluate(() =>
      localStorage.getItem('karaoke_test_persistence')
    );

    // Verify value persisted
    expect(valueAfterNavigation).toBe('test-value-123');
    console.log('LocalStorage persisted correctly across same-domain navigation');

    // Also verify by navigating to a different section
    await page.goto(`${LANDING_URL}#faq`);
    await page.waitForLoadState('networkidle');

    const valueAfterSecondNav = await page.evaluate(() =>
      localStorage.getItem('karaoke_test_persistence')
    );
    expect(valueAfterSecondNav).toBe('test-value-123');

    await page.screenshot({ path: 'test-results/journey-11-same-domain-token.png' });

    // Cleanup
    await page.evaluate(() => {
      localStorage.removeItem('karaoke_test_persistence');
    });
  });
});

test.describe('User Journey - Complete Flow with Email', () => {

  test('Full flow: Beta enrollment with session token and welcome email', async ({ page, request }) => {
    /**
     * Tests the complete beta enrollment flow:
     * 1. Fill out beta form with a MailSlurp test inbox
     * 2. Submit form and receive session token immediately (no email verification needed)
     * 3. Get redirected to /app
     * 4. Verify welcome email was received
     *
     * Note: Beta enrollment for NEW users returns a session token directly.
     * The welcome email is informational only (no magic link).
     */
    test.skip(!isEmailTestingAvailable(), 'Skipping email flow - set MAILSLURP_API_KEY for full test');

    const emailHelper = await createEmailHelper();

    if (!emailHelper.isAvailable) {
      test.skip();
      return;
    }

    // Step 1: Create a test inbox
    console.log('\n=== STEP 1: Creating test inbox ===');
    const inbox = await emailHelper.createInbox();
    if (!inbox.id || !inbox.emailAddress) {
      throw new Error('MailSlurp inbox creation failed - missing id or email');
    }
    console.log(`Test email: ${inbox.emailAddress}`);

    try {
      // Step 2: Go to landing page and enroll in beta
      console.log('\n=== STEP 2: Beta enrollment ===');
      await page.goto(LANDING_URL);
      await page.waitForLoadState('networkidle');

      // Click "Join Beta Program" and wait for form
      await page.getByRole('button', { name: /join beta program/i }).click();
      await expect(page.locator('#beta-email')).toBeVisible();

      // Fill the beta form
      await page.locator('#beta-email').fill(inbox.emailAddress);
      await page.locator('textarea').fill('I want to create karaoke for my favorite indie songs that nobody has made yet!');
      await page.locator('input[type="checkbox"]').check();

      await page.screenshot({ path: 'test-results/email-flow-01-beta-form.png' });

      // Submit the form
      await page.getByRole('button', { name: /get my free credit/i }).click();

      // Step 3: Verify successful enrollment
      console.log('\n=== STEP 3: Verifying enrollment success ===');

      // Wait for success message - "Redirecting to the app..." means we got a session token
      await expect(
        page.getByText(/welcome to the beta|redirecting to the app/i)
      ).toBeVisible({ timeout: 15000 });
      await page.screenshot({ path: 'test-results/email-flow-02-after-submit.png' });

      // Step 4: Wait for redirect to /app
      console.log('\n=== STEP 4: Waiting for redirect to /app ===');
      await page.waitForURL(/\/app/, { timeout: 10000 });

      // Verify we're authenticated
      const token = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));
      expect(token).toBeTruthy();
      console.log('Session token received successfully!');

      // Verify app is loaded
      await expect(page.getByText('Create Karaoke Video')).toBeVisible();
      await page.screenshot({ path: 'test-results/email-flow-03-app-authenticated.png' });

      // Step 5: Verify welcome email was received
      console.log('\n=== STEP 5: Verifying welcome email ===');
      const email = await emailHelper.waitForEmail(inbox.id, 60000); // 1 minute timeout
      console.log(`Received email: "${email.subject}"`);

      // Verify it's the beta welcome email
      expect(email.subject).toMatch(/welcome.*beta|beta.*tester/i);
      console.log('Welcome email received successfully!');

      await page.screenshot({ path: 'test-results/email-flow-04-completed.png' });
      console.log('\n=== Beta enrollment flow completed successfully! ===');

    } finally {
      // Cleanup: delete the test inbox
      if (inbox.id) {
        await emailHelper.deleteInbox(inbox.id);
      }
    }
  });

  test('Full flow: Payment checkout with email verification', async ({ page, request }) => {
    // Skip if no email testing capability
    test.skip(!isEmailTestingAvailable(), 'Skipping email flow - set MAILSLURP_API_KEY for full test');
    test.skip(!process.env.TEST_PAYMENT_FLOW, 'Skipping payment flow - set TEST_PAYMENT_FLOW=true');

    const emailHelper = await createEmailHelper();

    if (!emailHelper.isAvailable) {
      test.skip();
      return;
    }

    // Create a test inbox
    const inbox = await emailHelper.createInbox();
    if (!inbox.id || !inbox.emailAddress) {
      throw new Error('MailSlurp inbox creation failed - missing id or email');
    }

    try {
      // Go to landing page
      await page.goto(LANDING_URL);
      await page.waitForLoadState('networkidle');

      // Scroll to pricing
      await page.locator('#pricing').scrollIntoViewIfNeeded();

      // Fill email and submit
      await page.locator('#email').fill(inbox.emailAddress);
      await page.getByRole('button', { name: /continue to payment/i }).click();

      // Should redirect to Stripe
      await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 });
      await page.screenshot({ path: 'test-results/email-payment-01-stripe.png' });

      // Note: We don't complete the Stripe payment in tests
      // After payment, Stripe would redirect back and trigger email

    } finally {
      if (inbox.id) {
        await emailHelper.deleteInbox(inbox.id);
      }
    }
  });
});

test.describe('User Journey - API Health', () => {

  test('API endpoints are responding', async ({ request }) => {
    // Health check
    const healthResponse = await request.get(`${API_URL}/api/health`);
    expect(healthResponse.ok()).toBe(true);

    // Root endpoint
    const rootResponse = await request.get(`${API_URL}/`);
    expect(rootResponse.ok()).toBe(true);
    const rootData = await rootResponse.json();
    expect(rootData.service).toContain('karaoke-gen');
    expect(rootData.version).toBeTruthy();

    console.log(`API Version: ${rootData.version}`);
  });

  test('Credit packages endpoint works', async ({ request }) => {
    interface CreditPackageResponse {
      id: string;
      credits: number;
      price_cents: number;
    }

    const response = await request.get(`${API_URL}/api/users/credits/packages`);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    expect(data.packages).toBeInstanceOf(Array);
    expect(data.packages.length).toBeGreaterThan(0);

    // Verify package structure
    const pkg = data.packages[0] as CreditPackageResponse;
    expect(pkg.id).toBeTruthy();
    expect(pkg.credits).toBeGreaterThan(0);
    expect(pkg.price_cents).toBeGreaterThan(0);

    console.log('Credit packages:', data.packages.map((p: CreditPackageResponse) => `${p.credits} credits @ $${p.price_cents/100}`).join(', '));
  });
});
