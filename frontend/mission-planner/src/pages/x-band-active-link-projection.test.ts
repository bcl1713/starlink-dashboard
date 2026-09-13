import { describe, expect, it } from 'vitest';
import { globePosition } from './globe-coordinates';
import { projectConfiguredXBandSatellite3d } from './x-band-satellites-projection';
import {
  calculateConfiguredXBandLookAngles,
  projectAircraftScenePosition,
  SCENE_EARTH_RADIUS,
  WGS84_SEMI_MAJOR_AXIS_METERS,
  projectConfiguredXBandActiveLink,
  projectActiveConfiguredXBandSatelliteId,
} from './x-band-active-link-projection';

describe('projectAircraftScenePosition', () => {
  it('projects valid aircraft latitude, longitude, and MSL altitude into the scene', () => {
    const altitudeFeet = 35_000;
    const altitudeMeters = altitudeFeet * 0.3048;
    const sceneRadius =
      SCENE_EARTH_RADIUS * (1 + altitudeMeters / WGS84_SEMI_MAJOR_AXIS_METERS);
    expect(
      projectAircraftScenePosition({
        position: {
          latitude: 12,
          longitude: -60,
          altitude: altitudeFeet,
        },
      })
    ).toEqual({
      latitude: 12,
      longitude: -60,
      altitudeFeet,
      position: globePosition(12, -60, sceneRadius),
    });
  });
  it('returns null when aircraft altitude is unavailable', () => {
    expect(
      projectAircraftScenePosition({
        position: {
          latitude: 12,
          longitude: -60,
        },
      })
    ).toBeNull();
  });
  it('returns null when aircraft altitude is not finite', () => {
    expect(
      projectAircraftScenePosition({
        position: {
          latitude: 12,
          longitude: -60,
          altitude: Number.NaN,
        },
      })
    ).toBeNull();
  });
  it('assembles an aircraft-to-selected-configured-satellite 3D link', () => {
    const status = {
      position: {
        latitude: 12,
        longitude: -60,
        altitude: 35_000,
      },
    };
    const satellites = [
      {
        satellite_id: 'X-Atlantic',
        transport: 'X',
        longitude: -60,
      },
    ];
    const aircraft = projectAircraftScenePosition(status);
    const satellite = projectConfiguredXBandSatellite3d(satellites).at(0);
    expect(
      projectConfiguredXBandActiveLink(status, satellites, 'X-Atlantic')
    ).toEqual({
      satelliteId: 'X-Atlantic',
      aircraft,
      satellite,
      points: [aircraft?.position, satellite?.position],
    });
  });
  it('calculates azimuth and elevation from the shared 3D link geometry', () => {
    const link = projectConfiguredXBandActiveLink(
      {
        position: {
          latitude: 30,
          longitude: 0,
          altitude: 35_000,
        },
      },
      [
        {
          satellite_id: 'X-Prime',
          transport: 'X',
          longitude: 0,
        },
      ],
      'X-Prime'
    );
    if (!link) {
      throw new Error('Expected a valid configured X-band link.');
    }
    const lookAngles = calculateConfiguredXBandLookAngles(link);
    expect(lookAngles.azimuthDegrees).toBeCloseTo(180, 6);
    expect(lookAngles.elevationDegrees).toBeCloseTo(55.02158, 5);
  });
  it('returns no link when selected satellite configuration is unavailable or invalid', () => {
    const status = {
      position: {
        latitude: 12,
        longitude: -60,
        altitude: 35_000,
      },
    };
    expect(
      projectConfiguredXBandActiveLink(status, undefined, 'X-Atlantic')
    ).toBeNull();
    expect(
      projectConfiguredXBandActiveLink(
        status,
        [
          {
            satellite_id: 'X-Atlantic',
            transport: 'X',
            longitude: 181,
          },
        ],
        'X-Atlantic'
      )
    ).toBeNull();
  });
  it('accepts only a nonblank active configured satellite ID', () => {
    expect(
      projectActiveConfiguredXBandSatelliteId({
        satellite_id: 'X-Atlantic',
      })
    ).toBe('X-Atlantic');
    expect(
      projectActiveConfiguredXBandSatelliteId({
        satellite_id: '   ',
      })
    ).toBeNull();
    expect(
      projectActiveConfiguredXBandSatelliteId({
        satellite_id: null,
      })
    ).toBeNull();
  });
});
