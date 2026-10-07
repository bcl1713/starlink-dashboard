import { Matrix4, Quaternion, Vector3 } from 'three';
import { globePosition } from './globe-coordinates';
import { routeHemisphere } from './overview-route-hemisphere';
import type { CameraFrame, FrameInput } from './overview-camera-frame';
import type { GlobeCoordinate } from './globe-route';

function axes(direction: Vector3) {
  const orientation = new Quaternion().setFromRotationMatrix(
    new Matrix4().lookAt(direction, new Vector3(), new Vector3(0, 1, 0))
  );
  return {
    right: new Vector3(1, 0, 0).applyQuaternion(orientation),
    up: new Vector3(0, 1, 0).applyQuaternion(orientation),
  };
}

/** Test the destination pose rather than chasing a still-damped camera each poll.
 * Smaller margins than fitting give overview mode hysteresis at the edges.
 */
export function overviewAircraftInFrame({
  width,
  height,
  fov,
  safeRect,
  aircraft,
  frame,
}: Pick<FrameInput, 'width' | 'height' | 'fov' | 'safeRect'> & {
  aircraft: GlobeCoordinate;
  frame: CameraFrame;
}): boolean {
  if (
    !Number.isFinite(aircraft.latitude) ||
    !Number.isFinite(aircraft.longitude) ||
    !frame.direction
  )
    return false;
  const point = new Vector3(
    ...globePosition(aircraft.latitude, aircraft.longitude, 2.04)
  );
  const facing = point.clone().normalize().dot(frame.direction);
  if (facing < 0.3 || facing < 2.04 / frame.distance + 0.08) return false;
  const { right, up } = axes(frame.direction);
  const focal = height / (2 * Math.tan((fov * Math.PI) / 360));
  const depth = frame.distance - point.dot(frame.direction);
  const x = width / 2 + (focal * point.dot(right)) / depth - frame.offsetX;
  const y = height / 2 - (focal * point.dot(up)) / depth - frame.offsetY;
  const margin = Math.min(16, Math.min(safeRect.width, safeRect.height) * 0.05);
  return (
    x >= safeRect.x + margin &&
    x <= safeRect.x + safeRect.width - margin &&
    y >= safeRect.y + margin &&
    y <= safeRect.y + safeRect.height - margin
  );
}

/** Fit projected bounds, with latitude/longitude kept on the original globe. */
function fitPoints(
  input: FrameInput,
  points: Vector3[],
  maximum: number
): CameraFrame | null {
  const { width, height, fov, safeRect, aircraft } = input;
  const marker = aircraft
    ? new Vector3(...globePosition(aircraft.latitude, aircraft.longitude, 2.04))
    : null;
  const direction = routeHemisphere(marker ? [...points, marker] : points);
  if (!direction) return null;
  if (marker) {
    const unit = marker.clone().normalize();
    const angle = direction.angleTo(unit);
    // Reserve an interior position for the aircraft instead of grazing the limb.
    if (angle > Math.acos(0.45)) {
      const axis = direction.clone().cross(unit).normalize();
      direction.applyAxisAngle(axis, angle - Math.acos(0.45)).normalize();
    }
  }
  const { right, up } = axes(direction);
  const coordinates = [...points, ...(marker ? [marker] : [])].map((p) => ({
    x: p.dot(right),
    y: p.dot(up),
    z: p.dot(direction),
  }));
  if (coordinates.some((p) => p.z <= 0)) return null;
  let minimum = Math.max(3, ...coordinates.map((p) => 4.04 / p.z));
  if (marker)
    minimum = Math.max(
      minimum,
      2.04 / (marker.clone().normalize().dot(direction) - 0.12)
    );
  if (minimum > maximum) return null;
  const focal = height / (2 * Math.tan((fov * Math.PI) / 360));
  const margin = Math.min(32, Math.min(safeRect.width, safeRect.height) * 0.1);
  const availableX = Math.max(
    0.001,
    (safeRect.width - 2 * margin) / (1.05 * focal)
  );
  const availableY = Math.max(
    0.001,
    (safeRect.height - 2 * margin) / (1.05 * focal)
  );
  const bounds = (distance: number) => {
    let left = Infinity,
      right = -Infinity,
      bottom = Infinity,
      top = -Infinity;
    for (const p of coordinates) {
      const x = p.x / (distance - p.z),
        y = p.y / (distance - p.z);
      left = Math.min(left, x);
      right = Math.max(right, x);
      bottom = Math.min(bottom, y);
      top = Math.max(top, y);
    }
    return { left, right, bottom, top };
  };
  const fits = (distance: number) => {
    const b = bounds(distance);
    return b.right - b.left <= availableX && b.top - b.bottom <= availableY;
  };
  if (!fits(maximum)) return null;
  let maximumFit = maximum;
  for (let i = 0; i < 24; i++) {
    const middle = (minimum + maximumFit) / 2;
    if (fits(middle)) maximumFit = middle;
    else minimum = middle;
  }
  const b = bounds(maximumFit);
  return {
    direction,
    distance: maximumFit,
    offsetX:
      width / 2 +
      (focal * (b.left + b.right)) / 2 -
      safeRect.x -
      safeRect.width / 2,
    offsetY:
      height / 2 -
      (focal * (b.top + b.bottom)) / 2 -
      safeRect.y -
      safeRect.height / 2,
  };
}

/** Full-route fitting first; otherwise the largest contiguous useful context.
 * Context uses arc length, not waypoint count, with twice as much room ahead.
 */
export function overviewRouteFrame(input: FrameInput): CameraFrame {
  const points = input.route!.map((point) => new Vector3(...point));
  const aircraft =
    input.aircraft &&
    Number.isFinite(input.aircraft.latitude) &&
    Number.isFinite(input.aircraft.longitude)
      ? input.aircraft
      : null;
  const cleanInput = { ...input, aircraft };
  const fraction = Math.max(
    0.001,
    Math.min(input.safeRect.width, input.safeRect.height) /
      Math.max(1, input.height)
  );
  // Don't shrink a route-aware overview beyond a comfortably readable globe.
  const readableDistance = Math.min(
    28,
    2.2 / Math.sin(Math.atan(Math.tan((input.fov * Math.PI) / 360) * fraction))
  );
  const maximum = aircraft ? readableDistance : 28;
  const full = fitPoints(cleanInput, points, maximum);
  if (full) return { ...full, routeFit: 'complete' };

  const anchor = new Vector3(
    ...globePosition(
      aircraft?.latitude ??
        (Math.asin(points[0].y / points[0].length()) * 180) / Math.PI,
      aircraft?.longitude ??
        (Math.atan2(-points[0].z, points[0].x) * 180) / Math.PI,
      1
    )
  );
  const nearest = points.reduce(
    (best, point, index) =>
      point.clone().normalize().dot(anchor) >
      points[best].clone().normalize().dot(anchor)
        ? index
        : best,
    0
  );
  const distances = [0];
  for (let i = 1; i < points.length; i++)
    distances.push(distances[i - 1] + points[i - 1].angleTo(points[i]));
  const total = distances.at(-1)!;
  const pointAt = (distance: number) => {
    const i = Math.max(
      1,
      distances.findIndex((d) => d >= distance)
    );
    const span = distances[i] - distances[i - 1];
    const fraction = span ? (distance - distances[i - 1]) / span : 0;
    const a = points[i - 1],
      b = points[i];
    const angle = a.angleTo(b),
      sine = Math.sin(angle);
    return sine > 1e-8
      ? a
          .clone()
          .multiplyScalar(Math.sin((1 - fraction) * angle) / sine)
          .addScaledVector(b, Math.sin(fraction * angle) / sine)
      : a.clone();
  };
  const section = (length: number) => {
    const start = Math.max(
      0,
      Math.min(total - length, distances[nearest] - length / 3)
    );
    const end = Math.min(total, start + length);
    return [
      pointAt(start),
      ...points.filter((_, i) => distances[i] > start && distances[i] < end),
      pointAt(end),
    ];
  };
  let best = fitPoints(cleanInput, [points[nearest]], readableDistance);
  let low = 0,
    high = total;
  for (let i = 0; i < 16; i++) {
    const middle = (low + high) / 2;
    const frame = fitPoints(cleanInput, section(middle), readableDistance);
    if (frame) {
      low = middle;
      best = frame;
    } else high = middle;
  }
  // An off-route aircraft can have no containing hemisphere with the route.
  best ??= fitPoints(cleanInput, [anchor.clone().multiplyScalar(2.015)], 28);
  return {
    ...(best ?? {
      direction: anchor,
      distance: 28,
      offsetX: input.width / 2 - input.safeRect.x - input.safeRect.width / 2,
      offsetY: input.height / 2 - input.safeRect.y - input.safeRect.height / 2,
    }),
    routeFit: 'partial',
  };
}
