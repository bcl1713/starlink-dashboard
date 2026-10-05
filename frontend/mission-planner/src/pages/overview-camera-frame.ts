import { Matrix3, Matrix4, Quaternion, Triangle, Vector3 } from 'three';
import { globePosition } from './globe-coordinates';
import type { GlobeCoordinate } from './globe-route';
import type { OverviewSafeRect } from './overview-responsive-layout';
interface FrameInput {
  width: number;
  height: number;
  fov: number;
  safeRect: OverviewSafeRect;
  route?: readonly [number, number, number][];
  direction?: Vector3;
  centerGlobe?: boolean;
  followAircraft?: boolean;
}
interface CameraFrame {
  distance: number;
  offsetX: number;
  offsetY: number;
  direction?: Vector3;
  /** Partial means the orbit limit or hemisphere prevents a complete route fit. */
  routeFit?: 'complete' | 'partial';
}
/** Fit the unchanged radius-two globe into measured CSS space, with 10% margin. */
export function overviewCameraFrame({
  width,
  height,
  fov,
  safeRect,
  route,
  direction,
  centerGlobe = false,
  followAircraft = false,
}: FrameInput): CameraFrame {
  if (centerGlobe && direction && route && route.length > 1)
    return centeredRouteFrame({
      width,
      height,
      fov,
      safeRect,
      route,
      direction,
    });
  const fullHeight = Math.max(1, height),
    fullWidth = Math.max(1, width);
  const fraction = Math.max(
    0.001,
    Math.min(safeRect.height / fullHeight, safeRect.width / fullHeight)
  );
  const halfAngle = Math.atan(Math.tan((fov * Math.PI) / 360) * fraction);
  let distance = followAircraft ? 4.5 : 2.2 / Math.sin(halfAngle);
  if (
    direction &&
    route &&
    route.length >= 2 &&
    route.every((point) => point.every(Number.isFinite))
  ) {
    const orientation = new Quaternion().setFromRotationMatrix(
      new Matrix4().lookAt(direction, new Vector3(), new Vector3(0, 1, 0))
    );
    const right = new Vector3(1, 0, 0).applyQuaternion(orientation);
    const up = new Vector3(0, 1, 0).applyQuaternion(orientation);
    const tanY = Math.tan((fov * Math.PI) / 360);
    const availableX = Math.max(0.001, (tanY * safeRect.width) / fullHeight);
    const availableY = Math.max(0.001, (tanY * safeRect.height) / fullHeight);
    distance = Math.max(
      ...route.map((point) => {
        const p = new Vector3(...point);
        return Math.max(
          // Keep fitting all geometry even when some samples cannot be visible.
          p.dot(direction) > 0 ? 4.04 / p.dot(direction) : 28,
          p.dot(direction) +
            Math.max(
              (1.1 * Math.abs(p.dot(right))) / availableX,
              (1.1 * Math.abs(p.dot(up))) / availableY
            )
        );
      })
    );
  }
  return {
    distance: Math.min(28, Math.max(3, distance)),
    offsetX: centerGlobe ? 0 : fullWidth / 2 - safeRect.x - safeRect.width / 2,
    offsetY: centerGlobe
      ? 0
      : fullHeight / 2 - safeRect.y - safeRect.height / 2,
    direction,
    ...(route && direction && route.length > 1
      ? {
          routeFit:
            distance <= 28 &&
            route.every(
              (point) =>
                new Vector3(...point).dot(direction) * Math.max(3, distance) >=
                4.04
            )
              ? ('complete' as const)
              : ('partial' as const),
        }
      : {}),
  };
}

/** Find a containing hemisphere from route extremes, independent of sample density.
 * The closest point to the origin in their convex hull faces the smallest cap.
 * Fully correct a support of at most four points each step, avoiding slow segment
 * convergence near the horizon. A hull containing the origin has no hemisphere.
 */
function routeHemisphere(points: Vector3[], seed: Vector3): Vector3 {
  const directions = points.map((point) => point.clone().normalize());
  let support = [directions[0]];
  const center = support[0].clone();
  const origin = new Vector3();
  for (let iteration = 0; iteration < 256; iteration++) {
    const extreme = directions.reduce((worst, point) =>
      point.dot(center) < worst.dot(center) ? point : worst
    );
    if (center.lengthSq() - extreme.dot(center) < 1e-10) break;
    const vertices = [...support, extreme];
    if (vertices.length === 4) {
      const [a, b, c, d] = vertices.map((p) => p.clone());
      a.sub(d);
      b.sub(d);
      c.sub(d);
      const basis = new Matrix3().set(
        a.x,
        b.x,
        c.x,
        a.y,
        b.y,
        c.y,
        a.z,
        b.z,
        c.z
      );
      if (Math.abs(basis.determinant()) > 1e-12) {
        const weights = d.negate().applyMatrix3(basis.invert());
        if (
          Math.min(weights.x, weights.y, weights.z) >= -1e-10 &&
          weights.x + weights.y + weights.z <= 1 + 1e-10
        )
          return seed.clone().normalize();
      }
    }
    let closest = vertices[0].clone(),
      nextSupport = [vertices[0]];
    const consider = (point: Vector3, active: Vector3[]) => {
      if (point.lengthSq() < closest.lengthSq()) {
        closest = point;
        nextSupport = active;
      }
    };
    for (let i = 0; i < vertices.length; i++) {
      const a = vertices[i];
      consider(a.clone(), [a]);
      for (let j = 0; j < i; j++) {
        const b = vertices[j],
          edge = b.clone().sub(a);
        if (edge.lengthSq() > 1e-12) {
          const weight = Math.min(
            1,
            Math.max(0, -a.dot(edge) / edge.lengthSq())
          );
          consider(a.clone().addScaledVector(edge, weight), [a, b]);
        }
        for (let k = 0; k < j; k++) {
          const c = vertices[k];
          if (edge.clone().cross(c.clone().sub(a)).lengthSq() < 1e-16) continue;
          const triangle = new Triangle(a, b, c);
          const point = triangle.closestPointToPoint(origin, new Vector3());
          const weights = triangle.getBarycoord(point, new Vector3())!;
          consider(
            point,
            [a, b, c].filter((_, index) => weights.getComponent(index) > 1e-10)
          );
        }
      }
    }
    center.copy(closest);
    support = nextSupport;
    if (center.lengthSq() < 1e-8) return seed.clone().normalize();
  }
  const facing = center.normalize();
  return points.every((point) => point.dot(facing) * 28 >= 4.04)
    ? facing
    : seed.clone().normalize();
}

/** Rotate under a centered camera to fill the opening below the right cards. */
function centeredRouteFrame({
  width,
  height,
  fov,
  safeRect,
  route,
  direction,
}: FrameInput): CameraFrame {
  const points = route!.map((point) => new Vector3(...point));
  const facing = points.every((point) => point.dot(direction!) * 28 >= 4.04)
    ? direction!.clone().normalize()
    : routeHemisphere(points, direction!);
  const focal = height / (2 * Math.tan((fov * Math.PI) / 360));
  const limits = [
    (width / 2 - safeRect.x) / focal,
    (safeRect.x + safeRect.width - width / 2) / focal,
    (height / 2 - safeRect.y) / focal,
    (safeRect.y + safeRect.height - height / 2) / focal,
  ];
  // Preserve the route's original hemisphere and geometry if centering fails.
  // Moving Earth's screen center into the opening is preferable to hiding a route.
  const fallback = overviewCameraFrame({
    width,
    height,
    fov,
    safeRect,
    route,
    direction: facing.clone(),
  });
  let validFrame: CameraFrame | undefined;
  let distance = 28;
  for (let iteration = 0; iteration < 32; iteration++) {
    const orientation = new Quaternion().setFromRotationMatrix(
      new Matrix4().lookAt(facing, new Vector3(), new Vector3(0, 1, 0))
    );
    const right = new Vector3(1, 0, 0).applyQuaternion(orientation);
    const up = new Vector3(0, 1, 0).applyQuaternion(orientation);
    const coordinates = points.map((p) => ({
      x: p.dot(right),
      y: p.dot(up),
      z: p.dot(facing),
    }));
    if (
      limits.some((limit) => limit <= 0) ||
      coordinates.some((p) => p.z <= 0 || !Number.isFinite(p.z))
    ) {
      return validFrame ?? fallback;
    }
    distance = Math.min(
      28,
      Math.max(
        3,
        ...coordinates.map((p) =>
          Math.max(
            4.04 / p.z,
            p.z + (1.05 * Math.abs(p.x)) / limits[p.x < 0 ? 0 : 1],
            p.z + (1.05 * Math.abs(p.y)) / limits[p.y > 0 ? 2 : 3]
          )
        )
      )
    );
    const xs = coordinates.map(
      (p) => width / 2 + (focal * p.x) / (distance - p.z)
    );
    const ys = coordinates.map(
      (p) => height / 2 - (focal * p.y) / (distance - p.z)
    );
    // Clamping the distance can invalidate both surface visibility and bounds.
    // A positive facing dot product alone does not establish an unobscured route.
    if (
      coordinates.some(
        (p, i) =>
          p.z * distance < 4.04 ||
          xs[i] < safeRect.x ||
          xs[i] > safeRect.x + safeRect.width ||
          ys[i] < safeRect.y ||
          ys[i] > safeRect.y + safeRect.height
      )
    )
      return validFrame ?? fallback;
    validFrame = {
      distance,
      direction: facing.clone(),
      offsetX: 0,
      offsetY: 0,
      routeFit: 'complete',
    };
    const dx =
      (Math.min(...xs) + Math.max(...xs)) / 2 - safeRect.x - safeRect.width / 2;
    const dy =
      (Math.min(...ys) + Math.max(...ys)) / 2 -
      safeRect.y -
      safeRect.height / 2;
    if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) break;
    if (iteration < 31) {
      const depth =
        distance -
        coordinates.reduce((sum, p) => sum + p.z, 0) / coordinates.length;
      facing
        .addScaledVector(right, (0.8 * dx * depth) / (focal * 2))
        .addScaledVector(up, (-0.8 * dy * depth) / (focal * 2))
        .normalize();
    }
  }
  return validFrame ?? fallback;
}
export type OverviewCameraIntent = 'automatic' | 'manual' | 'follow';

/** Average sphere directions handles the dateline without flattening route geometry. */
export function overviewInitialDirection(
  route: readonly [number, number, number][],
  aircraft: GlobeCoordinate | null,
  fallback: Vector3
) {
  const valid = route.filter((point) => point.every(Number.isFinite));
  if (valid.length > 1) {
    const center = valid.reduce(
      (sum, point) => sum.add(new Vector3(...point).normalize()),
      new Vector3()
    );
    return (
      center.lengthSq() > 1e-8 ? center : new Vector3(...valid[0])
    ).normalize();
  }
  return aircraft
    ? new Vector3(...globePosition(aircraft.latitude, aircraft.longitude, 1))
    : fallback.clone().normalize();
}
