import type { NextConfig } from "next";

// The browser talks only to this app; /api/* is forwarded to the FastAPI backend,
// so no CORS opening is needed and the backend can stay on loopback.
const apiOrigin = process.env.MASTRR_API_ORIGIN ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  distDir: process.env.MASTRR_DEMO_FRONTEND === "1" ? ".next-demo" : ".next",
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'" },
    ] }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default config;
