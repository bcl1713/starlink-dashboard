import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));
vi.mock('@/services/overview-history', () => ({
  overviewHistorySettingsApi: {
    get: vi.fn(),
  },
}));
import { useQuery } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';
import { useOverviewHistorySettings } from './useOverviewHistorySettings';
describe('useOverviewHistorySettings', () => {
  it('reads the persisted history window without polling', () => {
    vi.mocked(useQuery).mockReturnValue({} as never);
    useOverviewHistorySettings();
    expect(useQuery).toHaveBeenCalledWith({
      queryKey: ['overview-history-settings'],
      queryFn: overviewHistorySettingsApi.get,
      retry: false,
    });
  });
});
