// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AviationStatus } from './AviationStatus';
import { emptyAviationView } from './aviation-controller';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW, station, advisory, collection, weatherValues } from './fixtures';
afterEach(cleanup);
it('reports unknown coverage, SI observations, passive forecast alternatives and textual hazards', () => {
  const taf = station(true);
  taf.properties.forecast_groups.push({
    ...weatherValues,
    time_becoming_ms: null,
    change_type: 'TEMPO' as never,
    probability: 30 as never,
    valid_from_ms: NOW + 60000,
    valid_to_ms: NOW + 3600000,
  });
  const a = advisory();
  a.geometry = null as unknown as typeof a.geometry;
  render(
    <AviationStatus
      view={{
        ...emptyAviationView,
        now: NOW,
        layers: {
          metar: {
            state: 'stale',
            data: parseAviationFeatures(collection([station()]), 'metar'),
          },
          taf: {
            state: 'current',
            data: parseAviationFeatures(collection([taf]), 'taf'),
          },
          sigmet: {
            state: 'current',
            data: parseAviationFeatures(collection([a]), 'sigmet'),
          },
        },
      }}
    />
  );
  expect(
    screen.getByLabelText('Aviation weather status').textContent
  ).toContain('Coverage unknown');
  expect(
    screen.getByLabelText('Aviation weather status').textContent
  ).toContain('Forecast alternative TEMPO 30%');
  expect(
    screen.getByLabelText('Aviation weather status').textContent
  ).toContain('1 unlocated');
  expect(
    screen.getByLabelText('Aviation weather status').textContent
  ).toContain('5 m/s');
  expect(screen.queryByRole('switch')).toBeNull();
});
it('uses later active FM values instead of the expired initial TAF group', () => {
  const taf = station(true);
  taf.properties.forecast_groups[0].valid_to_ms = NOW + 60000;
  taf.properties.forecast_groups.push({
    ...weatherValues,
    time_becoming_ms: null,
    wind_speed_mps: 15,
    change_type: 'FM' as never,
    probability: null,
    valid_from_ms: NOW + 60000,
    valid_to_ms: NOW + 3600000,
  });
  render(
    <AviationStatus
      view={{
        ...emptyAviationView,
        now: NOW + 60000,
        layers: {
          ...emptyAviationView.layers,
          taf: {
            state: 'current',
            data: parseAviationFeatures(collection([taf]), 'taf'),
          },
        },
      }}
    />
  );
  expect(
    screen.getByLabelText('Aviation weather status').textContent
  ).toContain('15 m/s');
});

it('labels fractional-millisecond timestamps explicitly as UTC without losing precision', () => {
  const report = station();
  report.properties.observed_at_ms = NOW - 60000 + 123;
  const data = parseAviationFeatures(
    { ...collection([report]), retrieved_at_ms: NOW + 123 },
    'metar'
  );
  render(
    <AviationStatus
      view={{
        ...emptyAviationView,
        now: NOW + 123,
        layers: {
          ...emptyAviationView.layers,
          metar: { state: 'current', data },
        },
      }}
    />
  );
  const status = screen.getByLabelText('Aviation weather status');
  expect(status.textContent).toContain('Observed 2026-10-06T11:59:00.123 UTC');
  expect(status.textContent).toContain('retrieved 2026-10-06T12:00:00.123 UTC');
  expect(status.textContent).not.toContain('.123Z');
});
