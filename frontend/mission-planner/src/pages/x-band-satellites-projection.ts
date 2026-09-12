export interface ConfiguredXBandSatellite {
  satelliteId: string;
  latitude: 0;
  longitude: number;
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
