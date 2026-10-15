import { describe, expect, it, vi } from 'vitest';

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));
vi.mock('@/services/overview-upcoming-pois', () => ({
  overviewUpcomingPoisApi: {
    get: vi.fn(),
  },
}));

import { useQuery } from '@tanstack/react-query';
import { overviewUpcomingPoisApi } from '@/services/overview-upcoming-pois';
import { useOverviewUpcomingPois } from './useOverviewUpcomingPois';

describe('useOverviewUpcomingPois', () => {
  it('polls the overview POI endpoint every five seconds in the background without retries', () => {
    vi.mocked(useQuery).mockReturnValue({} as never);

    useOverviewUpcomingPois();

    expect(useQuery).toHaveBeenCalledWith({
      queryKey: ['overview-upcoming-pois'],
      queryFn: overviewUpcomingPoisApi.get,
      refetchInterval: 5_000,
      refetchIntervalInBackground: true,
      retry: false,
    });
  });
});
