/** @type {import('next').NextConfig} */
const nextConfig = {
  // Only use static export for production builds (not dev)
  output: process.env.NODE_ENV === 'production' ? 'export' : undefined,
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // GitHub Pages serves from subdomain, so no basePath needed
  // gen.nomadkaraoke.com -> nomadkaraoke.github.io/karaoke-gen

  // Proxy API requests to backend in development (avoids CORS)
  async rewrites() {
    // Only apply rewrites in development
    if (process.env.NODE_ENV === 'production') {
      return [];
    }
    const backendUrl = process.env.BACKEND_URL || 'https://api.nomadkaraoke.com';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
}

export default nextConfig
