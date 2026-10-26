import type { NextConfig } from "next";

// The browser talks only to this app; /api/* is forwarded to the FastAPI backend,
// so no CORS opening is needed and the backend can stay on loopback.
const apiOrigin = process.env.MASTRR_API_ORIGIN ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default config;
