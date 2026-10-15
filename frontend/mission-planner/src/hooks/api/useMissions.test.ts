import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));
vi.mock('../../services/missions', () => ({
  missionsApi: {
    activateLeg: vi.fn(),
    deactivateAllLegs: vi.fn(),
  },
}));
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useActivateLeg, useDeactivateAllLegs } from './useMissions';
describe('mission clock cache invalidation', () => {
  it('refreshes overview clocks after activating a leg', () => {
    const invalidateQueries = vi.fn();
    let onSuccess:
      | ((
          data: unknown,
          variables: { missionId: string; legId: string }
        ) => void)
      | undefined;
    vi.mocked(useQueryClient).mockReturnValue({
      invalidateQueries,
    } as never);
    vi.mocked(useMutation).mockImplementation((options) => {
      onSuccess = options.onSuccess as typeof onSuccess;
      return {} as never;
    });
    useActivateLeg();
    onSuccess?.(undefined, {
      missionId: 'mission-1',
      legId: 'leg-1',
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['overview-clock-settings'],
    });
  });
  it('refreshes overview clocks after deactivating a mission', () => {
    const invalidateQueries = vi.fn();
    let onSuccess: (() => void) | undefined;
    vi.mocked(useQueryClient).mockReturnValue({
      invalidateQueries,
    } as never);
    vi.mocked(useMutation).mockImplementation((options) => {
      onSuccess = options.onSuccess as typeof onSuccess;
      return {} as never;
    });
    useDeactivateAllLegs('mission-1');
    onSuccess?.();
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['overview-clock-settings'],
    });
  });
});
