/**
 * Email Testing Utilities using MailSlurp
 *
 * MailSlurp provides disposable email inboxes for e2e testing.
 * Free tier: 50 emails/month - perfect for CI/CD testing.
 *
 * Setup:
 * 1. Create account at https://app.mailslurp.com
 * 2. Get API key from dashboard
 * 3. Set MAILSLURP_API_KEY environment variable
 *
 * Usage in tests:
 *   const emailHelper = await createEmailHelper();
 *   const inbox = await emailHelper.createInbox();
 *   // ... trigger email send to inbox.emailAddress ...
 *   const email = await emailHelper.waitForEmail(inbox.id);
 *   const magicLink = emailHelper.extractMagicLink(email);
 */

import { MailSlurp, InboxDto, Email } from 'mailslurp-client';

const MAILSLURP_API_KEY = process.env.MAILSLURP_API_KEY;

export interface EmailHelper {
  isAvailable: boolean;
  createInbox: () => Promise<InboxDto>;
  waitForEmail: (inboxId: string, timeout?: number) => Promise<Email>;
  extractMagicLink: (email: Email) => string | null;
  extractVerificationCode: (email: Email) => string | null;
  deleteInbox: (inboxId: string) => Promise<void>;
}

/**
 * Creates an email testing helper.
 * Returns a helper with isAvailable=false if MAILSLURP_API_KEY is not set.
 */
export async function createEmailHelper(): Promise<EmailHelper> {
  if (!MAILSLURP_API_KEY) {
    console.warn('MAILSLURP_API_KEY not set - email testing disabled');
    return createDisabledHelper();
  }

  const mailslurp = new MailSlurp({ apiKey: MAILSLURP_API_KEY });

  return {
    isAvailable: true,

    /**
     * Create a new disposable inbox for testing
     */
    async createInbox(): Promise<InboxDto> {
      const inbox = await mailslurp.createInbox();
      console.log(`Created test inbox: ${inbox.emailAddress}`);
      return inbox;
    },

    /**
     * Wait for an email to arrive in the inbox
     * @param inboxId - The inbox ID to check
     * @param timeout - Timeout in ms (default: 60000 = 1 minute)
     */
    async waitForEmail(inboxId: string, timeout = 60000): Promise<Email> {
      console.log(`Waiting for email in inbox ${inboxId}...`);
      const email = await mailslurp.waitForLatestEmail(inboxId, timeout);
      console.log(`Received email: ${email.subject}`);
      return email;
    },

    /**
     * Extract magic link URL from email body
     */
    extractMagicLink(email: Email): string | null {
      const body = email.body || '';

      // Debug: Log email structure
      console.log('Email subject:', email.subject);
      console.log('Email body length:', body.length);
      console.log('Email body preview (first 500 chars):', body.substring(0, 500));

      // Look for common magic link patterns
      const patterns = [
        // gen.nomadkaraoke.com verify link
        /https:\/\/gen\.nomadkaraoke\.com\/auth\/verify\?token=[a-zA-Z0-9_-]+/,
        // api.nomadkaraoke.com verify link
        /https:\/\/api\.nomadkaraoke\.com\/api\/users\/auth\/verify\?token=[a-zA-Z0-9_-]+/,
        // Generic magic link patterns - allow URL-encoded characters
        /https?:\/\/[^\s<>"]+\/auth\/verify[^\s<>"]*/,
        /https?:\/\/[^\s<>"]+verify\?token=[a-zA-Z0-9_%-]+/,
        /https?:\/\/[^\s<>"]+token=[a-zA-Z0-9_%-]+/,
      ];

      for (const pattern of patterns) {
        const match = body.match(pattern);
        if (match) {
          console.log(`Found magic link with pattern ${pattern}: ${match[0]}`);
          return match[0];
        }
      }

      // Also check HTML links
      if (email.body) {
        const htmlLinkPattern = /href=["']([^"']*(?:verify|token)[^"']*)["']/i;
        const htmlMatch = email.body.match(htmlLinkPattern);
        if (htmlMatch) {
          console.log(`Found magic link in HTML href: ${htmlMatch[1]}`);
          return htmlMatch[1];
        }
      }

      // Debug: Log all URLs found in the email
      const allUrls = body.match(/https?:\/\/[^\s<>"]+/g) || [];
      console.log('All URLs found in email:', allUrls);

      console.warn('No magic link found in email');
      return null;
    },

    /**
     * Extract verification code from email body
     */
    extractVerificationCode(email: Email): string | null {
      const body = email.body || '';

      // Look for 6-digit codes
      const codePattern = /\b(\d{6})\b/;
      const match = body.match(codePattern);

      if (match) {
        console.log(`Found verification code: ${match[1]}`);
        return match[1];
      }

      console.warn('No verification code found in email');
      return null;
    },

    /**
     * Delete an inbox after testing
     */
    async deleteInbox(inboxId: string): Promise<void> {
      await mailslurp.deleteInbox(inboxId);
      console.log(`Deleted inbox ${inboxId}`);
    },
  };
}

/**
 * Creates a disabled helper for when MailSlurp is not configured
 */
function createDisabledHelper(): EmailHelper {
  const notAvailable = () => {
    throw new Error('Email testing not available - set MAILSLURP_API_KEY');
  };

  return {
    isAvailable: false,
    createInbox: notAvailable,
    waitForEmail: notAvailable,
    extractMagicLink: () => null,
    extractVerificationCode: () => null,
    deleteInbox: notAvailable,
  };
}

/**
 * Check if email testing is available
 */
export function isEmailTestingAvailable(): boolean {
  return !!MAILSLURP_API_KEY;
}
