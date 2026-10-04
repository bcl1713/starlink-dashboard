import { globePosition } from '../globe-coordinates';
import type { GlobeCoordinate } from '../globe-route';
import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import { projectTrafficArc } from '../overview-traffic-arc';
import type { AircraftScenePosition } from '../x-band-active-link-projection';
import { ecefKmToScene, sceneToEcefKm } from './coordinates';
import { pointAt, segmentClearanceKm } from './geometry';
import { routeIsValid } from './routing';
import type { OrbitalRoute, OrbitalSnapshot } from './types';

export function projectOrbitalTrafficPath(
  route: OrbitalRoute | null,
  snapshot: OrbitalSnapshot | null,
  aircraft: AircraftScenePosition | null,
  pop: GlobeCoordinate | null
): FlowPoint[] {
  if (
    !route ||
    !snapshot ||
    !aircraft ||
    !pop ||
    !Number.isFinite(pop.latitude) ||
    Math.abs(pop.latitude) > 90 ||
    !Number.isFinite(pop.longitude) ||
    Math.abs(pop.longitude) > 180
  )
    return [];
  const popScene = globePosition(pop.latitude, pop.longitude, 2);
  const endpoints = {
    aircraft: sceneToEcefKm(aircraft.position),
    pop: sceneToEcefKm(popScene),
  };
  if (!routeIsValid(route, snapshot, endpoints)) return [];
  const space = route.ids.map((id) =>
    pointAt(snapshot, snapshot.ids.indexOf(id))
  );
  if (space.some((p) => !p.every(Number.isFinite))) return [];
  const physical = [endpoints.aircraft, ...space, endpoints.pop];
  if (
    physical
      .slice(1)
      .some(
        (p, i) =>
          segmentClearanceKm(physical[i], p) <
          (i === 0 || i === physical.length - 2 ? -1e-7 : 80 - 1e-7)
      )
  )
    return [];
  return [aircraft.position, ...space.map(ecefKmToScene), popScene];
}
export function chooseTrafficPath(
  route: OrbitalRoute | null,
  snapshot: OrbitalSnapshot | null,
  aircraft: AircraftScenePosition | null,
  pop: GlobeCoordinate | null
) {
  const orbitalPoints = projectOrbitalTrafficPath(
    route,
    snapshot,
    aircraft,
    pop
  );
  const orbital = orbitalPoints.length >= 3;
  return {
    orbital,
    points: orbital ? orbitalPoints : projectTrafficArc(aircraft, pop),
    particleKey: orbital
      ? `orbital:${route!.identity}`
      : `pop:${pop?.latitude}:${pop?.longitude}`,
  };
}
