import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
}));
vi.mock('@/services/overview-clock-settings', () => ({
  overviewClockSettingsApi: {
    get: vi.fn(),
  },
}));
import { useQuery } from '@tanstack/react-query';
import { overviewClockSettingsApi } from '@/services/overview-clock-settings';
import { useOverviewClockSettings } from './useOverviewClockSettings';
describe('useOverviewClockSettings', () => {
  it('reads persistent clock settings without polling', () => {
    vi.mocked(useQuery).mockReturnValue({} as never);
    useOverviewClockSettings();
    expect(useQuery).toHaveBeenCalledWith({
      queryKey: ['overview-clock-settings'],
      queryFn: overviewClockSettingsApi.get,
      retry: false,
    });
  });
});
