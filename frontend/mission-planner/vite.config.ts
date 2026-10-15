import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const backendProxyTarget =
  process.env.STARLINK_DEV_BACKEND_ORIGIN ?? 'http://localhost:8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  worker: { format: 'es' },
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
    alias: {
      '@react-three/fiber': path.resolve(
        __dirname,
        'node_modules/@react-three/fiber/dist/react-three-fiber.esm.js'
      ),
      '@react-three/test-renderer': path.resolve(
        __dirname,
        'node_modules/@react-three/test-renderer/dist/react-three-test-renderer.esm.js'
      ),
    },
    server: {
      deps: {
        // Use the ESM entries so the renderer and app share Three.js classes.
        inline: ['@react-three/test-renderer', '@react-three/fiber'],
      },
    },
  },
});
