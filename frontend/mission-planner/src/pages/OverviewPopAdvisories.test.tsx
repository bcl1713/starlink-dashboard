/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OverviewPopAdvisories } from './OverviewPopAdvisories';
afterEach(cleanup);
it('stays clear for a complete snapshot with no visible advisories', () => {
  const { container } = render(
    <OverviewPopAdvisories state={{ items: [], notice: null }} />
  );
  expect(container.textContent).toBe('');
});
it('shows simultaneous concise themed advisories without controls or diagnostics', () => {
  const { container } = render(
    <OverviewPopAdvisories
      state={{
        items: [
          {
            id: 'pop',
            title: 'Starshield Transition Window',
            detail: 'Brief Interruption Possible · Modeled',
          },
          {
            id: 'x',
            title: 'X-Band Concurrency Restriction',
            detail: 'Current · Modeled',
          },
          {
            id: 'ka',
            title: 'KA Service Interruption Expected',
            detail: 'Approaching · Planned',
          },
        ],
        notice: null,
      }}
    />
  );
  expect(screen.getByRole('status').textContent).toContain(
    'Starshield Transition Window'
  );
  expect(
    container.querySelectorAll('.overview-transport-advisory')
  ).toHaveLength(3);
  expect(container.querySelector('details, button, input, time')).toBeNull();
  expect(container.textContent).not.toMatch(
    /192\.0\.2|Observed PoP|unresolved|UTC|unavailable/
  );
});
it('communicates unavailable coverage without an all-clear or raw PoP fallback', () => {
  render(
    <OverviewPopAdvisories
      state={{ items: [], notice: 'Transport Advisories Unavailable' }}
    />
  );
  expect(screen.getByRole('status').textContent).toBe(
    'Transport Advisories Unavailable'
  );
});
