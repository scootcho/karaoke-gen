/**
 * API client for the Nomad Karaoke backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.nomadkaraoke.com';

export interface CreditPackage {
  id: string;
  credits: number;
  price_cents: number;
  name: string;
  description: string;
}

export interface CreditPackagesResponse {
  packages: CreditPackage[];
}

export interface CheckoutResponse {
  status: string;
  checkout_url: string;
  message: string;
}

/**
 * Fetch available credit packages.
 */
export async function getCreditPackages(): Promise<CreditPackage[]> {
  const response = await fetch(`${API_BASE_URL}/api/users/credits/packages`);

  if (!response.ok) {
    throw new Error('Failed to fetch credit packages');
  }

  const data: CreditPackagesResponse = await response.json();
  return data.packages;
}

/**
 * Create a Stripe checkout session.
 */
export async function createCheckout(packageId: string, email: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/users/credits/checkout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      package_id: packageId,
      email: email,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create checkout session');
  }

  const data: CheckoutResponse = await response.json();
  return data.checkout_url;
}

/**
 * Format price from cents to display string.
 */
export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/**
 * Calculate per-credit price.
 */
export function pricePerCredit(pkg: CreditPackage): number {
  return pkg.price_cents / pkg.credits;
}

// ============================================================================
// Beta Tester Program
// ============================================================================

export interface BetaEnrollRequest {
  email: string;
  promise_text: string;
  accept_corrections_work: boolean;
}

export interface BetaEnrollResponse {
  status: string;
  message: string;
  credits_granted: number;
  session_token: string | null;
}

/**
 * Enroll as a beta tester to receive free credits.
 */
export async function enrollBetaTester(
  email: string,
  promiseText: string,
  acceptCorrectionsWork: boolean
): Promise<BetaEnrollResponse> {
  const response = await fetch(`${API_BASE_URL}/api/users/beta/enroll`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      email: email,
      promise_text: promiseText,
      accept_corrections_work: acceptCorrectionsWork,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to enroll in beta program');
  }

  return response.json();
}
