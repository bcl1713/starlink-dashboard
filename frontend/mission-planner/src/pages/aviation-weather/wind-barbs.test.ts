import { expect, it } from 'vitest';
import { barb, windSamples, windFrame } from './wind-barbs';
import { lease } from '@/test/gfs-lease';
it('uses rounded knots with filled 50 knot pennants, full 10 and half 5 feathers and calm circles', () => {
  expect(barb(0, 0)).toMatchObject({ knots: 0, calm: true });
  expect(barb(65 / 1.9438444924406, 0)).toMatchObject({
    knots: 65,
    flags: 1,
    full: 1,
    half: 1,
    fromEast: -1,
    fromNorth: 0,
  });
  expect(barb(2 / 1.9438444924406, 0).calm).toBe(true);
});
it.each([
  [50, 179],
  [-50, -179],
  [89, 0],
  [-89, 90],
])('points toward meteorological wind FROM at %s,%s', (lat, lon) => {
  const f = windFrame(lat, lon, 10, -20);
  expect(f.shaft.dot(f.east)).toBeCloseTo(-1 / Math.sqrt(5));
  expect(f.shaft.dot(f.north)).toBeCloseTo(2 / Math.sqrt(5));
  expect(f.east.dot(f.north)).toBeCloseTo(0);
  expect(f.shaft.length()).toBeCloseTo(1);
});
it('uses a deterministic equal area subset, at most 2000, omitting all masked cells', () => {
  const l = lease(),
    a = windSamples(l);
  expect(a.length).toBe(2000);
  expect(a).toEqual(windSamples(l));
  expect(new Set(a.map((s) => s.row * 720 + s.col)).size).toBe(a.length);
  for (const s of a) l.mask[s.row * 720 + s.col] = 2;
  expect(windSamples(l)).toHaveLength(0);
});
