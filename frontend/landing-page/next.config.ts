import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : "standalone",
  experimental: {
    outputFileTracingRoot: path.join(__dirname, "../../"),
  },
};

export default nextConfig;
