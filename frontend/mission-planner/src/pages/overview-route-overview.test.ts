import { describe, expect, it } from 'vitest';
import { PerspectiveCamera, Vector3 } from 'three';
import { globePosition } from './globe-coordinates';
import { projectRouteArc } from './globe-route-projection';
import {
  overviewCameraFrame,
  overviewInitialDirection,
} from './overview-camera-frame';

// Fabricated coordinates, independent of any imported mission or airport.
const crossing = [
  { latitude: 58, longitude: -135 },
  { latitude: 50, longitude: 170 },
  { latitude: 25, longitude: 140 },
  { latitude: 5, longitude: 115 },
];
const safeRect = { x: 520, y: 380, width: 1380, height: 640 };
const width = 1920,
  height = 1280;
function cameraFor(frame: ReturnType<typeof overviewCameraFrame>) {
  const camera = new PerspectiveCamera(45, width / height);
  camera.position.copy(frame.direction!.clone().multiplyScalar(frame.distance));
  camera.lookAt(0, 0, 0);
  camera.setViewOffset(
    width,
    height,
    frame.offsetX,
    frame.offsetY,
    width,
    height
  );
  camera.updateMatrixWorld();
  return camera;
}
function visible(
  camera: PerspectiveCamera,
  point: readonly number[],
  inset = 0
) {
  const p = new Vector3(...point),
    surface = p.dot(camera.position);
  p.project(camera);
  const x = ((p.x + 1) * width) / 2,
    y = ((1 - p.y) * height) / 2;
  return (
    surface > 4.04 &&
    x > safeRect.x + inset &&
    x < safeRect.x + safeRect.width - inset &&
    y > safeRect.y + inset &&
    y < safeRect.y + safeRect.height - inset
  );
}
describe('route overview framing', () => {
  it.each([false, true])(
    'keeps a broad crossing readable with fullscreen=%s',
    (centerGlobe) => {
      const route = projectRouteArc(crossing, 2.015, 24);
      const frame = overviewCameraFrame({
        width,
        height,
        fov: 45,
        safeRect,
        route,
        centerGlobe,
        aircraft: crossing[0],
        direction: overviewInitialDirection(route, null, new Vector3(0, 0, 1)),
      });
      const camera = cameraFor(frame);
      expect(frame.routeFit).toBe('complete');
      expect(route.every((point) => visible(camera, point))).toBe(true);
      const ys = route.map(
        (point) => (new Vector3(...point).project(camera).y * height) / 2
      );
      expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(450);
      expect(
        visible(
          camera,
          globePosition(crossing[0].latitude, crossing[0].longitude, 2.04),
          16
        )
      ).toBe(true);
    }
  );
  it.each([false, true])(
    'does not let dense destination samples choose the overview angle with fullscreen=%s',
    (centerGlobe) => {
      const route = projectRouteArc(crossing, 2.015, 24);
      const dense = [
        ...route,
        ...Array.from({ length: 1000 }, () => route.at(-1)!),
      ];
      const frame = (points: typeof route) =>
        overviewCameraFrame({
          width,
          height,
          fov: 45,
          safeRect,
          route: points,
          centerGlobe,
          direction: overviewInitialDirection(
            points,
            null,
            new Vector3(0, 0, 1)
          ),
        });
      const a = frame(route),
        b = frame(dense);
      expect(a.direction!.angleTo(b.direction!)).toBeLessThan(0.001);
      expect(a.distance).toBeCloseTo(b.distance, 3);
    }
  );
  it('keeps an unrelated aircraft visible when a route is on the opposite hemisphere', () => {
    const route = projectRouteArc(
      [
        { latitude: 25, longitude: 15 },
        { latitude: 20, longitude: 30 },
      ],
      2.015,
      12
    );
    const aircraft = { latitude: -25, longitude: -165 };
    const frame = overviewCameraFrame({
      width,
      height,
      fov: 45,
      safeRect,
      route,
      aircraft,
      direction: overviewInitialDirection(route, null, new Vector3(0, 0, 1)),
    });
    expect(frame.routeFit).toBe('partial');
    expect(visible(cameraFor(frame), globePosition(-25, -165, 2.04), 16)).toBe(
      true
    );
  });
  it('fits useful forward context around the aircraft when the entire route spans the globe', () => {
    const route = Array.from({ length: 65 }, (_, i) =>
      globePosition(0, i * 5, 2.015)
    );
    const aircraft = { latitude: 0, longitude: 90 };
    const frame = overviewCameraFrame({
      width,
      height,
      fov: 45,
      safeRect,
      route,
      aircraft,
      direction: overviewInitialDirection(route, null, new Vector3(0, 0, 1)),
      centerGlobe: true,
    });
    const camera = cameraFor(frame);
    expect(frame.routeFit).toBe('partial');
    expect(frame.distance).toBeLessThan(12);
    expect(visible(camera, globePosition(0, 90, 2.04), 16)).toBe(true);
    const indices = route.flatMap((point, i) =>
      visible(camera, point) ? [i] : []
    );
    expect(indices.length).toBeGreaterThan(24);
    expect(indices.filter((i) => i > 18).length).toBeGreaterThan(
      indices.filter((i) => i < 18).length
    );
  });
});
