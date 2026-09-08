import { describe, expect, it } from 'vitest';
import { projectRouteArc, projectRoutePoints } from './globe-route-projection';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';

describe('projectRoutePoints', () => {
  it('preserves route-point order while projecting every point onto the globe', () => {
    const route = projectRoutePoints(
      [
        { latitude: 0, longitude: 0 },
        { latitude: 90, longitude: 0 },
      ],
      ROUTE_OVERLAY_RADIUS
    );

    expect(route).toHaveLength(2);

    expect(route[0][0]).toBeCloseTo(ROUTE_OVERLAY_RADIUS, 10);
    expect(route[0][1]).toBeCloseTo(0, 10);
    expect(route[0][2]).toBeCloseTo(0, 10);

    expect(route[1][0]).toBeCloseTo(0, 10);
    expect(route[1][1]).toBeCloseTo(ROUTE_OVERLAY_RADIUS, 10);
    expect(route[1][2]).toBeCloseTo(0, 10);
  });

  it('returns no globe points for an empty route', () => {
    expect(projectRoutePoints([], ROUTE_OVERLAY_RADIUS)).toEqual([]);
  });

  it('keeps a sparse anti-meridian route on the globe surface', () => {
    const route = projectRouteArc(
      [
        { latitude: 0, longitude: 179 },
        { latitude: 0, longitude: -179 },
      ],
      ROUTE_OVERLAY_RADIUS,
      8
    );

    expect(route).toHaveLength(9);

    for (const point of route) {
      expect(Math.hypot(...point)).toBeCloseTo(ROUTE_OVERLAY_RADIUS, 10);
    }

    const midpoint = route[4];

    expect(midpoint[0]).toBeCloseTo(-ROUTE_OVERLAY_RADIUS, 2);
    expect(midpoint[1]).toBeCloseTo(0, 10);
    expect(midpoint[2]).toBeCloseTo(0, 2);
  });
});
