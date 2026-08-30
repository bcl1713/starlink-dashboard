import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import {
  getMissionEventETAs,
  getPOIETAs,
  getSatelliteETAs,
} from './monitoring';
import { OVERVIEW_POI_FILTER_OPTIONS } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56Z';
const poi = {
  poi_id: 'poi-1',
  name: 'Departure',
  latitude: 39,
  longitude: -104,
  category: 'departure',
  icon: 'plane-takeoff',
  active: true,
  eta_seconds: -1,
  eta_type: 'anticipated',
  is_pre_departure: true,
  flight_phase: 'pre_departure',
  distance_meters: 0,
  bearing_degrees: 360,
  course_status: 'on_course',
  is_on_active_route: true,
  projected_latitude: 39,
  projected_longitude: -104,
  projected_waypoint_index: 0,
  projected_route_progress: 100,
  route_aware_status: 'pre_departure',
};
const payload = { pois: [poi], total: 1, timestamp: aware };

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

describe('POI ETA overview service', () => {
  it('exports ordered filter options', () => {
    expect(OVERVIEW_POI_FILTER_OPTIONS).toEqual([
      { label: 'Departure & Arrival', value: 'departure,arrival' },
      { label: 'All POIs', value: '' },
      { label: 'Departure Only', value: 'departure' },
      { label: 'Arrival Only', value: 'arrival' },
      { label: 'Waypoints Only', value: 'waypoint' },
      { label: 'Alternates Only', value: 'alternate' },
    ]);
  });

  it('constructs exact category params, helpers, all omission, and signal identity', async () => {
    const signal = new AbortController().signal;
    const cases = [
      [() => getPOIETAs(undefined, signal), { category: 'departure,arrival' }],
      [() => getPOIETAs('', signal), undefined],
      [() => getPOIETAs('departure', signal), { category: 'departure' }],
      [() => getSatelliteETAs(signal), { category: 'satellite' }],
      [() => getMissionEventETAs(signal), { category: 'mission-event' }],
    ] as const;

    for (const [call, params] of cases) {
      respond(params ? payload : { pois: [], total: 0, timestamp: aware });
      await call();
      expect(getMock).toHaveBeenLastCalledWith(
        '/api/pois/etas',
        params ? { params, signal } : { signal }
      );
    }
  });

  it('parses enum and nullable variants while preserving timestamp text', async () => {
    const variants = [
      { ...poi, eta_type: 'estimated', flight_phase: 'in_flight' },
      { ...poi, flight_phase: 'post_arrival', course_status: 'slightly_off' },
      {
        ...poi,
        course_status: 'off_track',
        route_aware_status: 'already_passed',
      },
      { ...poi, course_status: 'behind', route_aware_status: 'not_on_route' },
      {
        ...poi,
        category: null,
        bearing_degrees: null,
        course_status: null,
        flight_phase: null,
        projected_latitude: null,
        projected_longitude: null,
        projected_waypoint_index: null,
        projected_route_progress: null,
        route_aware_status: null,
      },
    ];
    const response = {
      pois: variants,
      total: variants.length,
      timestamp: aware,
    };
    respond(response);

    await expect(getPOIETAs()).resolves.toEqual(response);
  });

  it('rejects malformed nested POI ETA contracts and management id', async () => {
    const invalidPois = [
      { ...poi, id: 'management-id' },
      { ...poi, poi_id: undefined },
      { ...poi, latitude: -91 },
      { ...poi, longitude: 181 },
      { ...poi, eta_seconds: Infinity },
      { ...poi, eta_type: 'actual' },
      { ...poi, flight_phase: 'taxi' },
      { ...poi, distance_meters: -1 },
      { ...poi, bearing_degrees: 361 },
      { ...poi, course_status: 'lost' },
      { ...poi, projected_latitude: null },
      { ...poi, projected_longitude: null },
      { ...poi, projected_waypoint_index: -1 },
      { ...poi, projected_waypoint_index: 1.2 },
      { ...poi, projected_route_progress: 101 },
      { ...poi, route_aware_status: 'missed' },
    ];
    const invalid = [
      { ...payload, total: 2 },
      { ...payload, timestamp: '2026-08-29T12:34:56' },
      { ...payload, extra: true },
      ...invalidPois.map((badPoi) => ({
        pois: [badPoi],
        total: 1,
        timestamp: aware,
      })),
    ];

    for (const bad of invalid) {
      respond(bad);
      await expect(getPOIETAs()).rejects.toMatchObject({ source: 'poi-etas' });
    }
  });
});
