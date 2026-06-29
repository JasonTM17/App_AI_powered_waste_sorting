import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  env: {
    TRASH_SORTER_CLIENT_REQUEST_CONCURRENCY:
      process.env.TRASH_SORTER_CLIENT_REQUEST_CONCURRENCY ?? "2",
    TRASH_SORTER_HARDWARE_REQUEST_CONCURRENCY:
      process.env.TRASH_SORTER_HARDWARE_REQUEST_CONCURRENCY ?? "1"
  },
  output: "standalone",
  poweredByHeader: false
};

export default nextConfig;
