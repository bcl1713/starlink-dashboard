import { expect, it } from 'vitest';
import { advanceHysteresis } from './hysteresis';

it.each([5, 0.1])(
  'requires two consecutive qualifying selections at threshold %s',
  (threshold) => {
    const first = advanceHysteresis('a', 'b', threshold, threshold, null, true);
    expect(first.selected).toBe('a');
    const second = advanceHysteresis(
      'a',
      'b',
      threshold,
      threshold,
      first.challenger,
      true
    );
    expect(second.selected).toBe('b');
    expect(
      advanceHysteresis('a', 'b', threshold - 0.001, threshold, null, true)
        .selected
    ).toBe('a');
    expect(
      advanceHysteresis('a', 'c', threshold, threshold, first.challenger, true)
        .selected
    ).toBe('a');
  }
);
it('invalidity bypasses hysteresis and no replacement clears selection', () => {
  expect(advanceHysteresis('a', 'b', 0, 5, null, false).selected).toBe('b');
  expect(advanceHysteresis('a', null, 0, 5, null, false).selected).toBeNull();
});
