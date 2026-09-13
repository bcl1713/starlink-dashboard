import { describe, expect, it } from 'vitest';
import {
  projectConfiguredXBandSatellites,
  projectConfiguredXBandSatellite3d,
  CONFIGURED_GEO_SCENE_RADIUS,
} from './x-band-satellites-projection';
import { globePosition } from './globe-coordinates';

describe('projectConfiguredXBandSatellite3d', () => {
  it('projects valid configured X-band record', () => {
    expect(
      projectConfiguredXBandSatellite3d([
        {
          satellite_id: 'X-Atlantic',
          transport: 'X',
          longitude: -60,
          slot: 'Atlantic',
          color: '#FF6B6B',
        },
      ])
    ).toEqual([
      {
        satelliteID: 'X-Atlantic',
        latitude: 0,
        longitude: -60,
        position: globePosition(0, -60, CONFIGURED_GEO_SCENE_RADIUS),
      },
    ]);
    expect(CONFIGURED_GEO_SCENE_RADIUS).toBe(13.234);
  });
});

describe('projectConfiguredXBandSatellites', () => {
  it('projects valid configured X-band records at the equator', () => {
    expect(
      projectConfiguredXBandSatellites([
        {
          satellite_id: 'X-Atlantic',
          transport: 'X',
          longitude: -60,
          slot: 'Atlantic',
          color: '#FF6B6B',
        },
      ])
    ).toEqual([
      {
        satelliteId: 'X-Atlantic',
        latitude: 0,
        longitude: -60,
      },
    ]);
  });

  it('returns no markers when satellite data is unavailable', () => {
    expect(projectConfiguredXBandSatellites(undefined)).toEqual([]);
  });

  it('excludes an X-band record with a whitespace-only satellite ID', () => {
    expect(
      projectConfiguredXBandSatellites([
        {
          satellite_id: '   ',
          transport: 'X',
          longitude: -60,
        },
      ])
    ).toEqual([]);
  });

  it('excludes non-X-band and invalid configured records', () => {
    expect(
      projectConfiguredXBandSatellites([
        {
          satellite_id: 'Ka-1',
          transport: 'Ka',
          longitude: 10,
          slot: null,
          color: '#4CAF50',
        },
        {
          satellite_id: 'X-invalid',
          transport: 'X',
          longitude: 181,
          slot: null,
          color: '#FF6B6B',
        },
      ])
    ).toEqual([]);
  });
});
