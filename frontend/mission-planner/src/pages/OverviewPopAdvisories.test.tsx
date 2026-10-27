/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { popForecast } from '@/test/pop-fixtures';
import { OverviewPopAdvisories } from './OverviewPopAdvisories';
afterEach(cleanup);
const now = Date.now();
const base = {
  timestamp: new Date(now).toISOString(),
  pop_forecast: popForecast(),
};
it('keeps the customer display clear outside an active advisory', () => {
  const { container } = render(
    <OverviewPopAdvisories
      status={base}
      realNowMs={now}
      refreshFailed={false}
    />
  );
  expect(container.textContent).toBe('');
});
it('shows only a concise themed transition advisory without diagnostic details', () => {
  const { container } = render(
    <OverviewPopAdvisories
      status={{
        ...base,
        call_continuity: null,
        pop_advisories: [{ kind: 'window' }],
        pop_observation: {
          status: 'known',
          source: 'simulation',
          ip: '192.0.2.2',
          entry: null,
        },
      }}
      realNowMs={now}
      refreshFailed={false}
    />
  );
  expect(screen.getByRole('status').textContent).toMatch(
    /Starshield transition window/
  );
  expect(screen.getByText('Brief interruption possible')).not.toBeNull();
  expect(
    container.querySelector('.overview-starshield-advisory')
  ).not.toBeNull();
  expect(container.querySelector('details, button, input')).toBeNull();
  expect(container.textContent).not.toMatch(
    /192\.0\.2|Observed PoP|Remaining mission|unresolved|UTC|predicted/
  );
});
it('does not turn missing observations or refresh failure into a customer debug warning', () => {
  const { container } = render(
    <OverviewPopAdvisories
      status={{ ...base, pop_advisories: [{ kind: 'observation_unknown' }] }}
      realNowMs={now}
      refreshFailed
    />
  );
  expect(container.textContent).toBe('');
});
it('keeps forecast disagreement and historical overdue forecasts off the interruption display', () => {
  const { container } = render(
    <OverviewPopAdvisories
      status={{
        ...base,
        pop_advisories: [{ kind: 'mismatch' }, { kind: 'overdue' }],
      }}
      realNowMs={now}
      refreshFailed={false}
    />
  );
  expect(container.textContent).toBe('');
});
