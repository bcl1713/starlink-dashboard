import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import { EARTH_RADIUS_KM, type PropagationResult } from './types';

export function distance(a: FlowPoint, b: FlowPoint): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}
export function pointAt(snapshot: PropagationResult, index: number): FlowPoint {
  return [
    snapshot.positionsKm[index * 3],
    snapshot.positionsKm[index * 3 + 1],
    snapshot.positionsKm[index * 3 + 2],
  ];
}
export function physicalEndpoint(point: FlowPoint | null): point is FlowPoint {
  return Boolean(
    point &&
      point.every(Number.isFinite) &&
      Math.hypot(...point) >= EARTH_RADIUS_KM - 1e-7
  );
}
export function segmentClearanceKm(start: FlowPoint, end: FlowPoint): number {
  const d = [end[0] - start[0], end[1] - start[1], end[2] - start[2]];
  const squared = d.reduce((sum, v) => sum + v * v, 0);
  const t = squared
    ? Math.max(
        0,
        Math.min(1, -start.reduce((sum, v, i) => sum + v * d[i], 0) / squared)
      )
    : 0;
  return Math.hypot(...start.map((v, i) => v + t * d[i])) - EARTH_RADIUS_KM;
}
export function elevationDegrees(
  endpoint: FlowPoint,
  spacecraft: FlowPoint
): number {
  const d = spacecraft.map((v, i) => v - endpoint[i]);
  const norm = Math.hypot(...d) * Math.hypot(...endpoint);
  if (!norm) return -90;
  return (
    (Math.asin(
      Math.max(
        -1,
        Math.min(1, d.reduce((sum, v, i) => sum + v * endpoint[i], 0) / norm)
      )
    ) *
      180) /
    Math.PI
  );
}
export const aboveMinimum = (elevation: number) => elevation > 10 + 1e-9;
