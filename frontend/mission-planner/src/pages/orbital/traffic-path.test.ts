import { expect, it } from 'vitest';
import { chooseTrafficPath, projectOrbitalTrafficPath } from './traffic-path';
import { projectAircraftScenePosition } from '../x-band-active-link-projection';
import { projectTrafficArc } from '../overview-traffic-arc';
import { selectRoute, emptyRoutingState } from './routing';
import { circle } from './routing-test-fixtures';
import { spriteSnapshot } from './sprite-test-fixtures';
import { ecefKmToScene, sceneToEcefKm } from './coordinates';
import { segmentClearanceKm } from './geometry';
const aircraft = projectAircraftScenePosition({
  position: { latitude: 0, longitude: 0, altitude: 35000 },
})!;
const pop = { latitude: 0, longitude: 60 };
function fixture() {
  const s = spriteSnapshot(
    [circle(0), circle(20), circle(40), circle(60)],
    ['1', '2', '3', '4']
  );
  const r = selectRoute(
    s,
    { aircraft: sceneToEcefKm(aircraft.position), pop: circle(60, 6378.137) },
    emptyRoutingState('a')
  ).route!;
  return { s, r };
}
it('orbital_polyline_preserves_clearance_and_altitude without missing-hop repairs', () => {
  const { s, r } = fixture();
  // Use precisely the same scene→physical endpoint as the worker.
  r.identity = JSON.stringify([
    'a',
    r.ids,
    sceneToEcefKm(ecefKmToScene(circle(60, 6378.137))),
  ]);
  const points = projectOrbitalTrafficPath(r, s, aircraft, pop);
  expect(points.length).toBe(r.ids.length + 2);
  expect(points[0]).toEqual(aircraft.position);
  expect(Math.hypot(...points[1])).toBeCloseTo((7000 * 2) / 6378.137);
  points
    .slice(1)
    .forEach((point, i) =>
      expect(
        segmentClearanceKm(sceneToEcefKm(points[i]), sceneToEcefKm(point))
      ).toBeGreaterThanOrEqual(i === 0 || i === points.length - 2 ? -1e-7 : 80)
    );
  s.valid[0] = 0;
  expect(projectOrbitalTrafficPath(r, s, aircraft, pop)).toEqual([]);
  expect(projectOrbitalTrafficPath(r, s, null, pop)).toEqual([]);
});
it('same sequence preserves key across aircraft movement; catalog/sequence/PoP handovers change it', () => {
  const { s, r } = fixture();
  const chosen = chooseTrafficPath(r, s, aircraft, pop);
  expect(chosen.orbital).toBe(true);
  const moved = {
    ...aircraft,
    position: ecefKmToScene(circle(0.01, 6388.8)) as [number, number, number],
  };
  expect(chooseTrafficPath(r, s, moved, pop).particleKey).toBe(
    chosen.particleKey
  );
  expect(chooseTrafficPath(null, s, moved, pop).particleKey).not.toBe(
    chosen.particleKey
  );
  expect(chooseTrafficPath(null, s, aircraft, pop).points).toEqual(
    projectTrafficArc(aircraft, pop)
  );
  expect(
    chooseTrafficPath(r, s, aircraft, { ...pop, longitude: 61 }).orbital
  ).toBe(false);
  expect(
    chooseTrafficPath(r, { ...s, catalogGeneration: 'new' }, aircraft, pop)
      .orbital
  ).toBe(false);
});
