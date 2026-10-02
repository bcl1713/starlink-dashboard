import { Matrix4, Quaternion, Vector3 } from 'three';
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
    route.every(
      (point) =>
        point.every(Number.isFinite) && new Vector3(...point).dot(direction) > 0
    )
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
          4.04 / p.dot(direction),
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
  };
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
  const facing = direction!.clone().normalize();
  const focal = height / (2 * Math.tan((fov * Math.PI) / 360));
  const limits = [
    (width / 2 - safeRect.x) / focal,
    (safeRect.x + safeRect.width - width / 2) / focal,
    (height / 2 - safeRect.y) / focal,
    (safeRect.y + safeRect.height - height / 2) / focal,
  ];
  const points = route!.map((point) => new Vector3(...point));
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
      const fallback = overviewCameraFrame({
        width,
        height,
        fov,
        safeRect,
        direction: facing,
      });
      return { ...fallback, offsetX: 0, offsetY: 0, direction: facing };
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
  return { distance, direction: facing, offsetX: 0, offsetY: 0 };
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
