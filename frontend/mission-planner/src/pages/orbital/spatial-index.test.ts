import { expect, it } from 'vitest';
import { OrbitalSpatialIndex } from './spatial-index';
import { snapshot } from './routing-test-fixtures';

it('returns nearest eight admissible neighbors with numeric ID tie breaking', () => {
  const s = snapshot(
    Array.from({ length: 12 }, (_, i) => [7000, i * 100, 0] as const)
  );
  expect(new OrbitalSpatialIndex(s).neighbors(0).map((i) => s.ids[i])).toEqual([
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '8',
    '9',
  ]);
  const ties = snapshot(
    [
      [7000, 0, 0],
      [7000, 0, 0],
      [7000, 0, 0],
    ],
    ['100001', '10', '2']
  );
  expect(new OrbitalSpatialIndex(ties).neighbors(0)).toEqual([2, 1]);
});
it('rejects distance over 5000 km and unsafe chords', () => {
  const s = snapshot([
    [7000, 0, 0],
    [-7000, 0, 0],
    [12001, 0, 0],
    [12000, 0, 0],
  ]);
  expect(new OrbitalSpatialIndex(s).neighbors(0)).toEqual([3]);
});
