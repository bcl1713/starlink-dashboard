import { expect, it } from 'vitest';
import { selectRoute, emptyRoutingState } from './routing';
import { OrbitalSpatialIndex } from './spatial-index';
import { snapshot } from './routing-test-fixtures';

it('maximum_catalog_routing_is_bounded for disconnected dense islands', () => {
  const points = Array.from(
    { length: 16384 },
    (_, i) => [i < 8192 ? 7000 : -7000, (i % 8192) / 1000, 0] as const
  );
  const s = snapshot(points);
  const index = new OrbitalSpatialIndex(s);
  expect(index.nodeCount).toBe(16384);
  expect(index.neighbors(0)).toHaveLength(8);
  const result = selectRoute(
    s,
    { aircraft: [6378.137, 0, 0], pop: [-6378.137, 0, 0] },
    emptyRoutingState()
  );
  expect(result.route).toBeNull();
  expect(result.expansions).toBeLessThanOrEqual(2048);
});
