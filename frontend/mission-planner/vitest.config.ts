import { defineConfig } from 'vitest/config';
import { applicationResolve } from './vite.shared';

export default defineConfig({
  resolve: applicationResolve,
  test: {
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
  },
});
