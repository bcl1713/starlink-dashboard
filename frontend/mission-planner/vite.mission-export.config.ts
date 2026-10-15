import { defineConfig } from 'vite';
import { copyFileSync } from 'node:fs';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'local-map-textures',
      closeBundle() {
        for (const name of ['earth-day-hi.jpg', 'city-lights-mask.png'])
          copyFileSync(`public/${name}`, `dist-mission-export/${name}`);
      },
    },
  ],
  publicDir: false,
  build: {
    outDir: 'dist-mission-export',
    rollupOptions: { input: 'mission-export.html' },
  },
});
