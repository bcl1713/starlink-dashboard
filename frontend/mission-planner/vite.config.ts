import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const radarPng = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49,
  0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06,
  0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44,
  0x41, 0x54, 0x78, 0x9c, 0x63, 0xf8, 0xcf, 0xc0, 0xf0, 0x1f, 0x00, 0x05, 0x00,
  0x01, 0xff, 0x89, 0x99, 0x3d, 0x1d, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
]);

function serveLocalRadarTile() {
  const pattern = /^\/api\/weather\/radar\/rainviewer\/\d+\/\d+\/\d+\.png$/;
  const enabled = process.env.PLAYWRIGHT_PORT !== undefined;
  return {
    name: 'serve-local-radar-tile',
    configureServer(server: import('vite').ViteDevServer) {
      server.middlewares.use((request, response, next) => {
        if (
          !enabled ||
          !request.url ||
          !pattern.test(new URL(request.url, 'http://local').pathname)
        ) {
          next();
          return;
        }
        response.setHeader('content-type', 'image/png');
        response.setHeader('x-radar-frame-timestamp', '1777294800');
        response.end(radarPng);
      });
    },
    configurePreviewServer(server: import('vite').PreviewServer) {
      server.middlewares.use((request, response, next) => {
        if (
          !enabled ||
          !request.url ||
          !pattern.test(new URL(request.url, 'http://local').pathname)
        ) {
          next();
          return;
        }
        response.setHeader('content-type', 'image/png');
        response.setHeader('x-radar-frame-timestamp', '1777294800');
        response.end(radarPng);
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [serveLocalRadarTile(), react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
