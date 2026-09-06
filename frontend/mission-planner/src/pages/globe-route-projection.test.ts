import { describe, expect, it } from 'vitest';
import { projectRouteArc, projectRoutePoints } from './globe-route-projection';

describe('projectRoutePoints', () => {
  it('preserves route-point order while projecting every point onto the globe', () => {
    const route = projectRoutePoints(
      [
        { latitude: 0, longitude: 0 },
        { latitude: 90, longitude: 0 },
      ],
      2.02
    );

    expect(route).toHaveLength(2);

    expect(route[0][0]).toBeCloseTo(2.02, 10);
    expect(route[0][1]).toBeCloseTo(0, 10);
    expect(route[0][2]).toBeCloseTo(0, 10);

    expect(route[1][0]).toBeCloseTo(0, 10);
    expect(route[1][1]).toBeCloseTo(2.02, 10);
    expect(route[1][2]).toBeCloseTo(0, 10);
  });

  it('returns no globe points for an empty route', () => {
    expect(projectRoutePoints([], 2.02)).toEqual([]);
  });

  it('keeps a sparse anti-meridian route on the globe surface', () => {
    const route = projectRouteArc(
      [
        { latitude: 0, longitude: 179 },
        { latitude: 0, longitude: -179 },
      ],
      2.02,
      8
    );

    expect(route).toHaveLength(9);

    for (const point of route) {
      expect(Math.hypot(...point)).toBeCloseTo(2.02, 10);
    }

    const midpoint = route[4];

    expect(midpoint[0]).toBeCloseTo(-2.02, 2);
    expect(midpoint[1]).toBeCloseTo(0, 10);
    expect(midpoint[2]).toBeCloseTo(0, 2);
  });
});
