import { describe, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { overviewUpcomingPoisApi } from './overview-upcoming-pois';

vi.mock('./api-client', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('overviewUpcomingPoisApi', () => {
  it('gets the typed dynamic overview POI response', async () => {
    const response = {
      state: 'available' as const,
      calculated_at: '2026-09-22T12:00:00.000Z',
      pois: [
        {
          poi_id: 'departure-1',
          name: 'Departure',
          kind: 'departure' as const,
          latitude: 41.2,
          longitude: -95.9,
          expected_arrival_time: '2026-09-22T12:10:00.000Z',
          eta_seconds: 600,
          estimated_arrival_time: '2026-09-22T12:11:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
      ],
    };
    vi.mocked(apiClient.get).mockResolvedValue({ data: response } as never);

    await expect(overviewUpcomingPoisApi.get()).resolves.toEqual(response);
    expect(apiClient.get).toHaveBeenCalledWith('/api/overview/upcoming-pois');
  });
});
