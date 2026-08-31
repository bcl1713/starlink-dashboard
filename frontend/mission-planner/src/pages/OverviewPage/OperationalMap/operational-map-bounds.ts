import type { LatLngBoundsExpression } from 'leaflet';

import type { OperationalFeature } from './operational-map-types';

interface BoundsPoint {
  readonly latitude: number;
  readonly longitude: number;
}

export function buildFeatureBounds(
  features: readonly OperationalFeature[]
): LatLngBoundsExpression | null {
  const points: BoundsPoint[] = features.flatMap((feature) =>
    feature.geometry.type === 'point'
      ? [
          {
            latitude: feature.geometry.latitude,
            longitude: feature.geometry.longitude,
          },
        ]
      : (feature.geometry.sourcePoints ?? feature.geometry.points).map(
          (point) => ({
            latitude: point.latitude,
            longitude: point.longitude,
          })
        )
  );
  const valid = points.filter((point) =>
    finiteGeographic(point.latitude, point.longitude)
  );
  if (valid.length === 0) return null;
  const latitudes = valid.map((point) => point.latitude);
  const unwrapped = unwrapLongitudes(valid.map((point) => point.longitude));
  return [
    [Math.min(...latitudes), Math.min(...unwrapped)],
    [Math.max(...latitudes), Math.max(...unwrapped)],
  ];
}

function unwrapLongitudes(longitudes: readonly number[]): readonly number[] {
  const normalized = [
    ...new Set(longitudes.map((value) => (value + 360) % 360)),
  ].sort((left, right) => left - right);
  if (normalized.length <= 1) return longitudes;
  let intervalStart = normalized[0];
  let largestGap = -1;
  for (let index = 0; index < normalized.length; index += 1) {
    const current = normalized[index];
    const next =
      normalized[(index + 1) % normalized.length] +
      (index === normalized.length - 1 ? 360 : 0);
    const gap = next - current;
    if (gap > largestGap) {
      largestGap = gap;
      intervalStart = next % 360;
    }
  }
  return longitudes.map((longitude) => {
    let value = (longitude + 360) % 360;
    if (value < intervalStart) value += 360;
    return value;
  });
}

export function finiteGeographic(latitude: number, longitude: number): boolean {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}
