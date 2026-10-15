import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import type { PropagationResult } from './types';
export function circle(degrees: number, radius = 7000): FlowPoint {
  const a = (degrees * Math.PI) / 180;
  return [radius * Math.cos(a), radius * Math.sin(a), 0];
}
export function snapshot(
  points: readonly FlowPoint[],
  ids = points.map((_, i) => String(i + 1))
): PropagationResult {
  return {
    utcMs: 0,
    ids,
    positionsKm: new Float64Array(points.flat()),
    valid: new Uint8Array(points.length).fill(1),
  };
}
