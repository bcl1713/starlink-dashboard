import { globePosition } from './globe-coordinates';
export interface ConfiguredXBandSatellite {
  satelliteId: string;
  latitude: 0;
  longitude: number;
}
// The scene Earth radius is 2; 13.234 represents configured GEO placement at
// about 6.617 Earth radii. It is illustrative configuration, not live   telemetry.
export const CONFIGURED_GEO_SCENE_RADIUS = 13.234;
export interface ConfiguredXBandSatellite3d extends ConfiguredXBandSatellite {
  position: [number, number, number];
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
export function projectConfiguredXBandSatellites(
  satellites: unknown
): ConfiguredXBandSatellite[] {
  if (!Array.isArray(satellites)) {
    return [];
  }
  return satellites.flatMap((satellite) => {
    if (
      !isRecord(satellite) ||
      typeof satellite.satellite_id !== 'string' ||
      satellite.satellite_id.trim().length === 0 ||
      satellite.transport !== 'X' ||
      typeof satellite.longitude !== 'number' ||
      !Number.isFinite(satellite.longitude) ||
      satellite.longitude < -180 ||
      satellite.longitude > 180
    ) {
      return [];
    }
    return [
      {
        satelliteId: satellite.satellite_id,
        latitude: 0,
        longitude: satellite.longitude,
      },
    ];
  });
}
export function projectConfiguredXBandSatellite3d(
  satellites: unknown
): ConfiguredXBandSatellite3d[] {
  return projectConfiguredXBandSatellites(satellites).map((satellite) => ({
    ...satellite,
    position: globePosition(
      satellite.latitude,
      satellite.longitude,
      CONFIGURED_GEO_SCENE_RADIUS
    ),
  }));
}
