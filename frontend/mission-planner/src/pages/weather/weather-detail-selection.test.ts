import { expect, it } from 'vitest';
import { Matrix4, PerspectiveCamera } from 'three';
import { readyWeather } from '@/test/weather-fixtures';
import {
  selectDetail,
  DetailDemandStabilizer,
  type CameraSnapshot,
} from './weather-detail-selection';

function camera(
  distance = 2.12,
  width = 1920,
  height = 1080,
  side = 1
): CameraSnapshot {
  const value = new PerspectiveCamera(45, width / height, 0.001, 100);
  value.position.set(distance * side, 0, 0);
  value.lookAt(0, 0, 0);
  value.updateMatrixWorld();
  return {
    projection: value.projectionMatrix.toArray(),
    cameraWorld: value.matrixWorld.toArray(),
    globeWorld: new Matrix4().toArray(),
    drawingBuffer: [width, height],
  };
}
it('regional native camera selects actual higher zoom, bounded to canonical visible keys', () => {
  const demand = selectDetail(camera(), readyWeather(), null);
  expect(demand.level).toBeGreaterThan(2);
  expect(demand.keys.length).toBeGreaterThan(0);
  expect(demand.keys.length).toBeLessThanOrEqual(8);
  for (const key of demand.keys) {
    expect(key.z).toBe(demand.level);
    expect(key.x).toBeGreaterThanOrEqual(0);
    expect(key.x).toBeLessThan(2 ** key.z);
    expect(key.y).toBeGreaterThanOrEqual(0);
    expect(key.y).toBeLessThan(2 ** key.z);
    // Greenwich-facing regional view cannot demand the hidden Pacific hemisphere.
    expect(Math.abs((key.x + 0.5) / 2 ** key.z - 0.5)).toBeLessThan(0.1);
  }
});
it('wraps visible antimeridian keys without leaking to the opposite hemisphere', () => {
  const demand = selectDetail(
    camera(2.12, 1920, 1080, -1),
    readyWeather(),
    null
  );
  const n = 2 ** demand.level;
  expect(demand.keys.some((key) => key.x < n * 0.1)).toBe(true);
  expect(demand.keys.some((key) => key.x >= n * 0.9)).toBe(true);
});
it('uses actual view offset, transformed globe and drawing buffer', () => {
  const snapshot = camera();
  const value = new PerspectiveCamera(45, 1920 / 1080, 0.001, 100);
  value.setViewOffset(1920, 1080, 960, 0, 960, 1080);
  const offset = selectDetail(
    { ...snapshot, projection: value.projectionMatrix.toArray() },
    readyWeather(),
    null
  );
  const ordinary = selectDetail(snapshot, readyWeather(), null);
  expect(offset.keys).not.toEqual(ordinary.keys);
  const rotated = selectDetail(
    { ...snapshot, globeWorld: new Matrix4().makeRotationY(Math.PI).toArray() },
    readyWeather(),
    null
  );
  expect(rotated.keys).not.toEqual(ordinary.keys);
  const mobile = selectDetail(camera(2.12, 390, 844), readyWeather(), null);
  expect(mobile.level).toBeLessThanOrEqual(ordinary.level);
});
it('does not refine a low-resolution whole globe or unsupported capabilities', () => {
  expect(selectDetail(camera(10, 390, 844), readyWeather(), null).keys).toEqual(
    []
  );
  expect(
    selectDetail(
      camera(),
      { ...readyWeather(), tile_schema: 'unknown' as never },
      null
    ).keys
  ).toEqual([]);
});
it('normalized source capabilities drive selection', () => {
  const demand = selectDetail(
    camera(2.005, 3840, 2160),
    { ...readyWeather(), max_zoom: 5 },
    null
  );
  expect(demand.level).toBeLessThanOrEqual(5);
  expect(demand.keys.every((key) => key.z <= 5)).toBe(true);
});
it('stabilizes one pending selection for 400 ms and never reemits identical keys', () => {
  const stable = new DetailDemandStabilizer();
  const demand = selectDetail(camera(), readyWeather(), null);
  expect(stable.update(demand, 0)).toBeNull();
  expect(stable.update(demand, 399)).toBeNull();
  expect(stable.update(demand, 400)).toEqual(demand);
  expect(stable.update(demand, 800)).toBeNull();
  const moved = { ...demand, keys: [{ z: 3, x: 1, y: 1 }], level: 3 };
  expect(stable.update(moved, 900)).toBeNull();
  expect(stable.update(demand, 1000)).toBeNull();
  expect(stable.update(moved, 1100)).toBeNull();
  expect(stable.update(moved, 1499)).toBeNull();
  expect(stable.update(moved, 1500)).toEqual(moved);
});
it('keeps resolution inside the twenty percent hysteresis band', () => {
  const initial = selectDetail(camera(), readyWeather(), null);
  const moved = selectDetail(camera(2.121), readyWeather(), initial);
  expect(moved.level).toBe(initial.level);
});
it('keeps polar missing coverage at the coarse fallback and rejects tangent-only views', () => {
  const polar = new PerspectiveCamera(45, 1920 / 1080, 0.001, 100);
  polar.position.set(0, 2.005, 0);
  polar.lookAt(0, 2, 0);
  polar.updateMatrixWorld();
  const snapshot = {
    ...camera(),
    projection: polar.projectionMatrix.toArray(),
    cameraWorld: polar.matrixWorld.toArray(),
  };
  expect(selectDetail(snapshot, readyWeather(), null).keys).toEqual([]);
  const away = new PerspectiveCamera(45, 1920 / 1080, 0.001, 100);
  away.position.set(3, 0, 0);
  away.lookAt(4, 0, 0);
  away.updateMatrixWorld();
  expect(
    selectDetail(
      { ...camera(), cameraWorld: away.matrixWorld.toArray() },
      readyWeather(),
      null
    ).keys
  ).toEqual([]);
});
