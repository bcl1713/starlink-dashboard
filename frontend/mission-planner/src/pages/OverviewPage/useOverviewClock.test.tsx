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
});
