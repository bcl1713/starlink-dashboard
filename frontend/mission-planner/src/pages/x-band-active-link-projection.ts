import { globePosition } from './globe-coordinates';

export const SCENE_EARTH_RADIUS = 2;
export const WGS84_SEMI_MAJOR_AXIS_METERS = 6_378_137;

export interface AircraftScenePosition {
  latitude: number;
  longitude: number;
  altitudeFeet: number;
  position: [number, number, number];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function projectAircraftScenePosition(
  status: unknown
): AircraftScenePosition | null {
  if (!isRecord(status) || !isRecord(status.position)) {
    return null;
  }
  const { latitude, longitude, altitude } = status.position;
  if (
    typeof latitude !== 'number' ||
    !Number.isFinite(latitude) ||
    latitude < -90 ||
    latitude > 90 ||
    typeof longitude !== 'number' ||
    !Number.isFinite(longitude) ||
    longitude < -180 ||
    longitude > 180 ||
    typeof altitude !== 'number' ||
    !Number.isFinite(altitude)
  ) {
    return null;
  }

  // /api/status reports aircraft altitude in feet MSL. Convert that telemetry
  // datum into the illustrative Earth-radius-2 scene used for link analysis.
  const altitudeMeters = altitude * 0.3048;
  const sceneRadius =
    SCENE_EARTH_RADIUS * (1 + altitudeMeters / WGS84_SEMI_MAJOR_AXIS_METERS);
  return {
    latitude,
    longitude,
    altitudeFeet: altitude,
    position: globePosition(latitude, longitude, sceneRadius),
  };
}
