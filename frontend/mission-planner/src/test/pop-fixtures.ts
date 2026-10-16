import type { PopForecast } from '@/types/pop';
export const popForecast = (revision = 'route-one'): PopForecast => ({
  revision,
  catalog_fingerprint: 'catalog-one',
  status: 'ready',
  reason: null,
  transitions: [
    {
      crossing: {
        id: `${revision}:crossing`,
        from_pop_id: 'los-angeles',
        to_pop_id: 'dallas',
        from_city: 'Los Angeles',
        to_city: 'Dallas',
        segment_index: 0,
        fraction: 0.5,
        latitude: 34,
        longitude: -110,
        distance_meters: 1000,
      },
      crossing_utc: '2035-03-02T00:00:00Z',
      window_start_utc: '2035-03-01T23:55:00Z',
      window_end_utc: '2035-03-02T00:05:00Z',
    },
  ],
});
