/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    config.watchOptions = {
      ...(config.watchOptions || {}),
      ignored: [
        "**/test-results/**",
        "**/playwright-report/**",
        "**/next-debug.log",
      ],
    };
    return config;
  },
};

module.exports = nextConfig;
