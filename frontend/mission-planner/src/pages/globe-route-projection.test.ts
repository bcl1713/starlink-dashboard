import { describe, expect, it } from 'vitest';
import { projectRoutePoints } from './globe-route-projection';

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
});
