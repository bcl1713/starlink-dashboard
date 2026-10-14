import { expect, it } from 'vitest';
import { lease } from '@/test/gfs-lease';
import * as sampling from './grid-sampling';
import type { WindParticleState } from './wind-particles';

async function physics() {
  const path = './wind-particles';
  return import(path) as Promise<typeof import('./wind-particles')>;
}
function field(u = 10, v = 0) {
  const l = lease();
  l.u.fill(u * 100);
  l.v.fill(v * 100);
  l.mask.fill(0);
  return l;
}
function anchor(s: WindParticleState, lat = 0, lon = 0) {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180;
  s.points.set(
    [Math.cos(a) * Math.cos(b), Math.sin(a), -Math.cos(a) * Math.sin(b)],
    0
  );
  s.history.fill(0, 0, 36);
  s.history.set(s.points.subarray(0, 3), 0);
  s.heads[0] = 0;
  s.lengths[0] = 1;
  s.ages[0] = 0;
  s.lifetimes[0] = 6;
}
function longitude(s: WindParticleState) {
  return Math.atan2(-s.points[2], s.points[0]);
}

it('samples the conservative signed field into a reusable target', () => {
  const l = field(),
    out = new Float64Array(3);
  l.u[0] = -100;
  l.u[719] = 100;
  l.mask[1] = 3;
  expect(typeof sampling.sampleWindInto).toBe('function');
  sampling.sampleWindInto(l, 90, 179.75, out);
  expect(Array.from(out)).toEqual([0, 0, 0]);
  sampling.sampleWindInto(l, 90, -179.75, out);
  expect(Number.isNaN(out[0])).toBe(true);
  expect(out[2]).toBe(3);
  sampling.sampleWindInto(l, 91, 0, out);
  expect(out[2]).toBe(1);
});
it('moves toward east/north with physical speed and the shared visual multiplier', async () => {
  const p = await physics(),
    east = p.createWindParticles(field()),
    fast = p.createWindParticles(field(20)),
    north = p.createWindParticles(field(0, 10));
  for (const s of [east, fast, north]) anchor(s);
  for (const s of [east, fast, north]) p.advanceWindParticles(s, 1 / 60);
  const expected = (10 * 12000) / 60 / 6371000;
  expect(longitude(east)).toBeCloseTo(expected, 10);
  expect(longitude(fast) / longitude(east)).toBeCloseTo(2, 3);
  expect(Math.asin(north.points[1])).toBeCloseTo(expected, 10);
});
it('preserves elapsed-time and 30Hz history across display rates', async () => {
  const p = await physics();
  const states = [30, 60, 120].map(() => p.createWindParticles(field(30, 10)));
  [30, 60, 120].forEach((rate, k) => {
    for (let i = 0; i < rate; i++) p.advanceWindParticles(states[k], 1 / rate);
  });
  for (const state of states.slice(1)) {
    for (let i = 0; i < state.points.length; i += 3) {
      expect(
        Math.hypot(
          state.points[i] - states[0].points[i],
          state.points[i + 1] - states[0].points[i + 1],
          state.points[i + 2] - states[0].points[i + 2]
        )
      ).toBeLessThan((0.05 * Math.PI) / 180);
    }
    expect(Array.from(state.lengths)).toEqual(Array.from(states[0].lengths));
    expect(Array.from(state.heads)).toEqual(Array.from(states[0].heads));
  }
});
it('caps suspended time, ignores invalid deltas and reuses bounded buffers', async () => {
  const p = await physics(),
    a = p.createWindParticles(field()),
    b = p.createWindParticles(field());
  const positions = a.positions,
    alpha = a.alpha,
    points = a.points;
  for (const delta of [-1, NaN, Infinity]) p.advanceWindParticles(a, delta);
  expect(Array.from(a.points)).toEqual(Array.from(b.points));
  p.advanceWindParticles(a, 60);
  p.advanceWindParticles(b, 0.05);
  expect(Array.from(a.points)).toEqual(Array.from(b.points));
  expect(a.positions).toBe(positions);
  expect(a.alpha).toBe(alpha);
  expect(a.points).toBe(points);
  expect(a.count).toBe(2000);
  expect(a.positions.length).toBe(2000 * 11 * 6);
  expect(a.alpha.length).toBe(2000 * 11 * 2);
  expect(a.lengths.every((n) => n <= 12)).toBe(true);
  expect(a.lifetimes.every((n) => n >= 3 && n <= 6)).toBe(true);
});
it('does not invent flow in valid calm cells', async () => {
  const p = await physics(),
    s = p.createWindParticles(field(0, 0)),
    before = s.points.slice();
  for (let i = 0; i < 20; i++) p.advanceWindParticles(s, 1 / 60);
  // Avoid initial end-of-life particles when checking a static physical point.
  const calm = p.createWindParticles(field(0, 0));
  anchor(calm);
  const origin = calm.points.slice(0, 3);
  p.advanceWindParticles(calm, 0.05);
  expect(Array.from(calm.points.slice(0, 3))).toEqual(Array.from(origin));
  expect(s.vertexCount).toBe(0);
  expect(before.every(Number.isFinite)).toBe(true);
});
it.each([1, 2, 3])(
  'bounds respawn work and emits no trails for fully masked %s fields',
  async (mask) => {
    const p = await physics(),
      l = field();
    l.mask.fill(mask);
    const s = p.createWindParticles(l);
    for (let i = 0; i < 3; i++) p.advanceWindParticles(s, 0.05);
    expect(s.vertexCount).toBe(0);
    expect(s.alpha.every((n) => n === 0)).toBe(true);
    expect(s.attempts.every((n) => n <= 4)).toBe(true);
  }
);
it.each([
  [90, 0],
  [-90, 180],
  [89.99999, 179.99999],
  [0, 179.99999],
])('keeps signed extreme winds finite at %s,%s', async (lat, lon) => {
  const p = await physics(),
    l = field();
  l.u.fill(-32768);
  l.v.fill(32767);
  const s = p.createWindParticles(l);
  anchor(s, lat, lon);
  for (let i = 0; i < 10; i++) p.advanceWindParticles(s, 0.05);
  expect(Math.hypot(...s.points.subarray(0, 3))).toBeCloseTo(1, 12);
  expect(s.points.every(Number.isFinite)).toBe(true);
  expect(s.positions.every(Number.isFinite)).toBe(true);
});
it('clears old history on respawn instead of connecting a globe-spanning streak', async () => {
  const p = await physics(),
    s = p.createWindParticles(field());
  anchor(s);
  s.ages[0] = 7;
  p.advanceWindParticles(s, 1 / 120);
  expect(s.lengths[0]).toBe(1);
  expect(s.history.subarray(3, 36).every((n) => n === 0)).toBe(true);
  expect(Math.abs(s.history[0] - 1)).toBeGreaterThan(0.001);
});
it('never bridges an unknown gap even if the segment endpoints are valid', async () => {
  const p = await physics(),
    l = field(327.67);
  l.mask[180 * 720 + 360] = 2;
  const s = p.createWindParticles(l);
  anchor(s, 0, -0.75);
  for (let i = 0; i < 5; i++) p.advanceWindParticles(s, 1 / 30);
  const out = new Float64Array(3);
  for (let i = 0; i < s.vertexCount; i += 2) {
    const a = i * 3,
      b = (i + 1) * 3;
    const x = s.positions[a] + s.positions[b],
      y = s.positions[a + 1] + s.positions[b + 1],
      z = s.positions[a + 2] + s.positions[b + 2];
    sampling.sampleWindInto(
      l,
      (Math.atan2(y, Math.hypot(x, z)) * 180) / Math.PI,
      (Math.atan2(-z, x) * 180) / Math.PI,
      out
    );
    expect(out[2]).toBe(0);
  }
});
