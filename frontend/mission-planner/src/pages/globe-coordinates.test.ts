import { describe, expect, it } from 'vitest';
import { globePosition } from './globe-coordinates';

describe('globePosition', () => {
  it('places the North Pole on the positive Y axis', () => {
    const [x, y, z] = globePosition(90, 0, 2);

    expect(x).toBeCloseTo(0, 10);
    expect(y).toBeCloseTo(2, 10);
    expect(z).toBeCloseTo(0, 10);
  });

  it('places the equator at 90 degrees west on the positive Z axis', () => {
    const [x, y, z] = globePosition(0, -90, 2);

    expect(x).toBeCloseTo(0, 10);
    expect(y).toBeCloseTo(0, 10);
    expect(z).toBeCloseTo(2, 10);
  });
});
