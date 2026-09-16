import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));
vi.mock('@/services/overview-history', () => ({
  overviewHistorySettingsApi: {
    update: vi.fn(),
  },
}));
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';
import { useUpdateOverviewHistorySettings } from './useUpdateOverviewHistorySettings';

describe('useUpdateOverviewHistorySettings', () => {
  it('invalidates settings and history after a persisted window update', () => {
    const invalidateQueries = vi.fn();
    let onSuccess: (() => void) | undefined;
    vi.mocked(useQueryClient).mockReturnValue({
      invalidateQueries,
    } as never);
    vi.mocked(useMutation).mockImplementation((options) => {
      onSuccess = options.onSuccess as () => void;
      return {} as never;
    });
    useUpdateOverviewHistorySettings();
    expect(useMutation).toHaveBeenCalledWith(
      expect.objectContaining({
        mutationFn: overviewHistorySettingsApi.update,
      })
    );
    onSuccess?.();
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['overview-history-settings'],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['overview-history'],
    });
  });
});
