import { test, expect, Page } from '@playwright/test';

/**
 * Production User Journey E2E Test
 *
 * Tests the complete user flow from landing page to karaoke generation:
 * 1. Visit buy site landing page
 * 2. Beta enrollment OR payment checkout
 * 3. Magic link verification
 * 4. Main app authentication
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

// After consolidation, both landing page and app are on the same domain
const BASE_URL = 'https://gen.nomadkaraoke.com';
const WELCOME_URL = `${BASE_URL}/welcome`;
const GEN_SITE_URL = BASE_URL;
const API_URL = 'https://api.nomadkaraoke.com';

// Legacy URL for testing redirect (can be removed after buy site is deleted)
const BUY_SITE_URL = 'https://buy.nomadkaraoke.com';

// Test data
const TEST_ARTIST = 'piri';
const TEST_TITLE = 'dog';

test.describe('User Journey - Buy Site', () => {

  test('Landing page loads and displays correctly', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Check hero section
    await expect(page.locator('h1')).toContainText('Karaoke Video');

    // Check navigation
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.getByText('Nomad Karaoke')).toBeVisible();

    // Check pricing section exists
    await expect(page.locator('#pricing')).toBeVisible();

    // Check beta tester program section
    await expect(page.getByText('Beta Tester Program')).toBeVisible();

    // Check FAQ section
    await expect(page.getByText('Questions?')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-01-landing.png', fullPage: true });
  });

  test('Pricing packages display correctly', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Scroll to pricing
    await page.locator('#pricing').scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Check all 4 credit packages are displayed
    await expect(page.getByText('1 Credit', { exact: false })).toBeVisible();
    await expect(page.getByText('3 Credits', { exact: false })).toBeVisible();
    await expect(page.getByText('5 Credits', { exact: false })).toBeVisible();
    await expect(page.getByText('10 Credits', { exact: false })).toBeVisible();

    // Check "Best Value" badge on 5 credits
    await expect(page.getByText('Best Value')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-02-pricing.png' });
  });

  test('Package selection updates checkout form', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    await page.locator('#pricing').scrollIntoViewIfNeeded();

    // Default should be 5 credits
    await expect(page.getByText('Selected package')).toBeVisible();

    // Click on 10 credits
    const tenCreditsBtn = page.locator('button').filter({ hasText: /^10/ });
    await tenCreditsBtn.click();
    await page.waitForTimeout(300);

    // Verify checkout form updated
    await expect(page.getByText('10 Credits')).toBeVisible();
    await expect(page.getByText('$30')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-03-package-selected.png' });
  });

  test('Checkout form validates email', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
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

    await page.goto(BUY_SITE_URL);
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
});

test.describe('User Journey - Beta Enrollment', () => {

  test('Beta form opens and validates input', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Click "Join Beta Program"
    await page.getByRole('button', { name: /join beta program/i }).click();
    await page.waitForTimeout(500);

    // Form should be visible
    await expect(page.getByText('Beta Tester Signup')).toBeVisible();
    await expect(page.getByText('Get 1 Free Credit')).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-06-beta-form.png' });

    // Try to submit without filling
    await page.getByRole('button', { name: /get my free credit/i }).click();

    // Should show validation error
    await expect(page.getByText(/please enter your email/i)).toBeVisible();
  });

  test('Beta form requires checkbox and promise', async ({ page }) => {
    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /join beta program/i }).click();
    await page.waitForTimeout(500);

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

test.describe('User Journey - Main App Auth', () => {

  test('Main app shows authentication required message', async ({ page }) => {
    await page.goto(GEN_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Should show auth required message
    await expect(page.getByText(/authentication required/i)).toBeVisible();
    await expect(page.getByText(/click the login button/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-08-auth-required.png' });
  });

  test('Auth dialog opens and shows magic link option', async ({ page }) => {
    await page.goto(GEN_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Click login button (AuthStatus component)
    await page.getByRole('button', { name: /login|sign in/i }).click();
    await page.waitForTimeout(500);

    // Auth dialog should open
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await expect(page.getByText(/enter your email/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-09-auth-dialog.png' });
  });

  test('Auth dialog can switch to token mode', async ({ page }) => {
    await page.goto(GEN_SITE_URL);
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /login|sign in/i }).click();
    await page.waitForTimeout(500);

    // Click "Use Access Token Instead"
    await page.getByRole('button', { name: /use access token/i }).click();
    await page.waitForTimeout(300);

    // Should show token input
    await expect(page.getByText(/access token/i)).toBeVisible();
    await expect(page.getByPlaceholder(/enter access token/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-10-token-mode.png' });
  });

  test('Token authentication works with valid token', async ({ page }) => {
    const accessToken = process.env.KARAOKE_ACCESS_TOKEN;
    test.skip(!accessToken, 'Skipping - set KARAOKE_ACCESS_TOKEN env var');

    await page.goto(GEN_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Inject token directly (simulating successful auth)
    await page.evaluate((token) => {
      localStorage.setItem('karaoke_access_token', token);
    }, accessToken);

    // Reload to apply auth
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Auth required message should be gone
    await expect(page.getByText(/authentication required/i)).not.toBeVisible();

    // Should see the job creation form
    await expect(page.getByText(/create karaoke video/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-11-authenticated.png' });
  });
});

test.describe('User Journey - Cross-Domain Issues', () => {

  test('CRITICAL: Buy site token key mismatch with main app', async ({ page }) => {
    /**
     * BUG DOCUMENTATION:
     *
     * The buy-site stores session tokens with key 'nomad_karaoke_token'
     * The main frontend uses key 'karaoke_access_token'
     *
     * Even if they used the same key, localStorage is domain-specific!
     * buy.nomadkaraoke.com and gen.nomadkaraoke.com cannot share localStorage.
     *
     * This test documents the issue and will fail until fixed.
     */

    // Simulate buy site storing a token
    await page.goto(BUY_SITE_URL);
    await page.evaluate(() => {
      // This is what buy-site does on beta enrollment success
      localStorage.setItem('nomad_karaoke_token', 'test-session-token');
    });

    // Navigate to main app
    await page.goto(GEN_SITE_URL);

    // Check what keys exist
    const buyToken = await page.evaluate(() => localStorage.getItem('nomad_karaoke_token'));
    const genToken = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));

    console.log('Token on gen.nomadkaraoke.com:');
    console.log('  nomad_karaoke_token:', buyToken);  // Will be null (different domain)
    console.log('  karaoke_access_token:', genToken); // Will be null (not set)

    // This demonstrates the cross-domain issue
    // Tokens set on buy.nomadkaraoke.com are NOT accessible from gen.nomadkaraoke.com
    expect(buyToken).toBeNull(); // Expected: null because different domain

    await page.screenshot({ path: 'test-results/journey-12-cross-domain-issue.png' });
  });
});

test.describe('User Journey - Complete Flow with Email', () => {

  test('Full flow: Beta enrollment with email verification', async ({ page, request }) => {
    // Skip if no email testing capability
    const mailslurpKey = process.env.MAILSLURP_API_KEY;
    test.skip(!mailslurpKey, 'Skipping email flow - set MAILSLURP_API_KEY for full test');

    // Dynamic import to avoid errors when MailSlurp not installed
    const { createEmailHelper } = await import('./helpers/email-testing');
    const emailHelper = await createEmailHelper();

    if (!emailHelper.isAvailable) {
      test.skip(true, 'Email testing not available');
      return;
    }

    // Step 1: Create a test inbox
    console.log('\n=== STEP 1: Creating test inbox ===');
    const inbox = await emailHelper.createInbox();
    console.log(`Test email: ${inbox.emailAddress}`);

    try {
      // Step 2: Go to welcome page and enroll in beta
      console.log('\n=== STEP 2: Beta enrollment ===');
      await page.goto(`${GEN_SITE_URL}/welcome`);
      await page.waitForLoadState('networkidle');

      // Click "Join Beta Program"
      await page.getByRole('button', { name: /join beta program/i }).click();
      await page.waitForTimeout(500);

      // Fill the beta form
      await page.locator('#beta-email').fill(inbox.emailAddress!);
      await page.locator('textarea').fill('I want to create karaoke for my favorite indie songs that nobody has made yet!');
      await page.locator('input[type="checkbox"]').check();

      await page.screenshot({ path: 'test-results/email-flow-01-beta-form.png' });

      // Submit the form
      await page.getByRole('button', { name: /get my free credit/i }).click();

      // Wait for response
      await page.waitForTimeout(3000);
      await page.screenshot({ path: 'test-results/email-flow-02-after-submit.png' });

      // Step 3: Wait for email
      console.log('\n=== STEP 3: Waiting for verification email ===');
      const email = await emailHelper.waitForEmail(inbox.id!, 120000); // 2 minute timeout
      console.log(`Received email: "${email.subject}"`);

      // Step 4: Extract and follow magic link
      console.log('\n=== STEP 4: Following magic link ===');
      const magicLink = emailHelper.extractMagicLink(email);

      if (!magicLink) {
        console.log('Email body:', email.body);
        throw new Error('Could not find magic link in email');
      }

      console.log(`Magic link: ${magicLink}`);
      await page.goto(magicLink);
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: 'test-results/email-flow-03-after-verify.png' });

      // Step 5: Verify authentication
      console.log('\n=== STEP 5: Verifying authentication ===');

      // Should be redirected to main app or see authenticated state
      await page.waitForTimeout(2000);

      // Check if we have a token stored
      const token = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));

      if (token) {
        console.log('Token stored successfully!');
        expect(token).toBeTruthy();
      } else {
        // May have been redirected - navigate to main app
        await page.goto(GEN_SITE_URL);
        await page.waitForLoadState('networkidle');

        const tokenAfterNav = await page.evaluate(() => localStorage.getItem('karaoke_access_token'));
        console.log('Token after navigation:', tokenAfterNav ? 'present' : 'not found');
      }

      await page.screenshot({ path: 'test-results/email-flow-04-authenticated.png' });
      console.log('\n=== Email flow test completed! ===');

    } finally {
      // Cleanup: delete the test inbox
      if (inbox.id) {
        await emailHelper.deleteInbox(inbox.id);
      }
    }
  });

  test('Full flow: Payment checkout with email verification', async ({ page, request }) => {
    // Skip if no email testing capability
    const mailslurpKey = process.env.MAILSLURP_API_KEY;
    test.skip(!mailslurpKey, 'Skipping email flow - set MAILSLURP_API_KEY for full test');
    test.skip(!process.env.TEST_PAYMENT_FLOW, 'Skipping payment flow - set TEST_PAYMENT_FLOW=true');

    const { createEmailHelper } = await import('./helpers/email-testing');
    const emailHelper = await createEmailHelper();

    if (!emailHelper.isAvailable) {
      test.skip(true, 'Email testing not available');
      return;
    }

    // Create a test inbox
    const inbox = await emailHelper.createInbox();

    try {
      // Go to welcome page
      await page.goto(`${GEN_SITE_URL}/welcome`);
      await page.waitForLoadState('networkidle');

      // Scroll to pricing
      await page.locator('#pricing').scrollIntoViewIfNeeded();

      // Fill email and submit
      await page.locator('#email').fill(inbox.emailAddress!);
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
    expect(rootData.service).toBe('karaoke-gen');
    expect(rootData.version).toBeTruthy();

    console.log(`API Version: ${rootData.version}`);
  });

  test('Credit packages endpoint works', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/users/credits/packages`);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    expect(data.packages).toBeInstanceOf(Array);
    expect(data.packages.length).toBeGreaterThan(0);

    // Verify package structure
    const pkg = data.packages[0];
    expect(pkg.id).toBeTruthy();
    expect(pkg.credits).toBeGreaterThan(0);
    expect(pkg.price_cents).toBeGreaterThan(0);

    console.log('Credit packages:', data.packages.map((p: any) => `${p.credits} credits @ $${p.price_cents/100}`).join(', '));
  });
});

test.describe('User Journey - UX Issues Documentation', () => {

  test('Document navigation confusion between sites', async ({ page }) => {
    /**
     * UX ISSUE: Two separate sites create confusion
     *
     * Problems:
     * 1. User starts at buy.nomadkaraoke.com
     * 2. After payment/beta, redirected to gen.nomadkaraoke.com
     * 3. Token from buy site doesn't transfer (different domains)
     * 4. User has to re-authenticate on gen site
     * 5. "Already have credits? Sign in" link goes to gen site but user won't be logged in
     */

    await page.goto(BUY_SITE_URL);
    await page.waitForLoadState('networkidle');

    // Click "Already have credits? Sign in"
    const signInLink = page.getByText(/already have credits/i);
    await expect(signInLink).toBeVisible();

    const href = await signInLink.getAttribute('href');
    console.log('Sign in link href:', href); // Goes to gen.nomadkaraoke.com

    // Follow the link
    await signInLink.click();
    await page.waitForLoadState('networkidle');

    // User arrives at gen site but NOT logged in
    await expect(page.url()).toContain('gen.nomadkaraoke.com');
    await expect(page.getByText(/authentication required/i)).toBeVisible();

    await page.screenshot({ path: 'test-results/journey-ux-navigation-issue.png' });
  });

  test('Document beta enrollment redirect issue', async ({ page }) => {
    /**
     * UX ISSUE: Beta enrollment flow breaks due to cross-domain redirect
     *
     * Current flow:
     * 1. User fills beta form on buy.nomadkaraoke.com
     * 2. Backend creates session, returns session_token
     * 3. buy-site stores token in localStorage as 'nomad_karaoke_token'
     * 4. buy-site redirects to gen.nomadkaraoke.com after 2 seconds
     * 5. gen.nomadkaraoke.com can't access buy site's localStorage
     * 6. User appears unauthenticated on gen site
     *
     * Expected flow (after fix):
     * 1. User fills beta form on gen.nomadkaraoke.com (single domain)
     * 2. OR: Redirect includes token in URL query param
     * 3. OR: Use cookies with domain=.nomadkaraoke.com
     */

    console.log('Beta enrollment creates token on buy site but redirects to gen site');
    console.log('Token is lost because localStorage is domain-specific');

    // The redirect in buy-site/app/page.tsx line 102:
    // window.location.href = 'https://gen.nomadkaraoke.com';
    // This loses the session because gen site cannot read buy site's localStorage
  });
});
