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
}
/** Fit the unchanged radius-two globe into measured CSS space, with 10% margin. */
export function overviewCameraFrame({
  width,
  height,
  fov,
  safeRect,
  route,
  direction,
}: FrameInput) {
  const fullHeight = Math.max(1, height),
    fullWidth = Math.max(1, width);
  const fraction = Math.max(
    0.001,
    Math.min(safeRect.height / fullHeight, safeRect.width / fullHeight)
  );
  const halfAngle = Math.atan(Math.tan((fov * Math.PI) / 360) * fraction);
  let distance = 2.2 / Math.sin(halfAngle);
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
    offsetX: fullWidth / 2 - safeRect.x - safeRect.width / 2,
    offsetY: fullHeight / 2 - safeRect.y - safeRect.height / 2,
  };
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
