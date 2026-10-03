import { globePosition } from './globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';
import type { GlobeCoordinate } from './globe-route';
import type { FlowPoint } from './overview-animated-flow-line-rendering';
import {
  SCENE_EARTH_RADIUS,
  type AircraftScenePosition,
} from './x-band-active-link-projection';

const SEGMENTS = 128;
const CLEARANCE_TOLERANCE = 1e-7;

function validCoordinate(coordinate: GlobeCoordinate): boolean {
  return (
    Number.isFinite(coordinate.latitude) &&
    Math.abs(coordinate.latitude) <= 90 &&
    Number.isFinite(coordinate.longitude) &&
    Math.abs(coordinate.longitude) <= 180
  );
}

function dot(left: FlowPoint, right: FlowPoint): number {
  return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

function normalize(point: FlowPoint): FlowPoint {
  const radius = Math.hypot(...point);
  return [point[0] / radius, point[1] / radius, point[2] / radius];
}

function interpolateDirection(
  start: FlowPoint,
  end: FlowPoint,
  t: number
): FlowPoint {
  const cosine = Math.max(-1, Math.min(1, dot(start, end)));
  if (cosine > 0.9995) {
    return normalize([
      start[0] * (1 - t) + end[0] * t,
      start[1] * (1 - t) + end[1] * t,
      start[2] * (1 - t) + end[2] * t,
    ]);
  }
  const angle = Math.acos(cosine);
  const denominator = Math.sin(angle);
  const startWeight = Math.sin((1 - t) * angle) / denominator;
  const endWeight = Math.sin(t * angle) / denominator;
  return normalize([
    start[0] * startWeight + end[0] * endWeight,
    start[1] * startWeight + end[1] * endWeight,
    start[2] * startWeight + end[2] * endWeight,
  ]);
}

function perpendicularMidpoint(start: FlowPoint): FlowPoint {
  // Project the least-aligned axis onto the plane perpendicular to start.
  // Strict comparisons give ties a stable X, Y, Z priority.
  let axis = 0;
  if (Math.abs(start[1]) < Math.abs(start[axis])) axis = 1;
  if (Math.abs(start[2]) < Math.abs(start[axis])) axis = 2;
  const component = start[axis];
  return normalize([
    (axis === 0 ? 1 : 0) - component * start[0],
    (axis === 1 ? 1 : 0) - component * start[1],
    (axis === 2 ? 1 : 0) - component * start[2],
  ]);
}

function segmentClearsEarth(start: FlowPoint, end: FlowPoint): boolean {
  const delta: FlowPoint = [
    end[0] - start[0],
    end[1] - start[1],
    end[2] - start[2],
  ];
  const lengthSquared = dot(delta, delta);
  const t =
    lengthSquared === 0
      ? 0
      : Math.max(0, Math.min(1, -dot(start, delta) / lengthSquared));
  const radius = Math.hypot(
    start[0] + t * delta[0],
    start[1] + t * delta[1],
    start[2] + t * delta[2]
  );
  return (
    Number.isFinite(radius) &&
    radius >= SCENE_EARTH_RADIUS - CLEARANCE_TOLERANCE
  );
}

/** One bounded polyline for both the measured traffic line and particle path. */
export function projectTrafficArc(
  aircraft: AircraftScenePosition | null,
  pop: GlobeCoordinate | null
): FlowPoint[] {
  if (
    !aircraft ||
    !pop ||
    !validCoordinate(aircraft) ||
    !validCoordinate(pop) ||
    !Number.isFinite(aircraft.altitudeFeet) ||
    !aircraft.position.every(Number.isFinite)
  ) {
    return [];
  }

  const startRadius = Math.hypot(...aircraft.position);
  // Allow only floating-point roundoff in a valid sea-level projection.
  if (
    !Number.isFinite(startRadius) ||
    startRadius < SCENE_EARTH_RADIUS - 4 * Number.EPSILON
  ) {
    return [];
  }
  const end = globePosition(pop.latitude, pop.longitude, ROUTE_OVERLAY_RADIUS);
  const endRadius = Math.hypot(...end);
  if (!end.every(Number.isFinite) || !Number.isFinite(endRadius)) return [];

  const startDirection = normalize(aircraft.position);
  const endDirection = normalize(end);
  const cosine = Math.max(-1, Math.min(1, dot(startDirection, endDirection)));
  const angle = Math.acos(cosine);
  const height = Math.max(0.04, Math.min(0.6, 0.6 * Math.sin(angle / 2)));
  const midpoint =
    cosine < -0.9995 ? perpendicularMidpoint(startDirection) : null;
  const points: FlowPoint[] = [aircraft.position];

  for (let index = 1; index < SEGMENTS; index++) {
    const t = index / SEGMENTS;
    const direction = midpoint
      ? t <= 0.5
        ? interpolateDirection(startDirection, midpoint, t * 2)
        : interpolateDirection(midpoint, endDirection, t * 2 - 1)
      : interpolateDirection(startDirection, endDirection, t);
    const radius =
      startRadius * (1 - t) + endRadius * t + height * Math.sin(Math.PI * t);
    points.push([
      direction[0] * radius,
      direction[1] * radius,
      direction[2] * radius,
    ]);
  }
  points.push(end);

  // Safe vertices alone do not guarantee safe chords. Fail closed on any
  // nonfinite point or segment whose analytic closest point is inside Earth.
  for (let index = 1; index < points.length; index++) {
    if (
      !points[index].every(Number.isFinite) ||
      !segmentClearsEarth(points[index - 1], points[index])
    ) {
      return [];
    }
  }
  return points;
}
