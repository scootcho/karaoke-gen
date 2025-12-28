import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Nomad Karaoke - Turn Any Song Into a Karaoke Video',
  description: 'Create professional karaoke videos in minutes. AI-powered vocal separation, perfect lyrics sync, and 4K video output.',
  keywords: ['karaoke', 'karaoke video', 'karaoke maker', 'vocal removal', 'lyrics sync'],
  authors: [{ name: 'Nomad Karaoke' }],
  openGraph: {
    title: 'Nomad Karaoke - Turn Any Song Into a Karaoke Video',
    description: 'Create professional karaoke videos in minutes with AI.',
    type: 'website',
    url: 'https://buy.nomadkaraoke.com',
    images: [
      {
        url: 'https://nomadkaraoke.com/logo.png',
        width: 512,
        height: 512,
        alt: 'Nomad Karaoke',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Nomad Karaoke - Turn Any Song Into a Karaoke Video',
    description: 'Create professional karaoke videos in minutes with AI.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="https://nomadkaraoke.com/favicon.ico" />
      </head>
      <body className="min-h-screen animated-gradient">
        {children}
      </body>
    </html>
  );
}
