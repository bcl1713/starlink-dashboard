import { globePosition } from './globe-coordinates';
import type { GlobeCoordinate } from './globe-route';

export function projectRoutePoints(
  points: readonly GlobeCoordinate[],
  radius: number
): [number, number, number][] {
  return points.map((point) =>
    globePosition(point.latitude, point.longitude, radius)
  );
}
