import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));
vi.mock('@/services/overview-clock-settings', () => ({
  overviewClockSettingsApi: {
    update: vi.fn(),
  },
}));
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewClockSettingsApi } from '@/services/overview-clock-settings';
import { useUpdateOverviewClockSettings } from './useUpdateOverviewClockSettings';
describe('useUpdateOverviewClockSettings', () => {
  it('refreshes the saved clock collection after a successful replacement', () => {
    const invalidateQueries = vi.fn();
    let onSuccess: (() => void) | undefined;
    vi.mocked(useQueryClient).mockReturnValue({
      invalidateQueries,
    } as never);
    vi.mocked(useMutation).mockImplementation((options) => {
      onSuccess = options.onSuccess as () => void;
      return {} as never;
    });
    useUpdateOverviewClockSettings();
    expect(useMutation).toHaveBeenCalledWith(
      expect.objectContaining({
        mutationFn: overviewClockSettingsApi.update,
      })
    );
    onSuccess?.();
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['overview-clock-settings'],
    });
  });
});
