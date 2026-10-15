import { describe, expect, it } from 'vitest';
import { motionOffsetPixels } from './overview-metric-motion';

const base = { widthPixels: 400, windowSeconds: 1800, bufferSeconds: 7.5 };
describe('motionOffsetPixels', () => {
  it.each([
    [0, 0],
    [2.5, -(2.5 / 1800) * 400],
    [5, -(5 / 1800) * 400],
    [12, -(7.5 / 1800) * 400],
    [-2, 0],
  ])('bounds elapsed %s seconds to %s pixels', (elapsedSeconds, expected) => {
    expect(motionOffsetPixels({ ...base, elapsedSeconds })).toBeCloseTo(
      expected
    );
  });
  it('stops on zero width, clock reversal and non-finite inputs', () => {
    for (const input of [
      { ...base, elapsedSeconds: 5, widthPixels: 0 },
      { ...base, elapsedSeconds: Number.NaN },
      { ...base, elapsedSeconds: Infinity },
      { ...base, elapsedSeconds: 5, windowSeconds: 0 },
      { ...base, elapsedSeconds: 5, widthPixels: Infinity },
      { ...base, elapsedSeconds: 5, bufferSeconds: NaN },
    ])
      expect(motionOffsetPixels(input)).toBe(0);
  });
  it.each([
    [400, 1, -40 / 3],
    [400, 5, -200 / 3],
    [400, 8, -100],
    [300, 1, -10],
    [300, 5, -50],
    [300, 8, -75],
  ])(
    'uses measured width %s at elapsed %ss without passing overscan',
    (widthPixels, elapsedSeconds, expected) => {
      expect(
        motionOffsetPixels({
          widthPixels,
          elapsedSeconds,
          windowSeconds: 30,
          bufferSeconds: 7.5,
        })
      ).toBeCloseTo(expected);
    }
  );
  it('rebase preserves the same position for a fresh poll', () => {
    const oldEnd = 120;
    const newEnd = 125;
    const now = 125;
    const oldPosition =
      oldEnd -
      7.5 -
      (motionOffsetPixels({ ...base, elapsedSeconds: now - oldEnd }) / 400) *
        1800;
    const newPosition =
      newEnd -
      7.5 -
      (motionOffsetPixels({ ...base, elapsedSeconds: now - newEnd }) / 400) *
        1800;
    expect(oldPosition).toBe(newPosition);
  });
});
