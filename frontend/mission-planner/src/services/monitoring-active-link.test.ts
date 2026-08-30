import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getActiveXLink } from './monitoring';
import {
  activeXLinkPayload,
  setAt,
  withResponse,
  xLinkHandoff,
} from './monitoring-test-fixtures';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
}

async function expectActiveInvalid(payload: unknown) {
  respond(payload);
  await expect(getActiveXLink('normal')).rejects.toMatchObject({
    source: 'active-x-link',
  });
}

describe('active X-link overview service', () => {
  it('requests exact state params and parses populated and empty filtered states', async () => {
    const signal = new AbortController().signal;
    respond(activeXLinkPayload);
    await expect(getActiveXLink('warning', signal)).resolves.toEqual(
      activeXLinkPayload
    );
    expect(getMock).toHaveBeenCalledWith('/api/active-x-link', {
      params: { state: 'warning' },
      signal,
    });

    const empty = {
      ...activeXLinkPayload,
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

  it('parses link enums, handoff phases, nullables, and observed timestamps', async () => {
    const variants = [
      setAt(activeXLinkPayload, ['coordinates', 0, 'state'], 'warning'),
      setAt(activeXLinkPayload, ['coordinates', 0, 'color'], 'yellow'),
      setAt(activeXLinkPayload, ['coordinates', 0, 'point'], 'satellite'),
      setAt(activeXLinkPayload, ['links', 0, 'state'], 'warning'),
      setAt(activeXLinkPayload, ['links', 0, 'color'], 'yellow'),
      {
        ...activeXLinkPayload,
        handoff: { ...xLinkHandoff, phase: 'in_handoff_zone' },
      },
      {
        ...activeXLinkPayload,
        handoff: { ...xLinkHandoff, phase: 'committed' },
      },
      {
        ...activeXLinkPayload,
        satellite_id: null,
        pending_satellite_id: null,
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

  it('rejects malformed coordinate, link, handoff, and top-level data', async () => {
    const invalid = [
      setAt(activeXLinkPayload, ['total'], -1),
      setAt(activeXLinkPayload, ['total'], 2),
      setAt(activeXLinkPayload, ['generated_at'], '2026-08-29T12:34:56'),
      setAt(activeXLinkPayload, ['handoff'], null),
      setAt(activeXLinkPayload, ['state'], 'alert'),
      setAt(activeXLinkPayload, ['color'], 'red'),
      setAt(activeXLinkPayload, ['relative_azimuth_degrees'], -1),
      setAt(activeXLinkPayload, ['relative_azimuth_degrees'], 361),
      setAt(activeXLinkPayload, ['relative_azimuth_degrees'], Infinity),
      setAt(activeXLinkPayload, ['in_forbidden_window'], 'false'),
      setAt(activeXLinkPayload, ['observed_at'], '2026-08-29T12:34:56'),
      setAt(activeXLinkPayload, ['extra'], true),
      setAt(activeXLinkPayload, ['coordinates', 0, 'state'], 'alert'),
      setAt(activeXLinkPayload, ['coordinates', 0, 'color'], 'red'),
      setAt(
        activeXLinkPayload,
        ['coordinates', 0, 'relative_azimuth_degrees'],
        -1
      ),
      setAt(
        activeXLinkPayload,
        ['coordinates', 0, 'relative_azimuth_degrees'],
        361
      ),
      setAt(
        activeXLinkPayload,
        ['coordinates', 0, 'relative_azimuth_degrees'],
        Infinity
      ),
      setAt(
        activeXLinkPayload,
        ['coordinates', 0, 'in_forbidden_window'],
        'no'
      ),
      setAt(activeXLinkPayload, ['coordinates', 0, 'point'], 'ground'),
      setAt(activeXLinkPayload, ['coordinates', 0, 'sequence'], -1),
      setAt(activeXLinkPayload, ['coordinates', 0, 'sequence'], 1.5),
      setAt(activeXLinkPayload, ['coordinates', 0, 'latitude'], 91),
      setAt(activeXLinkPayload, ['coordinates', 0, 'latitude'], NaN),
      setAt(activeXLinkPayload, ['coordinates', 0, 'longitude'], -181),
      setAt(activeXLinkPayload, ['coordinates', 0, 'longitude'], Infinity),
      setAt(activeXLinkPayload, ['coordinates', 0, 'observed_at'], 'naive'),
      setAt(activeXLinkPayload, ['coordinates', 0, 'extra'], true),
      setAt(activeXLinkPayload, ['links', 0, 'state'], 'alert'),
      setAt(activeXLinkPayload, ['links', 0, 'color'], 'red'),
      setAt(activeXLinkPayload, ['links', 0, 'relative_azimuth_degrees'], -1),
      setAt(activeXLinkPayload, ['links', 0, 'relative_azimuth_degrees'], 361),
      setAt(
        activeXLinkPayload,
        ['links', 0, 'relative_azimuth_degrees'],
        Infinity
      ),
      setAt(activeXLinkPayload, ['links', 0, 'in_forbidden_window'], 'no'),
      setAt(activeXLinkPayload, ['links', 0, 'extra'], true),
      setAt(activeXLinkPayload, ['links', 0, 'coordinates', 0, 'extra'], true),
      setAt(activeXLinkPayload, ['handoff', 'phase'], 'pending'),
      setAt(activeXLinkPayload, ['handoff', 'transition_id'], 1),
      setAt(activeXLinkPayload, ['handoff', 'transition_satellite_id'], 1),
      setAt(activeXLinkPayload, ['handoff', 'radius_meters'], -1),
      setAt(activeXLinkPayload, ['handoff', 'radius_meters'], Infinity),
      setAt(
        activeXLinkPayload,
        ['handoff', 'distance_to_transition_meters'],
        -1
      ),
      setAt(
        activeXLinkPayload,
        ['handoff', 'distance_to_transition_meters'],
        Infinity
      ),
      setAt(activeXLinkPayload, ['handoff', 'in_handoff_zone'], 'false'),
      setAt(activeXLinkPayload, ['handoff', 'route_progress_percent'], 101),
      setAt(activeXLinkPayload, ['handoff', 'transition_progress_percent'], -1),
      setAt(activeXLinkPayload, ['handoff', 'extra'], true),
    ];

    for (const bad of invalid) await expectActiveInvalid(bad);
  });
});
