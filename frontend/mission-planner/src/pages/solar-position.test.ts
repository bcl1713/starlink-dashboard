import { describe, expect, it } from 'vitest';
import { subsolarPoint, sunLightPosition } from './solar-position';

describe('subsolarPoint', () => {
  it('places the Sun near the Tropic of Cancer at the June solstice', () => {
    const point = subsolarPoint(new Date('2026-06-21T12:00:00Z'));

    expect(point.latitude).toBeCloseTo(23.45, 1);
    expect(point.longitude).toBeCloseTo(0.33, 1);
  });
  it('places the Sun near the Tropic of Capricorn at the December solstice', () => {
    const point = subsolarPoint(new Date('2026-12-21T12:00:00Z'));

    expect(point.latitude).toBeCloseTo(-23.42, 1);
    expect(point.longitude).toBeCloseTo(-0.54, 1);
  });
  it('projects the June-solstice Sun to the requested globe distance', () => {
    const lightPosition = sunLightPosition(
      new Date('2026-06-21T12:00:00Z'),
      10
    );

    expect(Math.hypot(...lightPosition)).toBeCloseTo(10, 8);
    expect(lightPosition[1]).toBeGreaterThan(3);
  });
});
