import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getActiveXLink } from './monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56Z';
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
const payload = {
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

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

describe('active X-link overview service', () => {
  it('requests exact state params and parses populated and empty filtered states', async () => {
    const signal = new AbortController().signal;
    respond(payload);

    await expect(getActiveXLink('warning', signal)).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/api/active-x-link', {
      params: { state: 'warning' },
      signal,
    });

    const empty = {
      ...payload,
      coordinates: [],
      links: [],
      total: 0,
      state: 'warning',
      color: 'yellow',
      relative_azimuth_degrees: 0,
      in_forbidden_window: true,
    };
    respond(empty);
    await expect(getActiveXLink('normal')).resolves.toEqual(empty);
  });

  it('parses handoff phase variants and nullable top-level state fields', async () => {
    const variants = [
      { ...payload, handoff: { ...handoff, phase: 'in_handoff_zone' } },
      { ...payload, handoff: { ...handoff, phase: 'committed' } },
      {
        ...payload,
        satellite_id: null,
        state: null,
        color: null,
        relative_azimuth_degrees: null,
        in_forbidden_window: null,
        observed_at: '2026-08-29T12:30:00+00:00',
      },
    ];

    for (const variant of variants) {
      respond(variant);
      await expect(getActiveXLink('normal')).resolves.toEqual(variant);
    }
  });

  it('rejects malformed nested coordinate, link, and handoff data', async () => {
    const invalid = [
      { ...payload, total: 2 },
      { ...payload, generated_at: '2026-08-29T12:34:56' },
      { ...payload, handoff: null },
      { ...payload, state: 'alert' },
      { ...payload, color: 'red' },
      { ...payload, relative_azimuth_degrees: 361 },
      { ...payload, observed_at: '2026-08-29T12:34:56' },
      { ...payload, extra: true },
      { ...payload, coordinates: [{ ...coordinate, point: 'ground' }] },
      { ...payload, coordinates: [{ ...coordinate, sequence: -1 }] },
      { ...payload, coordinates: [{ ...coordinate, latitude: 91 }] },
      { ...payload, coordinates: [{ ...coordinate, observed_at: 'naive' }] },
      {
        ...payload,
        links: [
          {
            ...payload.links[0],
            coordinates: [{ ...coordinate, extra: true }],
          },
        ],
      },
      { ...payload, handoff: { ...handoff, phase: 'pending' } },
      { ...payload, handoff: { ...handoff, radius_meters: -1 } },
      {
        ...payload,
        handoff: { ...handoff, distance_to_transition_meters: -1 },
      },
      { ...payload, handoff: { ...handoff, route_progress_percent: 101 } },
      { ...payload, handoff: { ...handoff, transition_progress_percent: -1 } },
      { ...payload, handoff: { ...handoff, extra: true } },
    ];

    for (const bad of invalid) {
      respond(bad);
      await expect(getActiveXLink('normal')).rejects.toMatchObject({
        source: 'active-x-link',
      });
    }
  });
});
