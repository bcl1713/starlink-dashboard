/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { popForecast } from '@/test/pop-fixtures';
import { OverviewPopAdvisories } from './OverviewPopAdvisories';
afterEach(cleanup);
it('renders backend active advisories and observed PoP separately from predicted UTC windows', () => {
  render(
    <OverviewPopAdvisories
      status={{
        timestamp: new Date().toISOString(),
        pop_forecast: popForecast(),
        pop_observation: {
          status: 'known',
          source: 'simulation',
          ip: '192.0.2.2',
          entry: {
            ip: '192.0.2.2',
            city: 'Tokyo',
            country: 'JP',
            latitude: 35,
            longitude: 139,
          },
        },
        pop_advisories: [{ kind: 'mismatch' }],
      }}
      nowMs={Date.parse('2035-03-02T00:00:00Z')}
      realNowMs={Date.now()}
      refreshFailed={false}
    />
  );
  expect(
    (
      screen
        .getByText(/PoP forecast ·/)
        .closest('details') as HTMLDetailsElement
    ).open
  ).toBe(true);
  expect(screen.getByText(/Observed PoP: Tokyo, JP/)).not.toBeNull();
  expect(screen.getByText(/any time; calls may be interrupted/)).not.toBeNull();
  expect(
    screen.getByText(/Estimated crossing UTC 2035-03-02 00:00:00/)
  ).not.toBeNull();
});
it('marks cached status stale on refresh failure without asserting completion', () => {
  render(
    <OverviewPopAdvisories
      status={{
        timestamp: new Date().toISOString(),
        pop_forecast: popForecast(),
        pop_advisories: [{ kind: 'overdue' }],
      }}
      nowMs={0}
      realNowMs={Date.now()}
      refreshFailed
    />
  );
  expect(screen.getByText(/last known/)).not.toBeNull();
  expect(screen.getByText(/Overdue/)).not.toBeNull();
});
