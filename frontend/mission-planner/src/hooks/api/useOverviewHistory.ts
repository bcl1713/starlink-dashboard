import { useQuery } from '@tanstack/react-query';
import { overviewHistoryApi } from '@/services/overview-history';

// Release gate: enable 1s after representative-host acceptance; 5s is rollback.
export function historyPollInterval(value: unknown): number {
  return value === '1' ? 1_000 : 5_000;
}

const POLL_INTERVAL = historyPollInterval(
  import.meta.env.VITE_OVERVIEW_HISTORY_POLL_SECONDS
);

export function useOverviewHistory() {
  return useQuery({
    queryKey: ['overview-history'],
    queryFn: overviewHistoryApi.get,
    refetchInterval: (query) =>
      query.state.status === 'error' ? 5_000 : POLL_INTERVAL,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: 'always',
    retry: false,
  });
}
