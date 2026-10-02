import { projectRouteArc } from './globe-route-projection';
import { globePosition } from './globe-coordinates';
import { describe, it, expect } from 'vitest';
import { PerspectiveCamera, Vector3 } from 'three';
import {
  overviewCameraFrame,
  overviewInitialDirection,
} from './overview-camera-frame';
describe('safe-area camera projection', () => {
  it('projects the globe center into the supplied rectangle without changing geometry', () => {
    const frame = overviewCameraFrame({
      width: 390,
      height: 360,
      fov: 45,
      safeRect: { x: 12, y: 12, width: 200, height: 200 },
    });
    expect(frame.distance).toBeGreaterThan(8);
    expect(frame.distance).toBeLessThan(12);
    const camera = new PerspectiveCamera(45, 390 / 360);
    camera.position.set(0, 0, frame.distance);
    camera.setViewOffset(390, 360, frame.offsetX, frame.offsetY, 390, 360);
    camera.updateMatrixWorld();
    const projected = new Vector3(0, 0, 0).project(camera);
    expect((projected.x + 1) * 195).toBeCloseTo(112, 3);
    expect((1 - projected.y) * 180).toBeCloseTo(112, 3);
  });
  it('keeps camera distance within the existing orbit limits on impossible tiny bounds', () => {
    expect(
      overviewCameraFrame({
        width: 390,
        height: 360,
        fov: 45,
        safeRect: { x: 0, y: 0, width: 1, height: 1 },
      }).distance
    ).toBe(28);
  });
});

describe('initial route orientation', () => {
  it('prefers route geometry over an unrelated aircraft and fits its points beside panels', () => {
    const route = projectRouteArc(
      [
        { latitude: 35, longitude: -100 },
        { latitude: 38, longitude: -90 },
        { latitude: 45, longitude: -80 },
      ],
      2.015,
      8
    );
    const direction = overviewInitialDirection(
      route,
      { latitude: -25, longitude: 80 },
      new Vector3(0, 0, 1)
    );
    const frame = overviewCameraFrame({
      width: 390,
      height: 380,
      fov: 45,
      safeRect: { x: 12, y: 12, width: 170, height: 245 },
      route,
      direction,
    });
    const camera = new PerspectiveCamera(45, 390 / 380);
    camera.position.copy(direction.multiplyScalar(frame.distance));
    camera.lookAt(0, 0, 0);
    camera.setViewOffset(390, 380, frame.offsetX, frame.offsetY, 390, 380);
    camera.updateMatrixWorld();
    const projectedXs: number[] = [];
    for (const point of route) {
      const projected = new Vector3(...point).project(camera);
      const x = (projected.x + 1) * 195,
        y = (1 - projected.y) * 190;
      projectedXs.push(x);
      expect(x).toBeGreaterThan(12);
      expect(x).toBeLessThan(182);
      expect(y).toBeGreaterThan(12);
      expect(y).toBeLessThan(257);
      expect(new Vector3(...point).dot(camera.position)).toBeGreaterThan(4);
    }
    expect(Math.max(...projectedXs) - Math.min(...projectedXs)).toBeGreaterThan(
      100
    );
  });
  it('handles a dateline route without aiming at the opposite hemisphere', () => {
    const route = projectRouteArc(
      [
        { latitude: 10, longitude: 170 },
        { latitude: 10, longitude: -170 },
      ],
      2.015,
      8
    );
    const direction = overviewInitialDirection(
      route,
      null,
      new Vector3(0, 0, 1)
    );
    expect(
      direction.dot(new Vector3(...globePosition(10, 180, 1)))
    ).toBeGreaterThan(0.99);
  });
});

it('keeps a broad visible-hemisphere route in front of the globe surface', () => {
  const route = projectRouteArc(
    [
      { latitude: 5, longitude: -85 },
      { latitude: 5, longitude: 85 },
    ],
    2.015,
    16
  );
  const direction = overviewInitialDirection(route, null, new Vector3(0, 0, 1));
  const frame = overviewCameraFrame({
    width: 2000,
    height: 1333,
    fov: 45,
    safeRect: { x: 100, y: 100, width: 1800, height: 900 },
    route,
    direction,
  });
  const position = direction.multiplyScalar(frame.distance);
  for (const point of route)
    expect(new Vector3(...point).dot(position)).toBeGreaterThan(4);
});
