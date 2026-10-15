import { expect, it } from 'vitest';
import { mercatorUv, weatherUvFromPosition } from './weather-projection';
it('maps independent globe coordinates to the top-left provider grid', () => {
  expect(weatherUvFromPosition([1, 0, 0])).toEqual([0.5, 0.5]);
  expect(weatherUvFromPosition([0, 0, -1])).toEqual([0.75, 0.5]);
  expect(mercatorUv(66.51326044311186, -90)?.[0]).toBe(0.25);
  expect(mercatorUv(66.51326044311186, -90)?.[1]).toBeCloseTo(0.25, 10);
  expect(mercatorUv(0, -180)).toEqual([0, 0.5]);
  expect(mercatorUv(0, 180)).toEqual([0, 0.5]);
  expect(mercatorUv(90, 0)).toBeNull();
  expect(mercatorUv(-90, 0)).toBeNull();
});
