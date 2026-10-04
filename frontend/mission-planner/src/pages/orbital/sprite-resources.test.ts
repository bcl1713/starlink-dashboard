import { expect, it, vi } from 'vitest';
import {
  createSpriteResources,
  disposeSpriteResources,
  writeSpriteSnapshots,
} from './sprite-resources';
import { spriteSnapshot } from './sprite-test-fixtures';
import { MAX_OBJECTS } from './types';

it('sprites_have_two_draw_call_and_three_buffer_caps with fixed reusable GPU arrays', () => {
  const r = createSpriteResources(MAX_OBJECTS);
  const points = Array.from(
    { length: MAX_OBJECTS },
    () => [7000, 0, 0] as const
  );
  const s = spriteSnapshot(
    points,
    points.map((_, i) => String(i + 1))
  );
  const arrays = Object.values(r.geometry.attributes).map((a) => a.array);
  expect(writeSpriteSnapshots(r, null, s, 1)).toBe(MAX_OBJECTS);
  expect(r.points.type).toBe('Points');
  expect(r.geometry.drawRange.count).toBe(MAX_OBJECTS);
  expect(r.material.depthTest).toBe(true);
  expect(r.material.depthWrite).toBe(false);
  expect(arrays.every((a) => a instanceof Float32Array)).toBe(true);
  writeSpriteSnapshots(r, s, { ...s, utcMs: 2000 }, 1);
  expect(Object.values(r.geometry.attributes).map((a) => a.array)).toEqual(
    arrays
  );
  expect(() => createSpriteResources(MAX_OBJECTS + 1)).toThrow();
  disposeSpriteResources(r);
});
it('interpolation joins only matching valid IDs in the same mount/catalog', () => {
  const r = createSpriteResources(3);
  const old = spriteSnapshot(
    [
      [7000, 0, 0],
      [7100, 0, 0],
    ],
    ['2', '1']
  );
  const current = spriteSnapshot(
    [
      [7200, 0, 0],
      [7300, 0, 0],
      [7400, 0, 0],
    ],
    ['1', '2', '3']
  );
  expect(writeSpriteSnapshots(r, old, current, 1)).toBe(3);
  expect(r.geometry.getAttribute('previous').getX(0)).toBeCloseTo(
    (7100 * 2) / 6378.137
  );
  expect(r.geometry.getAttribute('previous').getX(2)).toBe(
    r.geometry.getAttribute('position').getX(2)
  );
  writeSpriteSnapshots(
    r,
    { ...old, catalogGeneration: 'different' },
    current,
    1
  );
  expect(r.geometry.getAttribute('previous').getX(0)).toBe(
    r.geometry.getAttribute('position').getX(0)
  );
  current.valid[0] = 0;
  current.positionsKm[3] = NaN;
  expect(writeSpriteSnapshots(r, old, current, 1)).toBe(1);
  expect(r.geometry.getAttribute('eligible').getX(0)).toBe(0);
  expect(r.geometry.getAttribute('eligible').getX(1)).toBe(0);
  expect(writeSpriteSnapshots(r, old, current, 2)).toBe(0);
  expect(r.geometry.drawRange.count).toBe(0);
  disposeSpriteResources(r);
});
it('explicit disposal releases geometry/material exactly once', () => {
  const r = createSpriteResources(3);
  const geometry = vi.spyOn(r.geometry, 'dispose'),
    material = vi.spyOn(r.material, 'dispose');
  disposeSpriteResources(r);
  disposeSpriteResources(r);
  expect(geometry).toHaveBeenCalledTimes(1);
  expect(material).toHaveBeenCalledTimes(1);
});
