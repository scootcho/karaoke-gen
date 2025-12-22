/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // GitHub Pages serves from subdomain, so no basePath needed
  // gen.nomadkaraoke.com -> nomadkaraoke.github.io/karaoke-gen
}

export default nextConfig
