import type { NextConfig } from "next";

// The admin site must know which API it talks to, and must never guess. Without this variable the
// build (and `next dev`) stops here, so a staging build can't quietly end up pointed at production.
//   development:  put it in .env.local, e.g. NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
//   staging:      NEXT_PUBLIC_API_URL=https://hostel-hunt-admin-pannel.onrender.com/api/v1
//   production:   NEXT_PUBLIC_API_URL=https://hostel-hunt-backend.onrender.com/api/v1
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
if (!apiUrl || !/^https?:\/\//.test(apiUrl)) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is missing or is not an http(s) address. Set it (for example in .env.local) to the " +
      "backend's /api/v1 address before building or starting the admin site."
  );
}

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: ['192.168.1.51', '192.168.1.61', 'localhost'],
};

export default nextConfig;
