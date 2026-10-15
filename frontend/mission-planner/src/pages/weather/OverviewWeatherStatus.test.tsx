/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OverviewWeatherStatus } from './OverviewWeatherStatus';
import { readyWeather } from '@/test/weather-fixtures';
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
        detailContext: {
          generation: 1,
          settingsRevision: 1,
          manifest: readyWeather(),
        },
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

it('uses displayed source attribution without hard-coded provider labeling', () => {
  render(
    <OverviewWeatherStatus
      weather={{
        ...emptyWeatherView,
        configuredEnabled: true,
        detailContext: {
          generation: 1,
          settingsRevision: 1,
          manifest: {
            ...readyWeather(),
            source: 'fixture-radar',
            attribution: {
              label: 'Fixture radar',
              url: 'https://example.com/radar',
            },
          },
        },
      }}
    />
  );
  expect(screen.getByRole('link').textContent).toBe('Fixture radar');
  expect(screen.getByRole('link').getAttribute('href')).toBe(
    'https://example.com/radar'
  );
});
