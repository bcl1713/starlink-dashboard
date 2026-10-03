/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { missionsApi } from '../../services/missions';
import { poisService, type POI } from '../../services/pois';
import { routesApi } from '../../services/routes';
import { POIDialog } from './POIDialog';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('populates an edit form from a delayed POI response and retains saved metadata', async () => {
  const poi: POI = {
    id: 'saved-poi',
    name: 'Greenwich waypoint',
    latitude: 51.48,
    longitude: 0,
    icon: '📍',
    category: 'waypoint',
    description: 'Keep this saved description',
    route_id: null,
    mission_id: null,
    active: true,
    created_at: '2026-10-03T00:00:00Z',
    updated_at: '2026-10-03T00:00:00Z',
  };
  let resolveDetail!: (poi: POI) => void;
  const detail = new Promise<POI>((resolve) => {
    resolveDetail = resolve;
  });
  vi.spyOn(poisService, 'getPOI').mockReturnValue(detail);
  const update = vi.spyOn(poisService, 'updatePOI').mockResolvedValue(poi);
  vi.spyOn(routesApi, 'list').mockResolvedValue([]);
  vi.spyOn(missionsApi, 'list').mockResolvedValue([]);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <POIDialog open poiId="saved-poi" onOpenChange={() => {}} />
    </QueryClientProvider>
  );
  expect(
    (screen.getByRole('button', { name: 'Saving...' }) as HTMLButtonElement)
      .disabled
  ).toBe(true);
  await act(async () => {
    resolveDetail(poi);
    await detail;
  });
  await waitFor(() => {
    expect((screen.getByLabelText('Name *') as HTMLInputElement).value).toBe(
      'Greenwich waypoint'
    );
  });
  expect((screen.getByLabelText('Category *') as HTMLSelectElement).value).toBe(
    'waypoint'
  );
  expect((screen.getByLabelText('Description') as HTMLInputElement).value).toBe(
    'Keep this saved description'
  );
  fireEvent.change(screen.getByLabelText('Name *'), {
    target: { value: 'Renamed waypoint' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save POI' }));
  await waitFor(() => {
    expect(update).toHaveBeenCalledWith(
      'saved-poi',
      expect.objectContaining({
        name: 'Renamed waypoint',
        category: 'waypoint',
        description: 'Keep this saved description',
        latitude: 51.48,
        longitude: 0,
      })
    );
  });
});
