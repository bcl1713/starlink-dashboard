import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { formatOverviewClock, useOverviewClock } from './useOverviewClock';

describe('overview clock formatting', () => {
  it('formats UTC and DST offsets exactly', () => {
    expect(
      formatOverviewClock(new Date('2026-01-02T03:04:05Z'), 'UTC')
    ).toEqual({
      dateTime: '2026-01-02T03:04:05.000Z',
      time: '03:04:05',
      offset: 'UTC+00:00',
      zoneAndOffset: 'UTC (UTC+00:00)',
    });
    expect(
      formatOverviewClock(new Date('2026-03-08T06:59:59Z'), 'America/New_York')
        ?.time
    ).toBe('01:59:59');
    expect(
      formatOverviewClock(new Date('2026-03-08T07:00:00Z'), 'America/New_York')
    ).toMatchObject({ time: '03:00:00', offset: 'UTC-04:00' });
    expect(
      formatOverviewClock(new Date('2026-11-01T05:59:59Z'), 'America/New_York')
    ).toMatchObject({ time: '01:59:59', offset: 'UTC-04:00' });
    expect(
      formatOverviewClock(new Date('2026-11-01T06:00:00Z'), 'America/New_York')
    ).toMatchObject({ time: '01:00:00', offset: 'UTC-05:00' });
  });

  it('returns null for invalid dates, invalid zones, and throwing Intl', () => {
    expect(formatOverviewClock(new Date(Number.NaN), 'UTC')).toBeNull();
    expect(formatOverviewClock(new Date(), 'No/Such')).toBeNull();
    const spy = vi
      .spyOn(Intl, 'DateTimeFormat')
      .mockImplementation(function () {
        throw new Error('intl');
      } as never);
    expect(formatOverviewClock(new Date(), 'UTC')).toBeNull();
    spy.mockRestore();
  });

  it('guards resolvedOptions and formatToParts traps before formatting', () => {
    const now = new Date('2026-01-02T03:04:05Z');
    const trapCases: Array<() => object> = [
      function () {
        return {
          get resolvedOptions() {
            throw new Error('resolved getter');
          },
          formatToParts: () => [
            { type: 'hour', value: '03' },
            { type: 'minute', value: '04' },
            { type: 'second', value: '05' },
            { type: 'timeZoneName', value: 'GMT' },
          ],
        };
      },
      function () {
        return {
          resolvedOptions: () => {
            throw new Error('resolved call');
          },
          formatToParts: () => [],
        };
      },
      function () {
        return {
          resolvedOptions: () => null,
          formatToParts: () => [],
        };
      },
      function () {
        return {
          resolvedOptions: () =>
            new Proxy(
              {},
              {
                get() {
                  throw new Error('resolved return trap');
                },
              }
            ),
          formatToParts: () => [],
        };
      },
      function () {
        return {
          resolvedOptions: () => ({ timeZone: 'UTC' }),
          get formatToParts() {
            throw new Error('parts getter');
          },
        };
      },
      function () {
        return {
          resolvedOptions: () => ({ timeZone: 'UTC' }),
          formatToParts: () => {
            throw new Error('parts call');
          },
        };
      },
      function () {
        return {
          resolvedOptions: () => ({ timeZone: 'UTC' }),
          formatToParts: () => null,
        };
      },
    ];

    for (const makeFormatter of trapCases) {
      vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(
        makeFormatter as never
      );
      expect(formatOverviewClock(now, 'UTC')).toBeNull();
      vi.mocked(Intl.DateTimeFormat).mockRestore();
    }
  });
});

describe('useOverviewClock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-02T00:00:00.250Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('uses one recursive timer aligned to whole seconds and cleans up', () => {
    let current = new Date('2026-01-02T00:00:00.250Z');
    const now = vi.fn(() => current);
    const { result, unmount, rerender } = renderHook(
      () => useOverviewClock(now),
      {
        wrapper: StrictMode,
      }
    );

    expect(result.current.toISOString()).toBe('2026-01-02T00:00:00.250Z');
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    rerender();
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    current = new Date('2026-01-02T00:00:01.000Z');
    act(() => vi.advanceTimersByTime(750));
    expect(result.current.toISOString()).toBe('2026-01-02T00:00:01.000Z');
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('falls back deterministically when the initial clock provider fails', () => {
    const invalidDates = [
      () => {
        throw new Error('clock provider');
      },
      () => new Date(Number.NaN),
      () => new Date(Number.POSITIVE_INFINITY),
      () => null as never,
    ];

    for (const now of invalidDates) {
      const { result, unmount } = renderHook(() => useOverviewClock(now));
      expect(result.current.toISOString()).toBe('1970-01-01T00:00:00.000Z');
      expect(vi.getTimerCount()).toBe(1);
      unmount();
      expect(vi.getTimerCount()).toBe(0);
    }
  });

  it('preserves the last valid clock value through invalid reads and recovers', () => {
    let current = new Date('2026-01-02T00:00:00.250Z') as Date | 'throw';
    const now = vi.fn(() => {
      if (current === 'throw') {
        throw new Error('later provider');
      }
      return current;
    });
    const { result, unmount } = renderHook(() => useOverviewClock(now));

    expect(result.current.toISOString()).toBe('2026-01-02T00:00:00.250Z');
    expect(vi.getTimerCount()).toBe(1);
    current = new Date(Number.NaN);
    act(() => vi.advanceTimersByTime(750));
    expect(result.current.toISOString()).toBe('2026-01-02T00:00:00.250Z');
    expect(vi.getTimerCount()).toBe(1);

    current = 'throw';
    act(() => vi.advanceTimersByTime(750));
    expect(result.current.toISOString()).toBe('2026-01-02T00:00:00.250Z');
    expect(vi.getTimerCount()).toBe(1);

    current = new Date('2026-01-02T00:00:02.000Z');
    act(() => vi.advanceTimersByTime(750));
    expect(result.current.toISOString()).toBe('2026-01-02T00:00:02.000Z');
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
