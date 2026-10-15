import { describe, expect, it } from 'vitest';
import { globePosition } from './globe-coordinates';
import type { GlobeCoordinate } from './globe-route';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';
import type { FlowPoint } from './overview-animated-flow-line-rendering';
import { projectTrafficArc } from './overview-traffic-arc';
import {
  projectAircraftScenePosition,
  type AircraftScenePosition,
} from './x-band-active-link-projection';

function aircraftAt(
  latitude: number,
  longitude: number,
  altitude = 35_000
): AircraftScenePosition {
  const aircraft = projectAircraftScenePosition({
    position: { latitude, longitude, altitude },
  });
  if (!aircraft) throw new Error('Expected valid aircraft fixture');
  return aircraft;
}

function closestSegmentRadius(start: FlowPoint, end: FlowPoint): number {
  const delta = end.map((value, axis) => value - start[axis]);
  const lengthSquared = delta.reduce((sum, value) => sum + value * value, 0);
  const t =
    lengthSquared === 0
      ? 0
      : Math.max(
          0,
          Math.min(
            1,
            -start.reduce((sum, value, axis) => sum + value * delta[axis], 0) /
              lengthSquared
          )
        );
  return Math.hypot(...start.map((value, axis) => value + t * delta[axis]));
}

function expectSafeArc(
  arc: FlowPoint[],
  aircraft: AircraftScenePosition,
  pop: GlobeCoordinate
) {
  // Requiring the full path prevents failing closed on valid adversarial routes.
  expect(arc).toHaveLength(129);
  expect(arc.length).toBeLessThanOrEqual(129);
  expect(arc[0]).toEqual(aircraft.position);
  expect(arc.at(-1)).toEqual(
    globePosition(pop.latitude, pop.longitude, ROUTE_OVERLAY_RADIUS)
  );
  const startRadius = Math.hypot(...aircraft.position);
  arc.forEach((point, index) => {
    expect(point.every(Number.isFinite)).toBe(true);
    const t = index / 128;
    const baseline = startRadius * (1 - t) + ROUTE_OVERLAY_RADIUS * t;
    const lift = Math.hypot(...point) - baseline;
    expect(lift).toBeGreaterThanOrEqual(-1e-12);
    expect(lift).toBeLessThanOrEqual(0.6 + 1e-12);
    if (index > 0) {
      const closestRadius = closestSegmentRadius(arc[index - 1], point);
      expect(closestRadius).toBeGreaterThanOrEqual(2 - 1e-7);
    }
  });
}

describe('projectTrafficArc', () => {
  it.each([0, 10, 35_000, 100_000])(
    'anchors the exact aircraft projection at %s feet and PoP surface overlay',
    (altitude) => {
      const aircraft = aircraftAt(12, -60, altitude);
      const pop = { latitude: 41.2565, longitude: -95.9345 };
      expectSafeArc(projectTrafficArc(aircraft, pop), aircraft, pop);
    }
  );

  it.each([
    ['dateline', 10, 179, 12, -179],
    ['north polar', 89.99, -120, 89.99, 60],
    ['opposite poles', 90, 0, -90, 180],
    ['south polar', -89.99, 80, -80, -100],
    ['long route', 51.5074, -0.1278, -33.8688, 151.2093],
    ['near coincident', 0, 0, 0, 0.000001],
    ['short route', 0, 0, 0, 0.01],
    ['before antipodal threshold', 0, 0, 0, 178.1],
    ['after antipodal threshold', 0, 0, 0, 178.2],
    ['inclusive geographic limits', -90, -180, 90, 180],
  ] as const)(
    'keeps %s segments finite and outside Earth',
    (_, lat, lon, popLat, popLon) => {
      const aircraft = aircraftAt(lat, lon, 0);
      const pop = { latitude: popLat, longitude: popLon };
      expectSafeArc(projectTrafficArc(aircraft, pop), aircraft, pop);
    }
  );

  it('keeps every antipodal segment outside Earth', () => {
    for (const [lat, lon] of [
      [0, 0],
      [0, 90],
      [45, 45],
      [90, 0],
      [-45, -120],
    ]) {
      const aircraft = aircraftAt(lat, lon, 0);
      const pop = {
        latitude: -lat,
        longitude: lon > 0 ? lon - 180 : lon + 180,
      };
      const arc = projectTrafficArc(aircraft, pop);
      expectSafeArc(arc, aircraft, pop);
      expect(arc.length).toBeLessThanOrEqual(129);
      expect(arc[0]).toEqual(aircraft.position);
      for (let index = 1; index < arc.length; index++) {
        const closestRadius = closestSegmentRadius(arc[index - 1], arc[index]);
        expect(closestRadius).toBeGreaterThanOrEqual(2 - 1e-7);
      }
    }
  });

  it.each([
    [0, 0, 0.00001, 179.99999],
    [45, 45, -45.00001, -135.00001],
    [89.9999, 0, -89.9999, 179.9999],
  ])(
    'preserves near-antipodal endpoints (%s, %s)',
    (lat, lon, popLat, popLon) => {
      const aircraft = aircraftAt(lat, lon, 0);
      const pop = { latitude: popLat, longitude: popLon };
      expectSafeArc(projectTrafficArc(aircraft, pop), aircraft, pop);
    }
  );

  it.each([
    [0, 0.04],
    [1, 0.04],
    [60, 0.3],
    [90, 0.4242640687119285],
    [180, 0.6],
  ])(
    'uses the bounded sinusoidal lift for a %s degree route',
    (longitude, height) => {
      const aircraft = aircraftAt(0, 0);
      const arc = projectTrafficArc(aircraft, { latitude: 0, longitude });
      expect(arc).toHaveLength(129);
      const startRadius = Math.hypot(...aircraft.position);
      for (const index of [1, 32, 64, 96, 127]) {
        const t = index / 128;
        const baseline = startRadius * (1 - t) + ROUTE_OVERLAY_RADIUS * t;
        expect(Math.hypot(...arc[index]) - baseline).toBeCloseTo(
          height * Math.sin(Math.PI * t),
          12
        );
      }
    }
  );

  it.each([0, 35_000])(
    'makes a shallow radial arch at coincident coordinates (%s feet)',
    (altitude) => {
      const aircraft = aircraftAt(0, 0, altitude);
      const pop = { latitude: 0, longitude: 0 };
      const arc = projectTrafficArc(aircraft, pop);
      expectSafeArc(arc, aircraft, pop);
      for (const [x, y, z] of arc) {
        expect(x).toBeGreaterThanOrEqual(2);
        expect(y).toBe(0);
        expect(z).toBeCloseTo(0, 12);
      }
    }
  );

  it('uses a repeatable least-aligned-axis midpoint for antipodal directions', () => {
    const aircraft = aircraftAt(0, 0, 0);
    const pop = { latitude: 0, longitude: 180 };
    Object.freeze(aircraft.position);
    Object.freeze(aircraft);
    Object.freeze(pop);
    const arc = projectTrafficArc(aircraft, pop);
    // +X start has Y as its first least-aligned Cartesian axis.
    expect(arc[64][0]).toBeCloseTo(0, 12);
    expect(arc[64][1]).toBeCloseTo(2.6000004778824914, 12);
    expect(arc[64][2]).toBeCloseTo(0, 12);
    expect(projectTrafficArc(aircraft, pop)).toEqual(arc);
    expect(
      projectTrafficArc(
        { ...aircraft, position: [...aircraft.position] },
        { ...pop }
      )
    ).toEqual(arc);
  });

  it('returns no arc for missing endpoints or unavailable altitude', () => {
    const aircraft = aircraftAt(0, 0);
    const pop = { latitude: 0, longitude: 90 };
    expect(projectTrafficArc(null, pop)).toEqual([]);
    expect(projectTrafficArc(aircraft, null)).toEqual([]);
    const missingAltitude = projectAircraftScenePosition({
      position: { latitude: 0, longitude: 0 },
    });
    expect(missingAltitude).toBeNull();
    expect(projectTrafficArc(missingAltitude, pop)).toEqual([]);
  });

  it.each([
    { latitude: -90.001, longitude: 0 },
    { latitude: 90.001, longitude: 0 },
    { latitude: 0, longitude: -180.001 },
    { latitude: 0, longitude: 180.001 },
    { latitude: NaN, longitude: 0 },
    { latitude: Infinity, longitude: 0 },
    { latitude: -Infinity, longitude: 0 },
    { latitude: 0, longitude: NaN },
    { latitude: 0, longitude: Infinity },
    { latitude: 0, longitude: -Infinity },
  ])('rejects invalid geographic inputs %j independently', (invalid) => {
    const aircraft = aircraftAt(0, 0);
    expect(projectTrafficArc(aircraft, invalid)).toEqual([]);
    expect(
      projectTrafficArc(
        { ...aircraft, ...invalid },
        { latitude: 0, longitude: 90 }
      )
    ).toEqual([]);
  });

  it.each([NaN, Infinity, -Infinity, undefined])(
    'rejects invalid aircraft altitude %s',
    (altitudeFeet) => {
      expect(
        projectTrafficArc(
          { ...aircraftAt(0, 0), altitudeFeet: altitudeFeet as number },
          { latitude: 0, longitude: 90 }
        )
      ).toEqual([]);
    }
  );

  it.each([
    [NaN, 0, 0],
    [0, Infinity, 0],
    [0, 0, -Infinity],
    [Number.MAX_VALUE, Number.MAX_VALUE, 0],
    [0, 0, 0],
    [1.99, 0, 0],
  ] as [number, number, number][])(
    'rejects nonfinite or below-surface projection %j',
    (...position) => {
      expect(
        projectTrafficArc(
          { ...aircraftAt(0, 0), position },
          { latitude: 0, longitude: 90 }
        )
      ).toEqual([]);
    }
  );

  it('rejects below-surface altitude without changing the existing aircraft projection', () => {
    const aircraft = aircraftAt(0, 0, -1);
    expect(aircraft.altitudeFeet).toBe(-1);
    expect(projectTrafficArc(aircraft, { latitude: 0, longitude: 90 })).toEqual(
      []
    );
  });
});
