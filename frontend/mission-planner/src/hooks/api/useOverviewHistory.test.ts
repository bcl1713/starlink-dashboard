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
import { historyPollInterval, useOverviewHistory } from './useOverviewHistory';
describe('useOverviewHistory', () => {
  it('polls one shared history bundle independently of live status', () => {
    vi.mocked(useQuery).mockReturnValue({} as never);
    useOverviewHistory();
    expect(useQuery).toHaveBeenCalledWith({
      queryKey: ['overview-history'],
      queryFn: expect.any(Function),
      refetchInterval: expect.any(Function),
      refetchIntervalInBackground: true,
      refetchOnWindowFocus: 'always',
      retry: false,
    });
    const options = vi.mocked(useQuery).mock.calls.at(-1)![0];
    const interval = options.refetchInterval;
    expect(typeof interval).toBe('function');
    if (typeof interval === 'function') {
      expect(interval({ state: { status: 'success' } } as never)).toBe(1_000);
      expect(interval({ state: { status: 'error' } } as never)).toBe(5_000);
    }
  });

  it('defaults to 1s while preserving explicit rollback and invalid fallback', () => {
    expect(historyPollInterval(undefined)).toBe(1_000);
    expect(historyPollInterval('1')).toBe(1_000);
    for (const value of ['5', '0', 'invalid', '', null, 1])
      expect(historyPollInterval(value)).toBe(5_000);
  });
});
