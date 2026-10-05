/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OverviewWeatherStatus } from './OverviewWeatherStatus';
import { emptyWeatherView } from './weather-state';
afterEach(cleanup);
it('is absent by default and supplies passive time, coverage and attribution when enabled', () => {
  const view = render(<OverviewWeatherStatus weather={emptyWeatherView} />);
  expect(screen.queryByLabelText('Weather status')).toBeNull();
  view.rerender(
    <OverviewWeatherStatus
      weather={{
        ...emptyWeatherView,
        configuredEnabled: true,
        state: 'stale',
        frameTimeMs: 1791244200000,
        ageMs: 600000,
      }}
    />
  );
  const panel = screen.getByLabelText('Weather status');
  expect(panel.textContent).toContain('Stale');
  expect(panel.textContent).toContain('10 min');
  expect(panel.textContent).toContain('UTC');
  expect(panel.textContent).toContain('No radar coverage');
  expect(within(panel).getByRole('link').getAttribute('href')).toBe(
    'https://www.rainviewer.com/'
  );
  expect(within(panel).queryByRole('button')).toBeNull();
  expect(within(panel).queryByRole('switch')).toBeNull();
});
