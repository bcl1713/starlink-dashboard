/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
  expect(screen.getByRole('status').textContent).toContain(
    'Transport Advisories Unavailable'
  );
});
it('dismisses a coverage notice across polls while retaining real advisories and rearms after recovery', () => {
  const item = {
    id: 'x',
    title: 'X-Band Service Interruption Expected',
    detail: 'Current · Modeled',
  };
  const { rerender } = render(
    <OverviewPopAdvisories
      state={{ items: [], notice: 'Transport Advisories Unavailable' }}
    />
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Dismiss transport advisory notice' })
  );
  expect(screen.queryByRole('status')).toBeNull();
  rerender(
    <OverviewPopAdvisories
      state={{ items: [item], notice: 'Transport Advisories Unavailable' }}
    />
  );
  expect(screen.getByText(item.title)).toBeTruthy();
  expect(screen.queryByText('Transport Advisories Unavailable')).toBeNull();
  rerender(
    <OverviewPopAdvisories
      state={{ items: [], notice: 'Transport Advisories Stale' }}
    />
  );
  expect(screen.queryByRole('status')).toBeNull();
  rerender(<OverviewPopAdvisories state={{ items: [], notice: null }} />);
  rerender(
    <OverviewPopAdvisories
      state={{ items: [], notice: 'Transport Advisories Unavailable' }}
    />
  );
  expect(
    screen.getByRole('button', { name: 'Dismiss transport advisory notice' })
  ).toBeTruthy();
});
it('keeps long simultaneous advisory lists keyboard reachable as a labeled scroll region', () => {
  render(
    <OverviewPopAdvisories
      state={{
        items: Array.from({ length: 12 }, (_, i) => ({
          id: String(i),
          title: `Window ${i}`,
          detail: 'Current · Modeled',
        })),
        notice: null,
      }}
    />
  );
  const region = screen.getByLabelText('Transport Advisories');
  expect(region.tabIndex).toBe(0);
  region.focus();
  expect(document.activeElement).toBe(region);
});
