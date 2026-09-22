import { describe, expect, it } from 'vitest';
import {
  layoutOverviewPoiLabels,
  type ProjectedPoiLabel,
} from './overview-poi-label-layout';

function label(id: string, width = 96): ProjectedPoiLabel {
  return {
    id,
    bounds: { x: 900, y: 500, width, height: 20 },
  };
}

function overlaps(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number }
) {
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}

describe('layoutOverviewPoiLabels', () => {
  it('places eight projected generated labels without reusing an occupied box', () => {
    const result = layoutOverviewPoiLabels(
      ['departure', 'arrival', 'x-band', 'ka-entry', 'ka-exit', 'ka-swap', 'aar-start', 'aar-end'].map(
        (id, index) => label(id, 70 + index * 4)
      ),
      { width: 1920, height: 1080 }
    );

    expect(result.fallback).toBeNull();
    expect(Object.keys(result.offsets)).toHaveLength(8);

    const boxes = Object.entries(result.offsets).map(([id, offset]) => {
      const source = ['departure', 'arrival', 'x-band', 'ka-entry', 'ka-exit', 'ka-swap', 'aar-start', 'aar-end']
        .map((candidate, index) => label(candidate, 70 + index * 4))
        .find((candidate) => candidate.id === id)!;
      return {
        x: source.bounds.x + offset[0],
        y: source.bounds.y + offset[1],
        width: source.bounds.width,
        height: source.bounds.height,
      };
    });

    for (let index = 0; index < boxes.length; index += 1) {
      for (let other = index + 1; other < boxes.length; other += 1) {
        expect(overlaps(boxes[index], boxes[other])).toBe(false);
      }
    }
  });

  it('returns a readable disclosure fallback rather than overlapping labels when no candidate fits', () => {
    const result = layoutOverviewPoiLabels(
      [label('one', 70), label('two', 70)],
      { width: 80, height: 30 }
    );

    expect(result.offsets).toEqual({});
    expect(result.fallback).toEqual({ anchorId: 'one', hiddenIds: ['one', 'two'] });
  });
});
