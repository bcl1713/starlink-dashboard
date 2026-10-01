import { describe, expect, it } from 'vitest';
import type {
  OverviewUpcomingPoi,
  OverviewUpcomingPoisResponse,
} from '@/services/overview-upcoming-pois';
import { deriveArrivalPanel, formatCountdown } from './overview-arrival';

const now = Date.parse('2026-10-01T12:00:00Z');
function poi(
  id: string,
  progress: number,
  overrides: Partial<OverviewUpcomingPoi> = {}
): OverviewUpcomingPoi {
  return {
    poi_id: id,
    name: id,
    kind: 'x_band_transition',
    latitude: 0,
    longitude: 0,
    projected_route_progress: progress,
    flight_phase: 'in_flight',
    expected_arrival_time: '2026-10-01T15:00:00Z',
    estimated_arrival_time: '2026-10-01T12:39:00Z',
    eta_seconds: 2340,
    eta_type: 'estimated',
    upcoming: true,
    map_retained: true,
    ...overrides,
  };
}
function response(
  overrides: Partial<OverviewUpcomingPoisResponse> = {}
): OverviewUpcomingPoisResponse {
  return {
    state: 'available',
    calculated_at: new Date(now).toISOString(),
    flight_phase: 'in_flight',
    scheduled_departure_time: null,
    position_observed_at: new Date(now).toISOString(),
    current_route_progress: 0,
    position_state: 'fresh',
    pois: [poi('landing', 100, { kind: 'arrival' }), poi('next', 10)],
    ...overrides,
  };
}

describe('arrival derivation', () => {
  it('selects route order across all records without hiding an untimed next event or mutating data', () => {
    const input = response({
      pois: [
        poi('later', 40),
        poi('earlier', 10, { estimated_arrival_time: null }),
        ...Array.from({ length: 5 }, (_, i) => poi(`event-${i}`, 50 + i)),
        poi('landing', 100, { kind: 'arrival' }),
      ],
    });
    const before = structuredClone(input);
    const view = deriveArrivalPanel(input, now);
    expect(view.sections.map((s) => s.name)).toEqual(['earlier', 'landing']);
    expect(view.sections[0].timing).toBeNull();
    expect(view.sections[1].timing?.countdown).toBe('39 MIN');
    expect(input).toEqual(before);
  });
  it('combines landing by identity, even if intermediate and landing names match', () => {
    expect(
      deriveArrivalPanel(
        response({ pois: [poi('landing', 100, { kind: 'arrival' })] }),
        now
      ).sections
    ).toHaveLength(1);
    const sections = deriveArrivalPanel(
      response({
        pois: [
          poi('same', 10),
          poi('arrival-id', 100, { kind: 'arrival', name: 'same' }),
        ],
      }),
      now
    ).sections;
    expect(sections).toHaveLength(2);
  });
  it.each(['stale', 'unavailable'] as const)(
    'suppresses timing for %s position while keeping known names',
    (position_state) => {
      const view = deriveArrivalPanel(response({ position_state }), now);
      expect(view.sections.every((s) => s.timing === null)).toBe(true);
      expect(view.sections.at(-1)?.name).toBe('landing');
      expect(view.exception).toMatch(/Position/);
    }
  );
  it('rechecks exact position age between polls and fails closed without provenance', () => {
    expect(
      deriveArrivalPanel(response(), now + 10_000).sections.every(
        (s) => s.timing === null
      )
    ).toBe(true);
    expect(
      deriveArrivalPanel(
        response({ position_observed_at: null }),
        now
      ).sections.every((s) => s.timing === null)
    ).toBe(true);
  });
  it('suppresses retained timing on failed refresh independently of fresh position', () => {
    expect(deriveArrivalPanel(response(), now, true).exception).toBe(
      'Arrival refresh unavailable'
    );
    expect(
      deriveArrivalPanel(response(), now, true).sections.every(
        (s) => s.timing === null
      )
    ).toBe(true);
  });
  it('uses only the explicit departure schedule, independent of GPS, before departure', () => {
    const input = response({
      flight_phase: 'pre_departure',
      position_state: 'unavailable',
      position_observed_at: null,
      scheduled_departure_time: '2026-10-01T13:39:00Z',
      pois: [poi('origin', 0, { kind: 'departure' })],
    });
    const section = deriveArrivalPanel(input, now).sections[0];
    expect(section.label).toBe('SCHEDULED DEPARTURE');
    expect(section.timing?.countdown).toBe('1 HR 39 MIN');
    expect(
      deriveArrivalPanel({ ...input, scheduled_departure_time: null }, now)
        .sections[0].timing
    ).toBeNull();
  });
  it.each([
    ['2026-10-01T11:48:00Z', '12 MIN AGO'],
    ['2026-10-01T11:59:59Z', '<1 MIN AGO'],
  ])(
    'counts up after scheduled departure %s',
    (scheduled_departure_time, countdown) => {
      const section = deriveArrivalPanel(
        response({ flight_phase: 'pre_departure', scheduled_departure_time }),
        now
      ).sections[0];
      expect(section.timing).toMatchObject({ countdown, late: true });
    }
  );
  it('does not infer landed from elapsed ETA or passed destination', () => {
    const input = response({
      pois: [
        poi('landing', 100, {
          kind: 'arrival',
          estimated_arrival_time: '2026-10-01T11:59:00Z',
        }),
      ],
    });
    expect(deriveArrivalPanel(input, now).sections[0].timing?.countdown).toBe(
      '0 MIN'
    );
    expect(
      deriveArrivalPanel({ ...input, flight_phase: 'post_arrival' }, now)
        .sections[0]
    ).toMatchObject({ label: 'LANDED', timing: null });
    expect(
      deriveArrivalPanel(
        response({
          current_route_progress: 100,
          pois: [poi('landing', 100, { kind: 'arrival', upcoming: false })],
        }),
        now
      ).sections.at(-1)?.unavailable
    ).toMatch(/passed/i);
  });
  it('does not label a destination passed when route progress is unknown', () => {
    const view = deriveArrivalPanel(
      response({
        current_route_progress: null,
        pois: [poi('landing', 100, { kind: 'arrival', upcoming: false })],
      }),
      now
    );
    expect(view.sections.at(-1)?.unavailable).toBe(
      'Arrival eligibility unavailable'
    );
  });
  it('reports absent or ambiguous destinations and missing route context', () => {
    for (const pois of [
      [poi('event', 10)],
      [poi('a', 100, { kind: 'arrival' }), poi('b', 100, { kind: 'arrival' })],
    ]) {
      expect(
        deriveArrivalPanel(response({ pois }), now).sections.at(-1)?.unavailable
      ).toBe('Destination unavailable');
    }
    expect(
      deriveArrivalPanel(response({ state: 'no_active_mission' }), now).message
    ).toBe('No active mission leg.');
  });
  it('rejects malformed estimates and shows a date across UTC midnight', () => {
    const pois = [
      poi('landing', 100, {
        kind: 'arrival',
        estimated_arrival_time: '2026-10-02T00:05:00Z',
      }),
    ];
    expect(
      deriveArrivalPanel(response({ pois }), now).sections[0].timing?.utc
    ).toBe('2026-10-02 00:05Z');
    expect(
      deriveArrivalPanel(
        response({ pois: [{ ...pois[0], estimated_arrival_time: 'invalid' }] }),
        now
      ).sections[0].timing
    ).toBeNull();
  });
  it('preserves anticipated labeling if route-based timing is returned', () => {
    const pois = [
      poi('landing', 100, { kind: 'arrival', eta_type: 'anticipated' }),
    ];
    expect(
      deriveArrivalPanel(response({ pois }), now).sections[0].timing
        ?.anticipated
    ).toBe(true);
  });
});

it.each([
  [0, '0 MIN'],
  [30_000, '<1 MIN'],
  [60_000, '1 MIN'],
  [5_940_000, '1 HR 39 MIN'],
])('formats duration %i', (ms, expected) => {
  expect(formatCountdown(ms)).toBe(expected);
});
