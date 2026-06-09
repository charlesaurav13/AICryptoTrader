import type { NextConfig } from "next";

// Internal URL reachable from the Next.js server container.
// Browser calls /gw/* → Next.js server proxies to Go gateway internally.
// This avoids the browser ever needing to resolve "go-gateway" (Docker hostname).
const GO_INTERNAL = process.env.GO_INTERNAL_URL ?? "http://go-gateway:8080";

const nextConfig: NextConfig = {
  reactCompiler: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/gw/:path*",
        destination: `${GO_INTERNAL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
