import { expect, it } from 'vitest';
import { popForecast } from '@/test/pop-fixtures';
import { projectPopAdvisories } from './pop-advisory-projection';
it('distinguishes old absent fields, unknown observations and a valid empty forecast', () => {
  expect(projectPopAdvisories({}).summary).toContain('unavailable');
  const projected = projectPopAdvisories({
    pop_forecast: { ...popForecast(), transitions: [] },
    pop_observation: {
      status: 'unknown',
      source: 'live',
      ip: null,
      entry: null,
    },
  });
  expect(projected.summary).toContain('No upcoming');
  expect(projected.observation).toContain('unknown');
});
it('uses only backend completion and persistent overdue/mismatch evidence', () => {
  const base = {
    pop_forecast: popForecast(),
    pop_observation: {
      status: 'known' as const,
      source: 'simulation' as const,
      ip: '192.0.2.2',
      entry: {
        ip: '192.0.2.2',
        city: 'Dallas',
        country: 'US',
        latitude: 32,
        longitude: -96,
        region: '',
      },
    },
  };
  const early = projectPopAdvisories({ ...base, pop_advisories: [] });
  expect(early.advisories).toEqual([]);
  expect(early.observation).toContain('Observed');
  expect(early.observation).toContain('Dallas');
  const overdue = projectPopAdvisories({
    ...base,
    pop_forecast: { ...base.pop_forecast, transitions: [] },
    pop_advisories: [
      {
        kind: 'overdue',
        transition_id: 'old-crossing',
        observed_pop_id: 'los-angeles',
      },
      { kind: 'mismatch', transition_id: null, observed_pop_id: 'tokyo' },
    ],
  });
  expect(overdue.advisories.join(' ')).toMatch(/Overdue.*until.*observed/);
  expect(overdue.advisories.join(' ')).toMatch(
    /any time.*calls may be interrupted/
  );
});
it('does not invent city matches for unknown or unfamiliar observed locations', () => {
  expect(
    projectPopAdvisories({
      pop_observation: {
        status: 'unknown',
        source: 'live',
        ip: '1.2.3.4',
        entry: null,
      },
    }).observation
  ).toContain('unknown');
  expect(
    projectPopAdvisories({
      pop_observation: {
        status: 'known',
        source: 'live',
        ip: '1.2.3.4',
        entry: {
          ip: '1.2.3.4',
          city: 'Unlisted City',
          country: 'ZZ',
          latitude: 0,
          longitude: 0,
        },
      },
    }).observation
  ).toContain('Unlisted City');
});
