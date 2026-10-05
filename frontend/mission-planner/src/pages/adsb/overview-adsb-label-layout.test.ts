import { expect, it } from 'vitest';
import { layoutAdsbLabels } from './overview-adsb-label-layout';
it('keeps every coincident identity instead of aggregation, avoiding reserved areas where possible', () => {
  const labels = Array.from({ length: 50 }, (_, i) => ({
    id: i.toString(),
    bounds: { x: 400, y: 250, width: 220, height: 24 },
  }));
  const offsets = layoutAdsbLabels(labels, { width: 1920, height: 1080 }, [
    { x: 400, y: 250, width: 300, height: 200 },
  ]);
  expect(Object.keys(offsets)).toHaveLength(50);
  expect(new Set(Object.values(offsets).map((p) => p.join(','))).size).toBe(50);
  expect(offsets['0']).not.toEqual([0, 0]);
});
it('keeps long labels and all identities even when the viewport cannot fit everything', () => {
  const labels = [
    { id: 'A', bounds: { x: 1, y: 1, width: 900, height: 24 } },
    { id: 'B', bounds: { x: 1, y: 1, width: 900, height: 24 } },
  ];
  const result = layoutAdsbLabels(labels, { width: 390, height: 844 }, []);
  expect(Object.keys(result)).toEqual(['A', 'B']);
  for (const offset of Object.values(result))
    expect(offset.every(Number.isFinite)).toBe(true);
});
