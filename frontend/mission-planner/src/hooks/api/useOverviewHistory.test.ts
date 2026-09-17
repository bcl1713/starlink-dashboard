import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));
vi.mock('@/services/overview-history', () => ({
  overviewHistoryApi: {
    get: vi.fn(),
  },
}));
import { useQuery } from '@tanstack/react-query';
import { overviewHistoryApi } from '@/services/overview-history';
import { useOverviewHistory } from './useOverviewHistory';
describe('useOverviewHistory', () => {
  it('polls one shared history bundle independently of live status', () => {
    vi.mocked(useQuery).mockReturnValue({} as never);
    useOverviewHistory();
    expect(useQuery).toHaveBeenCalledWith({
      queryKey: ['overview-history'],
      queryFn: overviewHistoryApi.get,
      refetchInterval: 5_000,
      refetchIntervalInBackground: true,
      retry: false,
    });
  });
});
