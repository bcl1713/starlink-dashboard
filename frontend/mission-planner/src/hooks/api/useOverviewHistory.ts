import { useQuery } from '@tanstack/react-query';
import { overviewHistoryApi } from '@/services/overview-history';

// Qualified 1s default; explicit 5 or invalid settings preserve safe rollback.
export function historyPollInterval(value: unknown): number {
  return value === undefined || value === '1' ? 1_000 : 5_000;
}

const POLL_INTERVAL = historyPollInterval(
  import.meta.env.VITE_OVERVIEW_HISTORY_POLL_SECONDS
);

export function useOverviewHistory() {
  return useQuery({
    queryKey: ['overview-history'],
    queryFn: ({ signal }) => overviewHistoryApi.get(signal),
    refetchInterval: (query) =>
      query.state.status === 'error' ? 5_000 : POLL_INTERVAL,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: 'always',
    retry: false,
  });
}
