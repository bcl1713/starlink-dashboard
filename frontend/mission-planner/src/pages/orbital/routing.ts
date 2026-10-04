import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import {
  aboveMinimum,
  distance,
  elevationDegrees,
  physicalEndpoint,
  pointAt,
  segmentClearanceKm,
} from './geometry';
import { advanceHysteresis, type Challenger } from './hysteresis';
import { OrbitalSpatialIndex } from './spatial-index';
import type {
  OrbitalEndpoints,
  OrbitalRoute,
  PropagationResult,
} from './types';

export interface RoutingState {
  catalogGeneration: string;
  access: string | null;
  egress: string | null;
  accessChallenger: Challenger | null;
  egressChallenger: Challenger | null;
  route: OrbitalRoute | null;
  routeChallenger: Challenger | null;
}
export interface RoutingSelection {
  route: OrbitalRoute | null;
  state: RoutingState;
  fallbackReason: string | null;
  expansions: number;
}
export function emptyRoutingState(catalogGeneration = ''): RoutingState {
  return {
    catalogGeneration,
    access: null,
    egress: null,
    accessChallenger: null,
    egressChallenger: null,
    route: null,
    routeChallenger: null,
  };
}
function endpointSelection(
  snapshot: PropagationResult,
  endpoint: FlowPoint,
  current: string | null,
  previous: Challenger | null
) {
  const choices = snapshot.ids
    .map((id, index) => ({
      id,
      elevation: snapshot.valid[index]
        ? elevationDegrees(endpoint, pointAt(snapshot, index))
        : -90,
    }))
    .filter((c) => aboveMinimum(c.elevation))
    .sort((a, b) => b.elevation - a.elevation || Number(a.id) - Number(b.id));
  const retained = choices.find((c) => c.id === current),
    best = choices[0];
  return advanceHysteresis(
    current,
    best?.id ?? null,
    (best?.elevation ?? -90) - (retained?.elevation ?? -90),
    5,
    previous,
    Boolean(retained)
  );
}
interface SearchState {
  index: number;
  path: number[];
  length: number;
}
function compare(a: SearchState, b: SearchState, s: PropagationResult): number {
  if (Math.abs(a.length - b.length) > 1e-9) return a.length - b.length;
  for (let i = 0; i < Math.min(a.path.length, b.path.length); i++) {
    const difference = Number(s.ids[a.path[i]]) - Number(s.ids[b.path[i]]);
    if (difference) return difference;
  }
  return a.path.length - b.path.length;
}
export function shortestPath(
  snapshot: PropagationResult,
  index: { neighbors: (index: number) => number[] },
  start: number,
  end: number
): { route: number[] | null; expansions: number; exhausted: boolean } {
  const heap: SearchState[] = [];
  const best = new Map<string, SearchState>();
  const push = (state: SearchState) => {
    heap.push(state);
    let n = heap.length - 1;
    while (n) {
      const parent = (n - 1) >> 1;
      if (compare(heap[parent], heap[n], snapshot) <= 0) break;
      [heap[parent], heap[n]] = [heap[n], heap[parent]];
      n = parent;
    }
  };
  const pop = () => {
    const first = heap[0],
      last = heap.pop()!;
    if (heap.length) {
      heap[0] = last;
      let n = 0;
      while (true) {
        let smallest = n;
        for (const child of [n * 2 + 1, n * 2 + 2])
          if (
            child < heap.length &&
            compare(heap[child], heap[smallest], snapshot) < 0
          )
            smallest = child;
        if (smallest === n) break;
        [heap[smallest], heap[n]] = [heap[n], heap[smallest]];
        n = smallest;
      }
    }
    return first;
  };
  const initial = { index: start, path: [start], length: 0 };
  push(initial);
  best.set(`${start}:1`, initial);
  let expansions = 0;
  while (heap.length && expansions < 2048) {
    const current = pop();
    expansions++;
    if (best.get(`${current.index}:${current.path.length}`) !== current)
      continue;
    if (current.index === end)
      return { route: current.path, expansions, exhausted: false };
    if (current.path.length >= 8) continue;
    for (const neighbor of index.neighbors(current.index)) {
      if (current.path.includes(neighbor)) continue;
      const next = {
        index: neighbor,
        path: [...current.path, neighbor],
        length:
          current.length +
          distance(
            pointAt(snapshot, current.index),
            pointAt(snapshot, neighbor)
          ),
      };
      const key = `${neighbor}:${next.path.length}`,
        old = best.get(key);
      if (!old || compare(next, old, snapshot) < 0) {
        best.set(key, next);
        push(next);
      }
    }
  }
  return { route: null, expansions, exhausted: heap.length > 0 };
}
export function routeLength(
  route: OrbitalRoute,
  snapshot: PropagationResult,
  endpoints: OrbitalEndpoints
): number {
  if (!endpoints.aircraft || !endpoints.pop) return Infinity;
  const points = [
    endpoints.aircraft,
    ...route.ids.map((id) => pointAt(snapshot, snapshot.ids.indexOf(id))),
    endpoints.pop,
  ];
  return points
    .slice(1)
    .reduce((sum, point, i) => sum + distance(points[i], point), 0);
}
export function routeIsValid(
  route: OrbitalRoute,
  snapshot: PropagationResult,
  endpoints: OrbitalEndpoints
): boolean {
  if (
    !physicalEndpoint(endpoints.aircraft) ||
    !physicalEndpoint(endpoints.pop) ||
    !route.ids.length ||
    route.ids.length > 8 ||
    new Set(route.ids).size !== route.ids.length
  )
    return false;
  try {
    const [generation, ids, pop] = JSON.parse(route.identity);
    if (
      JSON.stringify(ids) !== JSON.stringify(route.ids) ||
      JSON.stringify(pop) !== JSON.stringify(endpoints.pop)
    )
      return false;
    if (
      'catalogGeneration' in snapshot &&
      snapshot.catalogGeneration !== generation
    )
      return false;
  } catch {
    return false;
  }
  const indices = route.ids.map((id) => snapshot.ids.indexOf(id));
  if (indices.some((i) => i < 0 || !snapshot.valid[i])) return false;
  const points = indices.map((i) => pointAt(snapshot, i));
  if (
    !aboveMinimum(elevationDegrees(endpoints.aircraft, points[0])) ||
    !aboveMinimum(elevationDegrees(endpoints.pop, points.at(-1)!))
  )
    return false;
  return points
    .slice(1)
    .every(
      (point, i) =>
        distance(points[i], point) <= 5000 + 1e-9 &&
        segmentClearanceKm(points[i], point) >= 80 - 1e-9
    );
}
export function selectRoute(
  snapshot: PropagationResult,
  endpoints: OrbitalEndpoints,
  previous: RoutingState
): RoutingSelection {
  const state = { ...previous };
  const fallback = (reason: string, expansions = 0): RoutingSelection => ({
    route: null,
    state: { ...state, route: null, routeChallenger: null },
    fallbackReason: reason,
    expansions,
  });
  if (!physicalEndpoint(endpoints.aircraft) || !physicalEndpoint(endpoints.pop))
    return fallback('invalid-endpoints');
  const access = endpointSelection(
      snapshot,
      endpoints.aircraft,
      state.access,
      state.accessChallenger
    ),
    egress = endpointSelection(
      snapshot,
      endpoints.pop,
      state.egress,
      state.egressChallenger
    );
  state.access = access.selected;
  state.accessChallenger = access.challenger;
  state.egress = egress.selected;
  state.egressChallenger = egress.challenger;
  if (!state.access || !state.egress) return fallback('disconnected');
  const current =
    state.route &&
    state.route.ids[0] === state.access &&
    state.route.ids.at(-1) === state.egress &&
    routeIsValid(state.route, snapshot, endpoints)
      ? {
          ...state.route,
          lengthKm: routeLength(state.route, snapshot, endpoints),
        }
      : null;
  const found = shortestPath(
    snapshot,
    new OrbitalSpatialIndex(snapshot),
    snapshot.ids.indexOf(state.access),
    snapshot.ids.indexOf(state.egress)
  );
  if (!found.route && current) {
    state.route = current;
    state.routeChallenger = null;
    return {
      route: current,
      state,
      fallbackReason: null,
      expansions: found.expansions,
    };
  }
  if (!found.route)
    return fallback(
      found.exhausted ? 'search-budget' : 'disconnected',
      found.expansions
    );
  const ids = found.route.map((index) => snapshot.ids[index]);
  const candidate: OrbitalRoute = {
    ids,
    lengthKm: 0,
    identity: JSON.stringify([state.catalogGeneration, ids, endpoints.pop]),
  };
  candidate.lengthKm = routeLength(candidate, snapshot, endpoints);
  const selected = advanceHysteresis(
    current?.identity ?? null,
    candidate.identity,
    current ? (current.lengthKm - candidate.lengthKm) / current.lengthKm : 1,
    0.1,
    state.routeChallenger,
    Boolean(current)
  );
  state.route = selected.selected === candidate.identity ? candidate : current;
  state.routeChallenger = selected.challenger;
  return {
    route: state.route,
    state,
    fallbackReason: null,
    expansions: found.expansions,
  };
}
