import { globePosition } from './globe-coordinates';
import {
  projectConfiguredXBandSatellite3d,
  type ConfiguredXBandSatellite3d,
} from './x-band-satellites-projection';
export const SCENE_EARTH_RADIUS = 2;
export const WGS84_SEMI_MAJOR_AXIS_METERS = 6_378_137;
export interface ConfiguredXBandLookAngles {
  azimuthDegrees: number;
  elevationDegrees: number;
}
export interface AircraftScenePosition {
  latitude: number;
  longitude: number;
  altitudeFeet: number;
  position: [number, number, number];
}
export interface ConfiguredXBandActiveLink {
  satelliteId: string;
  aircraft: AircraftScenePosition;
  satellite: ConfiguredXBandSatellite3d;
  points: [[number, number, number], [number, number, number]];
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
export function projectActiveConfiguredXBandSatelliteId(
  activeLink: unknown
): string | null {
  if (
    !isRecord(activeLink) ||
    typeof activeLink.satellite_id !== 'string' ||
    activeLink.satellite_id.trim().length === 0
  ) {
    return null;
  }
  return activeLink.satellite_id;
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
/**
 * Builds an analytical 3D link from aircraft telemetry to one selected
 * configured X-band satellite. The satellite placement is configuration, not
 * live orbital ephemeris or telemetry.
 */
export function projectConfiguredXBandActiveLink(
  status: unknown,
  satellites: unknown,
  activeSatelliteId: string
): ConfiguredXBandActiveLink | null {
  const aircraft = projectAircraftScenePosition(status);
  const satellite = projectConfiguredXBandSatellite3d(satellites).find(
    (candidate) => candidate.satelliteId === activeSatelliteId
  );
  if (!aircraft || !satellite) {
    return null;
  }
  return {
    satelliteId: satellite.satelliteId,
    aircraft,
    satellite,
    points: [aircraft.position, satellite.position],
  };
}

function dot(
  left: [number, number, number],
  right: [number, number, number]
): number {
  return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

function subtract(
  left: [number, number, number],
  right: [number, number, number]
): [number, number, number] {
  return [left[0] - right[0], left[1] - right[1], left[2] - right[2]];
}

function magnitude(vector: [number, number, number]): number {
  return Math.hypot(vector[0], vector[1], vector[2]);
}

export function calculateConfiguredXBandLookAngles(
  link: ConfiguredXBandActiveLink
): ConfiguredXBandLookAngles {
  const latitudeRadians = (link.aircraft.latitude * Math.PI) / 180;
  const longitudeRadians = (link.aircraft.longitude * Math.PI) / 180;
  const lineOfSight = subtract(link.satellite.position, link.aircraft.position);
  const lineOfSightMagnitude = magnitude(lineOfSight);
  const up = globePosition(link.aircraft.latitude, link.aircraft.longitude, 1);
  const east: [number, number, number] = [
    -Math.sin(longitudeRadians),
    0,
    -Math.cos(longitudeRadians),
  ];
  const north: [number, number, number] = [
    -Math.sin(latitudeRadians) * Math.cos(longitudeRadians),
    Math.cos(latitudeRadians),
    Math.sin(latitudeRadians) * Math.sin(longitudeRadians),
  ];
  const elevationDegrees =
    (Math.asin(dot(lineOfSight, up) / lineOfSightMagnitude) * 180) / Math.PI;
  const azimuthDegrees =
    ((Math.atan2(dot(lineOfSight, east), dot(lineOfSight, north)) * 180) /
      Math.PI +
      360) %
    360;
  return { azimuthDegrees, elevationDegrees };
}
