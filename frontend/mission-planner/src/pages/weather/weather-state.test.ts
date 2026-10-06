import { expect, it } from 'vitest';
import { frameState } from './weather-state';
it.each([
  [0, false, 'current'],
  [1200000, false, 'current'],
  [1200001, false, 'stale'],
  [3599999, false, 'stale'],
  [3600000, false, 'unavailable'],
  [1, true, 'stale'],
])(
  'classifies original observation age %s with failure %s',
  (age, failed, state) => {
    expect(frameState(100000, 100000 + Number(age), Boolean(failed))).toBe(
      state
    );
  }
);
