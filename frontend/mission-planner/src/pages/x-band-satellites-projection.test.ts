import { describe, expect, it } from 'vitest';
import { projectConfiguredXBandSatellites } from './x-band-satellites-projection';

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

  it('excludes non-X-band and invalid configured records', () => {
    expect(
      projectConfiguredXBandSatellites([
        {
          satelliate_id: 'Ka-1',
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
