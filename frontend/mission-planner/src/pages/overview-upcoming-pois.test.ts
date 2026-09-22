import { describe, expect, it } from 'vitest';
import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';
import { overviewPoiView, urgencyColor } from './overview-upcoming-pois';

const now = new Date('2026-09-22T12:00:00.000Z');

function poi(
  poi_id: string,
  overrides: Partial<OverviewUpcomingPoi> = {}
): OverviewUpcomingPoi {
  return {
    poi_id,
    name: poi_id,
    kind: 'x_band_transition',
    latitude: 41.2,
    longitude: -95.9,
    expected_arrival_time: '2026-09-22T11:00:00.000Z',
    eta_seconds: 60,
    estimated_arrival_time: '2026-09-22T12:01:00.000Z',
    eta_type: 'estimated',
    upcoming: true,
    map_retained: true,
    ...overrides,
  };
}

describe('urgencyColor', () => {
  it.each([
    [60 * 60 * 1000, '#22c55e'],
    [45 * 60 * 1000, '#8fd13a'],
    [30 * 60 * 1000, '#facc15'],
    [15 * 60 * 1000, '#f28b2d'],
    [0, '#ef4444'],
  ])('uses the approved colour interpolation at %i ms', (remaining, colour) => {
    expect(
      urgencyColor(new Date(now.valueOf() + remaining).toISOString(), now)
    ).toBe(colour);
  });

  it('uses slate for unavailable or invalid timing and red for overdue estimates', () => {
    expect(urgencyColor(null, now)).toBe('#64748b');
    expect(urgencyColor('not-a-date', now)).toBe('#64748b');
    expect(urgencyColor('2026-09-22T11:59:59.000Z', now)).toBe('#ef4444');
  });

  it('derives colour only from the dynamic estimated arrival time', () => {
    const delayedEstimate = new Date(now.valueOf() + 60 * 60 * 1000).toISOString();
    expect(urgencyColor(delayedEstimate, now)).toBe('#22c55e');
  });
});

describe('overviewPoiView', () => {
  it('uses slate for unavailable timing and retains untimed operational markers', () => {
    const untimedXTransition = poi('untimed-x', {
      expected_arrival_time: '2026-09-22T12:01:00.000Z',
      eta_seconds: null,
      estimated_arrival_time: null,
      eta_type: null,
      upcoming: false,
    });

    const view = overviewPoiView([untimedXTransition], now);

    expect(urgencyColor(null, now)).toBe('#64748b');
    expect(view.markers).toEqual([untimedXTransition]);
    expect(view.topFive).toEqual([]);
  });

  it('uses only map-retained finite-coordinate markers and five table-upcoming rows in server order', () => {
    const mixedRecords = [
      poi('passed-x', { upcoming: false }),
      poi('not-retained', { map_retained: false, upcoming: false }),
      poi('invalid-latitude', { latitude: Number.NaN, upcoming: false }),
      poi('first-upcoming'),
      poi('untimed-upcoming', {
        estimated_arrival_time: null,
        eta_seconds: null,
        eta_type: null,
      }),
      poi('third-upcoming'),
      poi('fourth-upcoming'),
      poi('fifth-upcoming'),
      poi('sixth-upcoming'),
    ];

    const view = overviewPoiView(mixedRecords, now);

    expect(view.markers.map(({ poi_id }) => poi_id)).toEqual([
      'passed-x',
      'invalid-latitude',
      'first-upcoming',
      'untimed-upcoming',
      'third-upcoming',
      'fourth-upcoming',
      'fifth-upcoming',
      'sixth-upcoming',
    ].filter((poiId) => poiId !== 'invalid-latitude'));
    expect(view.topFive.map(({ poi_id }) => poi_id)).toEqual([
      'first-upcoming',
      'untimed-upcoming',
      'third-upcoming',
      'fourth-upcoming',
      'fifth-upcoming',
    ]);
  });
});
