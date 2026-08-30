import { useEffect, useRef, useState } from 'react';

export type OverviewNow = () => Date;
export interface FormattedOverviewClock {
  readonly dateTime: string;
  readonly time: string;
  readonly offset: string;
  readonly zoneAndOffset: string;
}

function nextSecondDelay(date: Date): number {
  const remainder = date.getTime() % 1000;
  return remainder === 0 ? 1000 : 1000 - remainder;
}

export function useOverviewClock(now: OverviewNow = () => new Date()): Date {
  const nowRef = useRef(now);
  const mountedRef = useRef(false);
  const [current, setCurrent] = useState(() => now());

  useEffect(() => {
    nowRef.current = now;
  }, [now]);

  useEffect(() => {
    mountedRef.current = true;
    let timeout: ReturnType<typeof setTimeout> | null = null;
    const schedule = () => {
      timeout = setTimeout(() => {
        const next = nowRef.current();
        if (!mountedRef.current) {
          return;
        }
        setCurrent(next);
        schedule();
      }, nextSecondDelay(nowRef.current()));
    };
    schedule();
    return () => {
      mountedRef.current = false;
      if (timeout !== null) {
        clearTimeout(timeout);
      }
    };
  }, []);

  return current;
}

function offsetFromParts(parts: Intl.DateTimeFormatPart[]): string | null {
  const value = parts.find((part) => part.type === 'timeZoneName')?.value;
  if (!value) {
    return null;
  }
  if (value === 'GMT' || value === 'UTC') {
    return 'UTC+00:00';
  }
  const match = /^GMT([+-])(\d{1,2})(?::?(\d{2}))?$/.exec(value);
  if (!match) {
    return null;
  }
  const [, sign, hour, minute = '00'] = match;
  return `UTC${sign}${hour.padStart(2, '0')}:${minute}`;
}

export function formatOverviewClock(
  now: Date,
  timeZone: string
): FormattedOverviewClock | null {
  try {
    if (!(now instanceof Date) || Number.isNaN(now.getTime())) {
      return null;
    }
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'longOffset',
    });
    const resolvedOptions = formatter.resolvedOptions;
    if (typeof resolvedOptions !== 'function') {
      return null;
    }
    const resolved = resolvedOptions.call(formatter) as unknown;
    if (
      !resolved ||
      typeof resolved !== 'object' ||
      typeof (resolved as { timeZone?: unknown }).timeZone !== 'string'
    ) {
      return null;
    }
    const formatToParts = formatter.formatToParts;
    if (typeof formatToParts !== 'function') {
      return null;
    }
    const parts = formatToParts.call(formatter, now) as unknown;
    if (!Array.isArray(parts)) {
      return null;
    }
    const hour = parts.find((part) => part.type === 'hour')?.value;
    const minute = parts.find((part) => part.type === 'minute')?.value;
    const second = parts.find((part) => part.type === 'second')?.value;
    const offset = offsetFromParts(parts);
    if (!hour || !minute || !second || !offset) {
      return null;
    }
    const time = `${hour}:${minute}:${second}`;
    return {
      dateTime: now.toISOString(),
      time,
      offset,
      zoneAndOffset: `${timeZone} (${offset})`,
    };
  } catch {
    return null;
  }
}
