import { describe, expect, it } from 'vitest';
import { nightSideFactor } from './night-side-factor';

describe('nightSideFactor', () => {
  it('hides city lights on the sun-facing side', () => {
    expect(nightSideFactor(1)).toBe(0);
  });

  it('shows city lights on the night-facing side', () => {
    expect(nightSideFactor(-1)).toBe(1);
  });

  it('softens city lights halfway through the terminator', () => {
    expect(nightSideFactor(0)).toBeCloseTo(0.5, 10);
  });
});
