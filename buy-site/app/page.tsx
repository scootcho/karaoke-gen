'use client';

import { useState } from 'react';
import { Mic2, Music, Sparkles, Video, Youtube, Check, ChevronDown, Mail, Loader2 } from 'lucide-react';

// Credit packages (matching backend)
const CREDIT_PACKAGES = [
  {
    id: '1_credit',
    credits: 1,
    price_cents: 500,
    name: '1 Credit',
    description: 'Create 1 karaoke video',
    popular: false,
  },
  {
    id: '3_credits',
    credits: 3,
    price_cents: 1200,
    name: '3 Credits',
    description: 'Save 20%',
    popular: false,
  },
  {
    id: '5_credits',
    credits: 5,
    price_cents: 1750,
    name: '5 Credits',
    description: 'Save 30%',
    popular: true,
  },
  {
    id: '10_credits',
    credits: 10,
    price_cents: 3000,
    name: '10 Credits',
    description: 'Save 40%',
    popular: false,
  },
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.nomadkaraoke.com';

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(0)}`;
}

function pricePerCredit(priceCents: number, credits: number): string {
  return `$${(priceCents / 100 / credits).toFixed(2)}`;
}

export default function Home() {
  const [selectedPackage, setSelectedPackage] = useState(CREDIT_PACKAGES[2]); // Default to 5 credits
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  const handleCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email) {
      setError('Please enter your email');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/users/credits/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          package_id: selectedPackage.id,
          email: email.toLowerCase(),
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create checkout');
      }

      const data = await response.json();
      window.location.href = data.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
      setIsLoading(false);
    }
  };

  const faqs = [
    {
      q: 'How does it work?',
      a: 'Just enter a song (artist + title), and our AI finds the audio, removes the vocals, transcribes the lyrics, and creates a professional karaoke video with perfectly synced lyrics.',
    },
    {
      q: 'What songs can I use?',
      a: "Most popular songs are available. We search multiple high-quality audio sources to find the best version. If we can't find a song, you won't be charged.",
    },
    {
      q: 'What format is the output?',
      a: 'You get a high-quality MP4 video file (up to 4K) with the instrumental audio and synchronized lyrics. You can also upload directly to YouTube.',
    },
    {
      q: 'What if something goes wrong?',
      a: "We offer generous refunds. If the quality isn't what you expected or there's an issue with the output, contact us and we'll refund your credit.",
    },
    {
      q: 'Do credits expire?',
      a: 'No, your credits never expire. Use them whenever you want.',
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-dark-900/80 backdrop-blur-md border-b border-dark-700">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mic2 className="w-8 h-8 text-primary-500" />
            <span className="text-xl font-bold">Nomad Karaoke</span>
          </div>
          <a
            href="https://gen.nomadkaraoke.com"
            className="text-sm text-dark-300 hover:text-white transition-colors"
          >
            Already have credits? Sign in
          </a>
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
              {
                icon: Music,
                title: 'Search',
                desc: 'Enter artist & song title',
              },
              {
                icon: Sparkles,
                title: 'AI Magic',
                desc: 'We remove vocals & sync lyrics',
              },
              {
                icon: Video,
                title: 'Review',
                desc: 'Preview and fine-tune',
              },
              {
                icon: Youtube,
                title: 'Export',
                desc: 'Download or upload to YouTube',
              },
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
              {
                title: 'Studio-Quality Separation',
                desc: 'State-of-the-art AI removes vocals cleanly, keeping the instrumental crisp.',
              },
              {
                title: 'Perfect Lyrics Sync',
                desc: 'Word-by-word timing that highlights exactly when to sing.',
              },
              {
                title: 'Multiple Instrumental Options',
                desc: 'Choose from different vocal removal levels to get the sound you want.',
              },
              {
                title: '4K Video Output',
                desc: 'Stunning video quality that looks great on any screen.',
              },
              {
                title: 'YouTube Integration',
                desc: 'Upload directly to your YouTube channel with one click.',
              },
              {
                title: 'Edit Before Export',
                desc: 'Fix any lyrics issues before generating your final video.',
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="bg-dark-800 border border-dark-700 rounded-xl p-6 card-hover"
              >
                <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                <p className="text-dark-400 text-sm">{feature.desc}</p>
              </div>
            ))}
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {CREDIT_PACKAGES.map((pkg) => (
              <button
                key={pkg.id}
                onClick={() => setSelectedPackage(pkg)}
                className={`relative p-4 rounded-xl border-2 transition-all ${
                  selectedPackage.id === pkg.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-700 hover:border-dark-500 bg-dark-800/50'
                }`}
              >
                {pkg.popular && (
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
                <div className="text-xs text-dark-500">
                  {pricePerCredit(pkg.price_cents, pkg.credits)}/video
                </div>
                {pkg.credits > 1 && (
                  <div className="text-xs text-green-400 mt-1">{pkg.description}</div>
                )}
              </button>
            ))}
          </div>

          {/* Checkout Form */}
          <div className="bg-dark-800 border border-dark-700 rounded-2xl p-8 max-w-md mx-auto">
            <div className="text-center mb-6">
              <div className="text-sm text-dark-400 mb-1">Selected package</div>
              <div className="text-2xl font-bold">
                {selectedPackage.credits} {selectedPackage.credits === 1 ? 'Credit' : 'Credits'}
              </div>
              <div className="text-3xl font-bold text-primary-400">
                {formatPrice(selectedPackage.price_cents)}
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

              {error && (
                <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg p-3">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-primary-500 hover:bg-primary-600 disabled:bg-primary-500/50 text-white font-semibold py-4 rounded-xl transition-all btn-glow flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Redirecting to checkout...
                  </>
                ) : (
                  <>
                    Continue to Payment
                    <Check className="w-5 h-5" />
                  </>
                )}
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
              <div
                key={i}
                className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                  className="w-full px-6 py-4 text-left flex items-center justify-between hover:bg-dark-700/50 transition-colors"
                >
                  <span className="font-medium">{faq.q}</span>
                  <ChevronDown
                    className={`w-5 h-5 text-dark-400 transition-transform ${
                      expandedFaq === i ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {expandedFaq === i && (
                  <div className="px-6 pb-4 text-dark-400">{faq.a}</div>
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
            <Mic2 className="w-6 h-6 text-primary-500" />
            <span className="font-semibold">Nomad Karaoke</span>
          </div>
          <div className="text-sm text-dark-500">
            &copy; {new Date().getFullYear()} Nomad Karaoke. All rights reserved.
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
