import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const backendProxyTarget =
  process.env.STARLINK_DEV_BACKEND_ORIGIN ?? 'http://localhost:8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': backendProxyTarget,
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
