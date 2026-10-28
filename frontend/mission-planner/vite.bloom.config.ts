import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const sourceSha = execFileSync('git', ['rev-parse', 'HEAD'], {
  encoding: 'utf8',
}).trim();
const dirty =
  execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim()
    .length > 0;
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'bloom-build-stamp',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'build.json',
          source: JSON.stringify(
            {
              sourceSha,
              dirty,
              node: process.version,
              scenario: 'synthetic-bloom-v1',
            },
            null,
            2
          ),
        });
      },
    },
  ],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  define: {
    __BLOOM_SHA__: JSON.stringify(sourceSha),
    __BLOOM_DIRTY__: JSON.stringify(dirty),
  },
  worker: { format: 'es' },
  build: { outDir: 'dist-bloom', rollupOptions: { input: 'bloom.html' } },
  // No dev server / API proxy; measurements use the static production build.
});
