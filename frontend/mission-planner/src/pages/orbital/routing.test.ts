import { expect, it } from 'vitest';
import {
  selectRoute,
  routeIsValid,
  emptyRoutingState,
  shortestPath,
} from './routing';
import { circle, snapshot } from './routing-test-fixtures';
import type { PropagationResult } from './types';

it('greatest_elevation_and_single_satellite ties use numeric IDs', () => {
  const s = snapshot(
    [
      [7000, 0, 0],
      [7000, 0, 0],
    ],
    ['10', '2']
  );
  const endpoints = {
    aircraft: [6388.137, 0, 0] as const,
    pop: [6378.137, 0, 0] as const,
  };
  const selected = selectRoute(s, endpoints, emptyRoutingState('catalog-a'));
  expect(selected.route?.ids).toEqual(['2']);
  expect(selected.route?.identity).toContain('catalog-a');
  expect(routeIsValid(selected.route!, s, endpoints)).toBe(true);
});
it('rejects exact 10-degree threshold and invalid endpoints', () => {
  const a = (10 * Math.PI) / 180;
  const s = snapshot([[6378.137 + 1000 * Math.sin(a), 1000 * Math.cos(a), 0]]);
  const endpoints = {
    aircraft: [6378.137, 0, 0] as const,
    pop: [6378.137, 0, 0] as const,
  };
  expect(selectRoute(s, endpoints, emptyRoutingState()).route).toBeNull();
  expect(
    selectRoute(s, { ...endpoints, aircraft: null }, emptyRoutingState()).route
  ).toBeNull();
  expect(
    selectRoute(s, { ...endpoints, pop: [NaN, 0, 0] }, emptyRoutingState())
      .route
  ).toBeNull();
});
it('neighbors_and_shortest_bounded_path chooses geometric shortest and stable ties', () => {
  const s = snapshot([circle(0), circle(20), circle(40), circle(60)]);
  const endpoints = {
    aircraft: circle(0, 6388.137),
    pop: circle(60, 6378.137),
  };
  const result = selectRoute(s, endpoints, emptyRoutingState());
  expect(result.route?.ids).toEqual(['1', '2', '4']);
  expect(new Set(result.route?.ids).size).toBe(result.route?.ids.length);
  expect(result.expansions).toBeLessThanOrEqual(2048);
  expect(routeIsValid(result.route!, s, endpoints)).toBe(true);
  s.valid[1] = 0;
  expect(routeIsValid(result.route!, s, endpoints)).toBe(false);
});
it('invalid clearance, catalog expiry and PoP changes bypass an old route', () => {
  const s = snapshot([circle(0), circle(30), circle(60)]);
  const endpoints = {
    aircraft: circle(0, 6378.137),
    pop: circle(60, 6378.137),
  };
  const result = selectRoute(s, endpoints, emptyRoutingState());
  expect(result.route).not.toBeNull();
  expect(
    routeIsValid(result.route!, s, { ...endpoints, pop: circle(61, 6378.137) })
  ).toBe(false);
  s.positionsKm.set(circle(180), 3);
  expect(routeIsValid(result.route!, s, endpoints)).toBe(false);
  expect(selectRoute(s, endpoints, result.state).route).toBeNull();
});
it('polar and antimeridian endpoints remain physical', () => {
  const polar = snapshot([[0, 0, 7000]]);
  expect(
    selectRoute(
      polar,
      { aircraft: [0, 0, 6388], pop: [0, 0, 6378.137] },
      emptyRoutingState()
    ).route?.ids
  ).toEqual(['1']);
  const s = snapshot([circle(179), circle(-179)]);
  expect(
    selectRoute(
      s,
      { aircraft: circle(179, 6378.137), pop: circle(-179, 6378.137) },
      emptyRoutingState()
    ).route
  ).not.toBeNull();
});

it('a confirmed endpoint handover cannot retain a route using the previous access satellite', () => {
  const s = snapshot([circle(0), circle(10)]);
  const initialEndpoints = {
    aircraft: circle(0, 6378.137),
    pop: circle(0, 6378.137),
  };
  const initial = selectRoute(s, initialEndpoints, emptyRoutingState());
  const moved = { ...initialEndpoints, aircraft: circle(10, 6378.137) };
  const first = selectRoute(s, moved, initial.state);
  expect(first.route?.ids[0]).toBe('1');
  const second = selectRoute(s, moved, first.state);
  expect(second.state.access).toBe('2');
  expect(second.route?.ids[0]).toBe('2');
});

it('route hysteresis compares lengths at the same UTC and requires two selections', () => {
  const middle = circle(15);
  const s = snapshot([circle(0), [middle[0], middle[1], 2000], circle(30)]);
  const endpoints = {
    aircraft: circle(0, 6378.137),
    pop: circle(30, 6378.137),
  };
  const initial = selectRoute(s, endpoints, emptyRoutingState());
  const route = {
    ids: ['1', '2', '3'],
    lengthKm: 1,
    identity: JSON.stringify(['', ['1', '2', '3'], endpoints.pop]),
  };
  expect(routeIsValid(route, s, endpoints)).toBe(true);
  const first = selectRoute(s, endpoints, { ...initial.state, route });
  expect(first.route?.ids).toEqual(['1', '2', '3']);
  expect(first.route!.lengthKm).toBeGreaterThan(1);
  const second = selectRoute(s, endpoints, first.state);
  expect(second.route?.ids).toEqual(['1', '3']);
});
it('depth-constrained search refuses a ninth node and exhausted budgets', () => {
  const s = snapshot(
    Array.from({ length: 9 }, (_, i) => [7000, i, 0] as const)
  );
  const chain = { neighbors: (i: number) => (i < 8 ? [i + 1] : []) };
  expect(shortestPath(s, chain, 0, 8).route).toBeNull();
  expect(shortestPath(s, chain, 0, 7).route).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  const large: PropagationResult = snapshot(
    Array.from({ length: 4096 }, (_, i) => [7000, i / 1000, 0] as const)
  );
  const graph = {
    neighbors: (i: number) =>
      Array.from({ length: 8 }, (_, j) => (i * 8 + j + 1) % 4095).filter(
        (n) => n !== i
      ),
  };
  const exhausted = shortestPath(large, graph, 0, 4095);
  expect(exhausted.route).toBeNull();
  expect(exhausted.expansions).toBe(2048);
  expect(exhausted.exhausted).toBe(true);
});

it('retains a physically valid route when the moving nearest-eight graph has no replacement', () => {
  const points = [
    circle(0),
    circle(30),
    ...Array.from({ length: 8 }, (_, i) => circle(180 + i)),
  ];
  const s = snapshot(points);
  const endpoints = {
    aircraft: circle(0, 6378.137),
    pop: circle(30, 6378.137),
  };
  const first = selectRoute(s, endpoints, emptyRoutingState('same'));
  expect(first.route?.ids).toEqual(['1', '2']);
  for (let i = 0; i < 8; i++)
    s.positionsKm.set(circle(0.01 + i * 0.001), (i + 2) * 3);
  expect(routeIsValid(first.route!, s, endpoints)).toBe(true);
  const next = selectRoute(s, endpoints, first.state);
  expect(next.route?.identity).toBe(first.route!.identity);
  expect(next.fallbackReason).toBeNull();
  expect(next.expansions).toBeLessThanOrEqual(2048);
});
