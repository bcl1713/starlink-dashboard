import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import {
  getMissionEventETAs,
  getPOIETAs,
  getSatelliteETAs,
} from './monitoring';
import {
  aware,
  missing,
  poi,
  poiPayload,
  setAt,
  withResponse,
} from './monitoring-test-fixtures';
import { OVERVIEW_POI_FILTER_OPTIONS } from '../types/monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
}

async function expectPoiInvalid(payload: unknown) {
  respond(payload);
  await expect(getPOIETAs()).rejects.toMatchObject({ source: 'poi-etas' });
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
      [() => getPOIETAs(undefined, signal), '?category=departure%2Carrival'],
      [() => getPOIETAs('', signal), ''],
      [() => getPOIETAs('departure', signal), '?category=departure'],
      [() => getSatelliteETAs(signal), '?category=satellite'],
      [() => getMissionEventETAs(signal), '?category=mission-event'],
    ] as const;

    for (const [call, query] of cases) {
      respond(query ? poiPayload : { pois: [], total: 0, timestamp: aware });
      await call();
      expect(getMock).toHaveBeenLastCalledWith(`/api/pois/etas${query}`, {
        signal,
      });
    }
  });

  it('parses every enum, null, and sentinel variant', async () => {
    const variants = [
      { ...poi, eta_type: 'estimated', flight_phase: 'in_flight' },
      { ...poi, flight_phase: 'post_arrival', course_status: 'slightly_off' },
      {
        ...poi,
        course_status: 'off_track',
        route_aware_status: 'ahead_on_route',
      },
      { ...poi, course_status: 'behind', route_aware_status: 'already_passed' },
      { ...poi, route_aware_status: 'not_on_route' },
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

  it('rejects malformed POI ETA contracts and management id', async () => {
    const invalidPois = [
      { ...poi, id: 'management-id' },
      { ...poi, poi_id: undefined },
      { ...poi, poi_id: 123 },
      { ...poi, name: 123 },
      { ...poi, icon: 123 },
      { ...poi, active: 'true' },
      { ...poi, latitude: -91 },
      { ...poi, latitude: NaN },
      { ...poi, latitude: '39' },
      { ...poi, longitude: 181 },
      { ...poi, longitude: Infinity },
      { ...poi, longitude: '-104' },
      { ...poi, eta_seconds: Infinity },
      { ...poi, eta_seconds: '1' },
      { ...poi, eta_type: 'actual' },
      { ...poi, flight_phase: 'taxi' },
      { ...poi, distance_meters: -1 },
      { ...poi, distance_meters: NaN },
      { ...poi, bearing_degrees: -1 },
      { ...poi, bearing_degrees: 361 },
      { ...poi, bearing_degrees: Infinity },
      { ...poi, course_status: 'lost' },
      { ...poi, is_on_active_route: 'true' },
      { ...poi, projected_latitude: null },
      { ...poi, projected_longitude: null },
      { ...poi, projected_latitude: -91 },
      { ...poi, projected_longitude: 181 },
      { ...poi, projected_latitude: NaN },
      { ...poi, projected_waypoint_index: -1 },
      { ...poi, projected_waypoint_index: 1.2 },
      { ...poi, projected_waypoint_index: Infinity },
      { ...poi, projected_route_progress: -1 },
      { ...poi, projected_route_progress: 101 },
      { ...poi, projected_route_progress: Infinity },
      { ...poi, route_aware_status: 'missed' },
      { ...poi, extra: true },
    ];
    const invalid = [
      setAt(poiPayload, ['total'], 2),
      setAt(poiPayload, ['total'], -1),
      setAt(poiPayload, ['timestamp'], '2026-08-29T12:34:56'),
      setAt(poiPayload, ['timestamp'], missing),
      setAt(poiPayload, ['extra'], true),
      ...invalidPois.map((badPoi) => ({
        pois: [badPoi],
        total: 1,
        timestamp: aware,
      })),
    ];

    for (const bad of invalid) await expectPoiInvalid(bad);
  });
});
