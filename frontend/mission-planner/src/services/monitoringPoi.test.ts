import { describe, expect, it } from 'vitest';
import poiEtaListResponse from './fixtures/poi-eta-list-response.json';
import { parseApplicablePois } from './monitoring';

describe('POI ETA response contract', () => {
  it('accepts and projects a complete serialized POI ETA response', () => {
    expect(parseApplicablePois(poiEtaListResponse)).toEqual([
      {
        poi_id: 'poi-normal',
        name: 'Airport',
        category: 'airport',
        eta_seconds: 60,
        distance_meters: 1000,
        active: true,
        latitude: 41,
        longitude: -96,
      },
      {
        poi_id: 'poi-no-eta',
        name: 'No ETA',
        category: null,
        eta_seconds: -1,
        distance_meters: 0,
        active: true,
        latitude: 0,
        longitude: 0,
      },
    ]);
  });

  it('strictly bounds the complete external POI contract', () => {
    const response = structuredClone(poiEtaListResponse);
    const poi = response.pois[0];
    expect(() =>
      parseApplicablePois({ ...response, pois: [{ ...poi, extra: true }] })
    ).toThrow();
    expect(() =>
      parseApplicablePois({
        ...response,
        pois: [{ ...poi, name: 'x'.repeat(201) }],
        total: 1,
      })
    ).toThrow();
    expect(() =>
      parseApplicablePois({
        ...response,
        pois: Array.from({ length: 101 }, () => poi),
        total: 101,
      })
    ).toThrow();
    expect(() => parseApplicablePois({ ...response, total: 3 })).toThrow();
    expect(() => parseApplicablePois({ ...response, extra: true })).toThrow();

    const invalidMutations = [
      { eta_seconds: -2 },
      { eta_type: 'unknown' },
      { flight_phase: 'taxiing' },
      { bearing_degrees: 361 },
      { course_status: 'lost' },
      { projected_latitude: 91 },
      { projected_longitude: 181 },
      { projected_waypoint_index: -1 },
      { projected_route_progress: 101 },
      { route_aware_status: 'unknown' },
      { icon: 'x'.repeat(201) },
    ];
    for (const mutation of invalidMutations) {
      expect(() =>
        parseApplicablePois({
          ...response,
          pois: [{ ...poi, ...mutation }],
          total: 1,
        })
      ).toThrow();
    }
  });
});
