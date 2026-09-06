import { describe, expect, it } from 'vitest';
import { greatCirclePoints } from './globe-route';

describe('greatCirclePoints', () => {
  it('includes both route endpoints and the requested number of segments', () => {
    const route = greatCirclePoints(
      { latitude: 41.8781, longitude: -87.6298 },
      { latitude: 51.5072, longitude: -0.1276 },
      2.02,
      8
    );

    expect(route).toHaveLength(9);

    const [startX, startY, startZ] = route[0];
    expect(startX).toBeCloseTo(0.05, 1);
    expect(startY).toBeCloseTo(1.34, 1);
    expect(startZ).toBeCloseTo(1.51, 1);

    const [endX, endY, endZ] = route.at(-1)!;
    expect(endX).toBeCloseTo(1.25, 1);
    expect(endY).toBeCloseTo(1.58, 1);
    expect(endZ).toBeCloseTo(0.0, 1);
  });
  it('keeps every interpolated route point on the requested radius', () => {
    const route = greatCirclePoints(
      { latitude: 41.8781, longitude: -87.6298 },
      { latitude: 51.5072, longitude: -0.1276 },
      2.02,
      8
    );

    for (const [x, y, z] of route) {
      expect(Math.hypot(x, y, z)).toBeCloseTo(2.02, 10);
    }
  });
});
