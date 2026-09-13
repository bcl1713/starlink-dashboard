import { describe, expect, it } from 'vitest';
import { globePosition } from './globe-coordinates';
import {
  projectAircraftScenePosition,
  SCENE_EARTH_RADIUS,
  WGS84_SEMI_MAJOR_AXIS_METERS,
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
});
