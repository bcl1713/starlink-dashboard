import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';
import { defineConfig } from 'eslint/config';

export default defineConfig([
  {
    ignores: [
      'node_modules/',
      '.venv/',
      'venv/',
      'dist/',
      'build/',
      '*.egg-info/',
      'coverage/',
      '.coverage',
      '.nyc_output/',
      '.vscode/',
      '.idea/',
      '*.swp',
      '*.swo',
      '.env',
      '.env.*',
      '.DS_Store',
      'Thumbs.db',
      '.pytest_cache/',
      'test-results/',
      'playwright-report/',
      '*.log',
      '**/*.min.js',
    ],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      'no-console': ['warn', { allow: ['error', 'log', 'warn', 'info'] }],
    },
  },
]);
