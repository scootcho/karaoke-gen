'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  MicVocal,
  Music,
  Sparkles,
  Video,
  Youtube,
  ChevronDown,
  Check,
  Gift,
  MessageSquare,
  Mail,
  Loader2,
} from 'lucide-react';
import { api, setAccessToken, getAccessToken, CreditPackage, BetaEnrollResponse } from '@/lib/api';

// FAQ data
const faqs = [
  {
    question: 'How does it work?',
    answer:
      'Enter the artist and song title, and our AI finds the audio, removes the vocals, transcribes and syncs the lyrics, then generates a professional karaoke video. You can review and edit the lyrics before final export.',
  },
  {
    question: 'What songs can I use?',
    answer:
      'Any song! Our system searches multiple audio sources to find high-quality versions. If a song exists online, we can likely create a karaoke video for it.',
  },
  {
    question: 'What format is the output?',
    answer:
      'You get a 4K MP4 video file with perfectly synced lyrics. We also offer direct YouTube upload and cloud storage integration.',
  },
  {
    question: 'What if something goes wrong?',
    answer:
      "If the AI makes mistakes, you can edit the lyrics and timing before generating the final video. If there's a technical issue, contact us and we'll make it right.",
  },
  {
    question: 'Do credits expire?',
    answer:
      'No! Your credits never expire. Use them whenever you want.',
  },
];

export default function LandingPage() {
  const router = useRouter();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [packages, setPackages] = useState<CreditPackage[]>([]);
  const [packagesLoading, setPackagesLoading] = useState(true);
  const [packagesError, setPackagesError] = useState<string | null>(null);
  const [selectedPackage, setSelectedPackage] = useState<CreditPackage | null>(null);
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Beta form state
  const [showBetaForm, setShowBetaForm] = useState(false);
  const [betaEmail, setBetaEmail] = useState('');
  const [betaPromise, setBetaPromise] = useState('');
  const [betaAccept, setBetaAccept] = useState(false);
  const [betaLoading, setBetaLoading] = useState(false);
  const [betaError, setBetaError] = useState<string | null>(null);
  const [betaSuccess, setBetaSuccess] = useState(false);
  const [betaWillRedirect, setBetaWillRedirect] = useState(false);

  // FAQ expansion state
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  // Ref for redirect timeout cleanup
  const redirectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (redirectTimeoutRef.current) {
        clearTimeout(redirectTimeoutRef.current);
      }
    };
  }, []);

  // Check if already logged in and redirect to app
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      router.replace('/app');
      return;
    }
    setIsCheckingAuth(false);
  }, [router]);

  // Load credit packages on mount
  useEffect(() => {
    if (isCheckingAuth) return;

    async function loadPackages() {
      try {
        const pkgs = await api.getCreditPackages();
        setPackages(pkgs);
        // Default to 5 credits (best value)
        const bestValue = pkgs.find((p) => p.credits === 5);
        setSelectedPackage(bestValue || pkgs[0]);
      } catch (err) {
        console.error('Failed to load packages:', err);
        setPackagesError('Failed to load pricing. Please refresh the page.');
      } finally {
        setPackagesLoading(false);
      }
    }
    loadPackages();
  }, [isCheckingAuth]);

  // Handle checkout
  const handleCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPackage || !email) return;

    setIsLoading(true);
    setError(null);

    try {
      const checkoutUrl = await api.createCheckout(selectedPackage.id, email);
      // Validate that the URL is a Stripe checkout URL
      if (!checkoutUrl.startsWith('https://checkout.stripe.com/')) {
        throw new Error('Invalid checkout URL received');
      }
      window.location.href = checkoutUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create checkout session');
      setIsLoading(false);
    }
  };

  // Handle beta enrollment
  const handleBetaEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    setBetaError(null);

    // Validation
    if (!betaEmail) {
      setBetaError('Please enter your email address');
      return;
    }
    if (!betaAccept) {
      setBetaError('Please accept the corrections work agreement');
      return;
    }
    if (!betaPromise || betaPromise.length < 10) {
      setBetaError('Please write a sentence about a song you want to make into karaoke');
      return;
    }

    setBetaLoading(true);

    try {
      const response: BetaEnrollResponse = await api.enrollBetaTester(
        betaEmail,
        betaPromise,
        betaAccept
      );

      // If we got a session token, store it and redirect to main app
      if (response.session_token) {
        setAccessToken(response.session_token);
        setBetaSuccess(true);
        setBetaWillRedirect(true);
        // Redirect to main app after showing success message
        redirectTimeoutRef.current = setTimeout(() => {
          router.push('/app');
        }, 2000);
      } else {
        // No token means email verification needed
        setBetaSuccess(true);
        setBetaWillRedirect(false);
      }
    } catch (err) {
      setBetaError(err instanceof Error ? err.message : 'Failed to enroll in beta program');
    } finally {
      setBetaLoading(false);
    }
  };

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(0)}`;
  const pricePerVideo = (pkg: CreditPackage) =>
    `$${(pkg.price_cents / 100 / pkg.credits).toFixed(2)}`;

  // Show loading while checking auth
  if (isCheckingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center animated-gradient">
        <Loader2 className="w-8 h-8 animate-spin text-white" />
      </div>
    );
  }

  return (
    <div className="min-h-screen animated-gradient">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-dark-900/80 backdrop-blur-md border-b border-dark-700">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MicVocal className="w-8 h-8 text-primary-500" />
            <span className="text-xl font-bold">Nomad Karaoke</span>
          </div>
          <Link
            href="/app"
            className="text-sm text-dark-300 hover:text-white transition-colors"
          >
            Already have credits? Sign in
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold mb-6 leading-tight">
            Turn Any Song Into a{' '}
            <span className="gradient-text">Karaoke Video</span>
          </h1>
          <p className="text-xl text-dark-300 mb-8 max-w-2xl mx-auto">
            Professional karaoke videos in minutes. AI-powered vocal removal,
            perfect lyrics sync, and stunning video output.
          </p>
          <a
            href="#pricing"
            className="inline-flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white font-semibold px-8 py-4 rounded-xl transition-all btn-glow"
          >
            Get Started
            <ChevronDown className="w-5 h-5" />
          </a>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
          <div className="grid md:grid-cols-4 gap-8">
            {[
              { icon: Music, title: 'Search', desc: 'Enter artist & song title' },
              { icon: Sparkles, title: 'AI Magic', desc: 'We remove vocals & sync lyrics' },
              { icon: Video, title: 'Review', desc: 'Preview and fine-tune' },
              { icon: Youtube, title: 'Export', desc: 'Download or upload to YouTube' },
            ].map((step, i) => (
              <div key={i} className="text-center">
                <div className="w-16 h-16 bg-primary-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <step.icon className="w-8 h-8 text-primary-400" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
                <p className="text-dark-400 text-sm">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 px-4 bg-dark-800/50">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">What You Get</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { title: 'Studio-Quality Separation', desc: 'State-of-the-art AI removes vocals cleanly, keeping the instrumental crisp.' },
              { title: 'Perfect Lyrics Sync', desc: 'Word-by-word timing that highlights exactly when to sing.' },
              { title: 'Multiple Instrumental Options', desc: 'Choose from different vocal removal levels to get the sound you want.' },
              { title: '4K Video Output', desc: 'Stunning video quality that looks great on any screen.' },
              { title: 'YouTube Integration', desc: 'Upload directly to your YouTube channel with one click.' },
              { title: 'Edit Before Export', desc: 'Fix any lyrics issues before generating your final video.' },
            ].map((feature, i) => (
              <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl p-6 card-hover">
                <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                <p className="text-dark-400 text-sm">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Beta Tester Program */}
      <section className="py-12 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="bg-gradient-to-r from-purple-900/40 to-pink-900/40 border border-purple-500/30 rounded-2xl p-8 text-center">
            <div className="inline-flex items-center gap-2 bg-purple-500/20 text-purple-300 px-4 py-2 rounded-full text-sm font-medium mb-4">
              <Gift className="w-4 h-4" />
              Beta Tester Program
            </div>
            <h3 className="text-2xl font-bold mb-3">Try It Free!</h3>
            <p className="text-dark-300 mb-6">
              Help us improve by testing the tool and sharing your feedback. Get a{' '}
              <span className="text-green-400 font-semibold">free credit</span> to
              create your first karaoke video!
            </p>

            {!showBetaForm && !betaSuccess && (
              <button
                onClick={() => setShowBetaForm(true)}
                className="inline-flex items-center gap-2 bg-purple-500 hover:bg-purple-600 text-white font-semibold px-6 py-3 rounded-xl transition-all"
              >
                Join Beta Program
                <MessageSquare className="w-5 h-5" />
              </button>
            )}

            {showBetaForm && !betaSuccess && (
              <form onSubmit={handleBetaEnroll} className="mt-6 text-left space-y-4">
                <div>
                  <label htmlFor="beta-email" className="block text-sm font-medium text-dark-300 mb-2">
                    Email address
                  </label>
                  <input
                    type="email"
                    id="beta-email"
                    value={betaEmail}
                    onChange={(e) => setBetaEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full px-4 py-3 bg-dark-900 border border-dark-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white placeholder-dark-500"
                    required
                  />
                </div>

                <div>
                  <label htmlFor="beta-promise" className="block text-sm font-medium text-dark-300 mb-2">
                    What song do you want to make into karaoke?
                  </label>
                  <textarea
                    id="beta-promise"
                    value={betaPromise}
                    onChange={(e) => setBetaPromise(e.target.value)}
                    placeholder="Tell us about a song you'd love to sing..."
                    rows={3}
                    className="w-full px-4 py-3 bg-dark-900 border border-dark-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white placeholder-dark-500 resize-none"
                  />
                </div>

                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    id="beta-accept"
                    checked={betaAccept}
                    onChange={(e) => setBetaAccept(e.target.checked)}
                    className="mt-1 w-4 h-4 rounded border-dark-600 bg-dark-900 text-purple-500 focus:ring-purple-500"
                  />
                  <label htmlFor="beta-accept" className="text-sm text-dark-300">
                    I understand that beta testers help improve lyrics accuracy by reviewing and correcting AI-generated lyrics
                  </label>
                </div>

                {betaError && (
                  <p className="text-red-400 text-sm">{betaError}</p>
                )}

                <button
                  type="submit"
                  disabled={betaLoading}
                  className="w-full bg-purple-500 hover:bg-purple-600 disabled:bg-purple-500/50 text-white font-semibold py-3 rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  {betaLoading ? 'Enrolling...' : 'Get My Free Credit'}
                  {!betaLoading && <Gift className="w-5 h-5" />}
                </button>
              </form>
            )}

            {betaSuccess && (
              <div className="mt-6 p-4 bg-green-500/20 border border-green-500/30 rounded-xl">
                <p className="text-green-400 font-semibold">
                  Welcome to the beta program!{' '}
                  {betaWillRedirect
                    ? 'Redirecting to the app...'
                    : 'Check your email for a sign-in link.'}
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Simple Pricing</h2>
          <p className="text-dark-400 text-center mb-12 max-w-xl mx-auto">
            One credit = one karaoke video. Buy more to save more.
          </p>

          {/* Package Selection */}
          {packagesLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
            </div>
          )}
          {packagesError && (
            <div className="text-center py-8 text-red-400">
              {packagesError}
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {packages.map((pkg) => {
              const isSelected = selectedPackage?.id === pkg.id;
              const isBestValue = pkg.credits === 5;
              const savings = pkg.credits > 1 ? Math.round((1 - pkg.price_cents / (pkg.credits * 500)) * 100) : 0;

              return (
                <button
                  key={pkg.id}
                  onClick={() => setSelectedPackage(pkg)}
                  className={`relative p-4 rounded-xl border-2 transition-all ${
                    isSelected
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500 bg-dark-800/50'
                  }`}
                >
                  {isBestValue && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-500 text-white text-xs font-semibold px-3 py-1 rounded-full">
                      Best Value
                    </span>
                  )}
                  <div className="text-2xl font-bold mb-1">{pkg.credits}</div>
                  <div className="text-sm text-dark-400 mb-2">
                    {pkg.credits === 1 ? 'credit' : 'credits'}
                  </div>
                  <div className="text-xl font-semibold text-primary-400">
                    {formatPrice(pkg.price_cents)}
                  </div>
                  <div className="text-xs text-dark-500">{pricePerVideo(pkg)}/video</div>
                  {savings > 0 && (
                    <div className="text-xs text-green-400 mt-1">Save {savings}%</div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Checkout Form */}
          <div className="bg-dark-800 border border-dark-700 rounded-2xl p-8 max-w-md mx-auto">
            <div className="text-center mb-6">
              <div className="text-sm text-dark-400 mb-1">Selected package</div>
              <div className="text-2xl font-bold">
                {selectedPackage?.credits} Credits
              </div>
              <div className="text-3xl font-bold text-primary-400">
                {selectedPackage && formatPrice(selectedPackage.price_cents)}
              </div>
            </div>

            <form onSubmit={handleCheckout} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-dark-300 mb-2">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-500" />
                  <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full pl-10 pr-4 py-3 bg-dark-900 border border-dark-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-white placeholder-dark-500"
                    required
                  />
                </div>
                <p className="text-xs text-dark-500 mt-2">
                  We&apos;ll send your login link to this email
                </p>
              </div>

              {error && <p className="text-red-400 text-sm">{error}</p>}

              <button
                type="submit"
                disabled={isLoading || !selectedPackage}
                className="w-full bg-primary-500 hover:bg-primary-600 disabled:bg-primary-500/50 text-white font-semibold py-4 rounded-xl transition-all btn-glow flex items-center justify-center gap-2"
              >
                {isLoading ? 'Redirecting...' : 'Continue to Payment'}
                {!isLoading && <Check className="w-5 h-5" />}
              </button>
            </form>

            <div className="mt-4 flex items-center justify-center gap-4 text-xs text-dark-500">
              <span>Secure checkout</span>
              <span>powered by Stripe</span>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-4 bg-dark-800/50">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Questions?</h2>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                  aria-expanded={expandedFaq === i}
                  className="w-full px-6 py-4 text-left flex items-center justify-between hover:bg-dark-700/50 transition-colors"
                >
                  <span className="font-medium">{faq.question}</span>
                  <ChevronDown
                    className={`w-5 h-5 text-dark-400 transition-transform ${
                      expandedFaq === i ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {expandedFaq === i && (
                  <div className="px-6 pb-4 text-dark-300 text-sm">{faq.answer}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 border-t border-dark-700">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <MicVocal className="w-6 h-6 text-primary-500" />
            <span className="font-semibold">Nomad Karaoke</span>
          </div>
          <div className="text-sm text-dark-500">
            © {new Date().getFullYear()} Nomad Karaoke. All rights reserved.
          </div>
          <div className="flex gap-6 text-sm text-dark-400">
            <a href="mailto:support@nomadkaraoke.com" className="hover:text-white transition-colors">
              Support
            </a>
            <a href="https://nomadkaraoke.com" className="hover:text-white transition-colors">
              About
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
