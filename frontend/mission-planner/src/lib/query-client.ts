import { QueryClient } from '@tanstack/react-query';

export function createQueryClient() {
  // API requests use the dashboard's own origin. Browser internet detection
  // must not pause reads or queue saves to a reachable local installation.
  return new QueryClient({
    defaultOptions: {
      queries: { networkMode: 'always' },
      mutations: { networkMode: 'always' },
    },
  });
}
