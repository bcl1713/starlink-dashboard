import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import {
  getActiveXLink,
  getMissionEventETAs,
  getPOIETAs,
  getRouteCoordinates,
  getSatelliteETAs,
} from './monitoring';
import { OVERVIEW_POI_FILTER_OPTIONS } from '../types/monitoring';

vi.mock('./api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

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
  bearing_degrees: null,
  course_status: null,
  is_on_active_route: true,
  projected_latitude: null,
  projected_longitude: null,
  projected_waypoint_index: null,
  projected_route_progress: null,
  route_aware_status: 'pre_departure',
};

const poiPayload = {
  pois: [poi],
  total: 1,
  timestamp: aware,
};

const routePayload = {
  route_id: 'route-1',
  route_name: null,
  revision_at: '2026-08-29T12:00:00+00:00',
  generated_at: aware,
  total: 1,
  coordinates: [
    {
      latitude: 39,
      longitude: -104,
      altitude_meters: null,
      sequence: 1.5,
    },
  ],
};

const coordinate = {
  satellite_id: 'sat-1',
  state: 'normal',
  color: 'green',
  relative_azimuth_degrees: 12.5,
  in_forbidden_window: false,
  point: 'aircraft',
  sequence: 0,
  latitude: 39,
  longitude: -104,
  observed_at: null,
};

const handoff = {
  phase: 'outside',
  transition_id: null,
  transition_satellite_id: null,
  radius_meters: 1000,
  distance_to_transition_meters: null,
  in_handoff_zone: false,
  route_progress_percent: null,
  transition_progress_percent: null,
};

const activeXLinkPayload = {
  coordinates: [coordinate],
  links: [
    {
      satellite_id: 'sat-1',
      state: 'normal',
      color: 'green',
      relative_azimuth_degrees: 12.5,
      in_forbidden_window: false,
      coordinates: [
        coordinate,
        { ...coordinate, point: 'satellite', sequence: 1 },
      ],
    },
  ],
  total: 1,
  satellite_id: 'sat-1',
  pending_satellite_id: null,
  handoff,
  state: 'normal',
  color: 'green',
  relative_azimuth_degrees: 12.5,
  in_forbidden_window: false,
  observed_at: null,
  generated_at: aware,
};

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

beforeEach(() => {
  getMock.mockReset();
});

describe('monitoring overlay services', () => {
  it('exports ordered POI filter options', () => {
    expect(OVERVIEW_POI_FILTER_OPTIONS).toEqual([
      { label: 'Departure & Arrival', value: 'departure,arrival' },
      { label: 'All POIs', value: '' },
      { label: 'Departure Only', value: 'departure' },
      { label: 'Arrival Only', value: 'arrival' },
      { label: 'Waypoints Only', value: 'waypoint' },
      { label: 'Alternates Only', value: 'alternate' },
    ]);
  });

  it('requests POI ETAs with default, empty, and helper filters', async () => {
    respond(poiPayload);
    await getPOIETAs();
    expect(getMock).toHaveBeenLastCalledWith('/api/pois/etas', {
      params: { category: 'departure,arrival' },
      signal: undefined,
    });

    respond({ ...poiPayload, pois: [], total: 0 });
    await getPOIETAs('');
    expect(getMock).toHaveBeenLastCalledWith('/api/pois/etas', {
      signal: undefined,
    });

    const signal = new AbortController().signal;
    respond(poiPayload);
    await getSatelliteETAs(signal);
    expect(getMock).toHaveBeenLastCalledWith('/api/pois/etas', {
      params: { category: 'satellite' },
      signal,
    });

    respond(poiPayload);
    await getMissionEventETAs(signal);
    expect(getMock).toHaveBeenLastCalledWith('/api/pois/etas', {
      params: { category: 'mission-event' },
      signal,
    });
  });

  it('rejects invalid POI ETA contracts and forbidden management id', async () => {
    for (const bad of [
      { ...poiPayload, total: 2 },
      { ...poiPayload, timestamp: '2026-08-29T12:34:56' },
      { ...poiPayload, pois: [{ ...poi, id: 'management-id' }] },
      { ...poiPayload, pois: [{ ...poi, eta_type: 'actual' }] },
      { ...poiPayload, pois: [{ ...poi, distance_meters: -1 }] },
      { ...poiPayload, pois: [{ ...poi, bearing_degrees: 361 }] },
      { ...poiPayload, pois: [{ ...poi, projected_latitude: 39 }] },
      { ...poiPayload, pois: [{ ...poi, projected_route_progress: 101 }] },
      { ...poiPayload, pois: [{ ...poi, route_aware_status: 'missed' }] },
    ]) {
      respond(bad);
      await expect(getPOIETAs()).rejects.toMatchObject({
        code: 'invalid_overview_data',
        source: 'poi-etas',
      });
    }
  });

  it('requests and validates route coordinates', async () => {
    const signal = new AbortController().signal;
    respond(routePayload);

    await expect(getRouteCoordinates('west', signal)).resolves.toEqual(
      routePayload
    );
    expect(getMock).toHaveBeenCalledWith('/api/route/coordinates/west', {
      signal,
    });

    respond({ ...routePayload, route_name: 'Westbound', revision_at: null });
    await expect(getRouteCoordinates('east')).resolves.toMatchObject({
      route_name: 'Westbound',
    });
    expect(getMock).toHaveBeenLastCalledWith('/api/route/coordinates/east', {
      signal: undefined,
    });
  });

  it('rejects invalid route coordinate contracts', async () => {
    for (const bad of [
      { ...routePayload, total: 2 },
      { ...routePayload, route_name: 123 },
      { ...routePayload, generated_at: '2026-08-29T12:34:56' },
      {
        ...routePayload,
        coordinates: [{ ...routePayload.coordinates[0], latitude: -91 }],
      },
      {
        ...routePayload,
        coordinates: [{ ...routePayload.coordinates[0], x: 1 }],
      },
    ]) {
      respond(bad);
      await expect(getRouteCoordinates('west')).rejects.toMatchObject({
        source: 'route-coordinates',
      });
    }
  });

  it('requests and validates active X-link overlays', async () => {
    const signal = new AbortController().signal;
    respond(activeXLinkPayload);

    await expect(getActiveXLink('warning', signal)).resolves.toEqual(
      activeXLinkPayload
    );

    expect(getMock).toHaveBeenCalledWith('/api/active-x-link', {
      params: { state: 'warning' },
      signal,
    });
  });

  it('rejects malformed active X-link and handoff data', async () => {
    for (const bad of [
      { ...activeXLinkPayload, total: 2 },
      { ...activeXLinkPayload, handoff: null },
      { ...activeXLinkPayload, state: 'alert' },
      { ...activeXLinkPayload, color: 'red' },
      { ...activeXLinkPayload, relative_azimuth_degrees: 361 },
      { ...activeXLinkPayload, observed_at: '2026-08-29T12:34:56' },
      {
        ...activeXLinkPayload,
        coordinates: [{ ...coordinate, point: 'ground' }],
      },
      {
        ...activeXLinkPayload,
        links: [
          {
            ...activeXLinkPayload.links[0],
            coordinates: [{ ...coordinate, extra: true }],
          },
        ],
      },
      {
        ...activeXLinkPayload,
        handoff: { ...handoff, phase: 'pending' },
      },
      {
        ...activeXLinkPayload,
        handoff: { ...handoff, transition_progress_percent: -1 },
      },
    ]) {
      respond(bad);
      await expect(getActiveXLink('normal')).rejects.toMatchObject({
        source: 'active-x-link',
      });
    }
  });
});
