import { expect, it } from 'vitest';
import { popForecast, partialKaContinuity } from '@/test/pop-fixtures';
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
  expect(projected.observation).toMatch(/unknown|unavailable/);
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
  expect(early.observation).toContain('Simulated PoP');
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
  expect(overdue.advisories.join(' ')).toContain('Forecast window passed');
  expect(overdue.advisories.join(' ')).toMatch(
    /does not establish a current interruption/
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
  ).toMatch(/unknown|unavailable/);
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

it('keeps unknown continuity unresolved even when numeric totals are zero', () => {
  expect(projectPopAdvisories({ call_continuity: null }).continuity).toContain(
    'unresolved'
  );
  const continuity = {
    revision: 'route-one',
    intervals: [
      {
        start_utc: '2035-03-01T23:55:00Z',
        end_utc: '2035-03-02T00:05:00Z',
        classification: 'unknown' as const,
        transition_ids: ['route-one:crossing'],
        usable_alternatives: [],
        source_ids: [],
      },
    ],
    planned_communications_outage_seconds: 0,
    pop_call_outage_seconds: 0,
    longest_call_outage_seconds: 0,
  };
  const view = projectPopAdvisories({
    pop_forecast: popForecast(),
    call_continuity: continuity,
  });
  expect(view.continuity).toContain('unresolved');
  expect(view.continuity).not.toContain('0s');
});
it('presents backend full or remaining totals and planned fallback explicitly', () => {
  const continuity = {
    revision: 'route-one',
    intervals: [
      {
        start_utc: '2035-03-01T23:55:00Z',
        end_utc: '2035-03-02T00:05:00Z',
        classification: 'x_fallback' as const,
        transition_ids: ['route-one:crossing'],
        usable_alternatives: ['X'],
        source_ids: [],
      },
    ],
    planned_communications_outage_seconds: 0,
    pop_call_outage_seconds: 0,
    longest_call_outage_seconds: 0,
  };
  const view = projectPopAdvisories({
    pop_forecast: popForecast(),
    call_continuity: continuity,
  });
  expect(view.continuity).toContain('Planned communications outage: 0s');
  expect(
    view.transitionDetails['route-one:crossing']
      .map((detail) => detail.message)
      .join(' ')
  ).toContain('Planned X-Band fallback');
  const outage = projectPopAdvisories({
    pop_forecast: popForecast(),
    call_continuity: {
      ...continuity,
      planned_communications_outage_seconds: 600,
      pop_call_outage_seconds: 600,
      longest_call_outage_seconds: 600,
      intervals: [
        {
          ...continuity.intervals[0],
          classification: 'planned_outage',
          usable_alternatives: [],
        },
      ],
    },
  });
  expect(outage.continuity).toContain('600s');
  expect(
    outage.transitionDetails['route-one:crossing']
      .map((detail) => detail.message)
      .join(' ')
  ).toContain('No secure-call transport');
});
it('rejects a stale continuity revision instead of displaying confirmed zero', () => {
  const view = projectPopAdvisories({
    pop_forecast: popForecast(),
    call_continuity: {
      revision: 'obsolete',
      intervals: [
        {
          start_utc: '2035-03-01T23:55:00Z',
          end_utc: '2035-03-02T00:05:00Z',
          classification: 'ordinary',
          transition_ids: [],
          usable_alternatives: [],
          source_ids: [],
        },
      ],
      planned_communications_outage_seconds: 0,
      pop_call_outage_seconds: 0,
      longest_call_outage_seconds: 0,
    },
  });
  expect(view.continuity).toContain('unresolved');
});

it('preserves every timed portion when Ka availability changes repeatedly within a window', () => {
  const continuity = partialKaContinuity();
  continuity.intervals = [
    { ...continuity.intervals[0], end_utc: '2035-03-01T23:57:00Z' },
    {
      ...continuity.intervals[1],
      start_utc: '2035-03-01T23:57:00Z',
      end_utc: '2035-03-02T00:00:00Z',
    },
    {
      ...continuity.intervals[0],
      start_utc: '2035-03-02T00:00:00Z',
      end_utc: '2035-03-02T00:03:00Z',
    },
    { ...continuity.intervals[1], start_utc: '2035-03-02T00:03:00Z' },
  ];
  const view = projectPopAdvisories({
    pop_forecast: popForecast(),
    call_continuity: continuity,
  });
  const details = view.transitionDetails['route-one:crossing'];
  expect(details).toHaveLength(4);
  expect(details.map((detail) => [detail.startUtc, detail.endUtc])).toEqual(
    continuity.intervals.map((interval) => [
      interval.start_utc,
      interval.end_utc,
    ])
  );
});

it('labels unverified egress as GeoIP and keeps disagreement separate from interruption risk', () => {
  const view = projectPopAdvisories({
    pop_observation: {
      status: 'known',
      source: 'live',
      ip: '192.0.2.8',
      entry: {
        ip: '192.0.2.8',
        city: 'Domestic City',
        country: 'US',
        latitude: 34,
        longitude: -84,
      },
    },
    pop_advisories: [{ kind: 'mismatch' }, { kind: 'overdue' }],
  });
  expect(view.observation).toContain('GeoIP');
  expect(view.observation).not.toContain('Observed PoP');
  expect(view.advisories.join(' ')).not.toMatch(
    /any time|until.*observed|interruption remains/
  );
});
