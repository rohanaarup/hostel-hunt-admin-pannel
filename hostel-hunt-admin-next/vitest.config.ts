import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Unit and component tests for the admin site. They run in a simulated browser (jsdom) with no network.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // The address the site is built with; tests never call it.
    env: { NEXT_PUBLIC_API_URL: 'http://api.test/api/v1' },
  },
});
