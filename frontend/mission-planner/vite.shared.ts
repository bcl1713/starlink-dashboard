import { fileURLToPath, URL } from 'node:url';

export const applicationResolve = {
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url)),
  },
};
