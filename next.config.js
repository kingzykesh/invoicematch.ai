/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'curacel',
        pathname: '/files/**',
      },
    ],
  },
};

module.exports = nextConfig;
