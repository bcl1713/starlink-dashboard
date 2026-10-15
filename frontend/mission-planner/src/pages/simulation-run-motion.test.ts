import { expect, it } from 'vitest';
import { prepareRunMotion, projectRunMotion } from './simulation-run-motion';

const at = (seconds: number) =>
  new Date(Date.UTC(2025, 0, 1) + seconds * 1000).toISOString();
const point = (longitude: number, seconds: number, altitude = 1000) => ({
  latitude: 0,
  longitude,
  altitude,
  expected_arrival_time: at(seconds),
});
it('interpolates sub-second movement across the dateline using segment timing', () => {
  const path = prepareRunMotion([
    point(179, 0),
    point(-179, 300),
    point(-178, 1200),
  ]);
  expect(projectRunMotion(path, Date.parse(at(150)))?.longitude).toBe(-180);
  expect(
    projectRunMotion(path, Date.parse(at(150)) + 100)?.longitude
  ).toBeCloseTo(-179.999333, 6);
  expect(projectRunMotion(path, Date.parse(at(750)))?.longitude).toBeCloseTo(
    -178.5
  );
});
it('keeps stationary segments still and clamps exact endpoints', () => {
  const path = prepareRunMotion([
    point(0, 0),
    point(1, 300),
    point(1, 600),
    point(2, 1200),
  ]);
  expect(projectRunMotion(path, Date.parse(at(450)))?.longitude).toBe(1);
  expect(projectRunMotion(path, Date.parse(at(-1)))?.longitude).toBe(0);
  expect(projectRunMotion(path, Date.parse(at(1300)))?.longitude).toBe(2);
});
it('converts interpolated route altitude from metres to status feet', () => {
  const path = prepareRunMotion([point(0, 0, 1000), point(1, 300, 2000)]);
  expect(projectRunMotion(path, Date.parse(at(150)))?.altitude).toBeCloseTo(
    1500 * 3.28084
  );
});
it('rejects missing or non-monotonic route timing', () => {
  expect(
    prepareRunMotion([
      point(0, 0),
      { ...point(1, 300), expected_arrival_time: null },
    ])
  ).toBeNull();
  expect(prepareRunMotion([point(0, 300), point(1, 0)])).toBeNull();
});
