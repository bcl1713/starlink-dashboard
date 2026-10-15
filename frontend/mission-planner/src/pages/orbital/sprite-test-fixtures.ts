import { snapshot } from './routing-test-fixtures';
import type { OrbitalSnapshot } from './types';
import type { FlowPoint } from '../overview-animated-flow-line-rendering';
export function spriteSnapshot(
  points: FlowPoint[] = [[7000, 0, 0]],
  ids = ['1']
): OrbitalSnapshot {
  return {
    ...snapshot(points, ids),
    utcMs: 1000,
    generation: 1,
    catalogGeneration: 'a',
    bankId: 0,
    route: null,
    updateMs: 1,
  };
}
