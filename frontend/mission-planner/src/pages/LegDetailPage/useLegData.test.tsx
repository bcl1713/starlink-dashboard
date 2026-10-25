// @vitest-environment jsdom
import { cleanup, renderHook, act } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useLegData } from './useLegData';
vi.mock('../../services/satellites', () => ({
  satelliteService: { getAll: async () => [] },
}));
vi.mock('../../services/pois', () => ({
  poisService: { getPOIsByRoute: async () => [] },
}));
vi.mock('../../services/routes', () => ({
  routesApi: { getCoordinates: async () => [], getWaypoints: async () => [] },
}));
afterEach(cleanup);
it('retains_pending_manual_edits_when_availability_refetch_changes_transports', () => {
  const { result, rerender } = renderHook(
    ({ transports }) => useLegData({ legTransports: transports }),
    { initialProps: { transports: { initial_x_satellite_id: 'X-1' } } }
  );
  act(() => {
    result.current.setSatelliteConfig((current) => ({
      ...current,
      xband_starting_satellite: 'X-2',
    }));
    result.current.setHasUnsavedChanges(true);
  });
  rerender({ transports: { initial_x_satellite_id: 'X-3' } });
  expect(result.current.satelliteConfig.xband_starting_satellite).toBe('X-2');
});

it('does_not_carry_pending_edits_to_another_leg_on_the_same_route', () => {
  const { result, rerender } = renderHook(
    ({ legId, transports }) =>
      useLegData({
        missionId: 'm',
        legId,
        routeId: 'shared-route',
        legTransports: transports,
      }),
    {
      initialProps: {
        legId: 'one',
        transports: { initial_x_satellite_id: 'X-1' },
      },
    }
  );
  act(() => {
    result.current.setSatelliteConfig((current) => ({
      ...current,
      xband_starting_satellite: 'X-local',
    }));
    result.current.setHasUnsavedChanges(true);
  });
  rerender({ legId: 'two', transports: { initial_x_satellite_id: 'X-2' } });
  expect(result.current.satelliteConfig.xband_starting_satellite).toBe('X-2');
  expect(result.current.hasUnsavedChanges).toBe(false);
});
