import { act } from '@testing-library/react';
import { vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import { makeOverviewSnapshot } from './test-fixtures';

export function mapProps(
  overrides: Partial<React.ComponentProps<typeof OperationalMap>> = {}
) {
  return {
    snapshot: makeOverviewSnapshot(),
    radarEnabled: true,
    radarRefreshToken: 1,
    retryRadar: vi.fn(),
    reportRadarResult: vi.fn(),
    onRadarEnabledChange: vi.fn(),
    ...overrides,
  };
}

export function validBoundsSnapshot(offset: number) {
  return makeOverviewSnapshot({
    routeWest: [
      { latitude: 39 + offset, longitude: -104 },
      { latitude: 40 + offset, longitude: -103 },
    ],
  });
}

export async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

export function installMatchMedia({
  wide,
  reduced,
}: {
  wide: boolean;
  reduced: boolean;
}) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  let wideQuery: MediaQueryList | null = null;
  const add = vi.fn(
    (_type: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener === 'function') listeners.add(listener as never);
    }
  );
  const remove = vi.fn(
    (_type: string, listener: EventListenerOrEventListenerObject) => {
      if (typeof listener === 'function') listeners.delete(listener as never);
    }
  );
  vi.stubGlobal('matchMedia', (query: string) => {
    const mql = {
      matches: query.includes('prefers-reduced-motion') ? reduced : wide,
      media: query,
      onchange: null,
      addEventListener: add,
      removeEventListener: remove,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } as unknown as MediaQueryList;
    if (query.includes('min-width')) wideQuery = mql;
    return mql;
  });
  return {
    add,
    remove,
    listeners,
    setWide(matches: boolean) {
      if (wideQuery) {
        Object.defineProperty(wideQuery, 'matches', {
          configurable: true,
          value: matches,
        });
      }
      for (const listener of listeners) {
        listener({ matches } as MediaQueryListEvent);
      }
    },
  };
}

export function pointerLikeEvent(): Event {
  return typeof PointerEvent === 'undefined'
    ? new MouseEvent('click')
    : new PointerEvent('pointerup');
}

export function layerEventCount(layer: L.Evented | undefined): number {
  if (!layer) return 0;
  return Object.values(
    (layer as unknown as { _events?: Record<string, unknown[]> })._events ?? {}
  ).reduce((total, listeners) => total + listeners.length, 0);
}

export function layerEventTypeCount(
  layer: L.Evented | undefined,
  type: string
): number {
  if (!layer) return 0;
  const listeners = (
    layer as unknown as { _events?: Record<string, unknown[]> }
  )._events?.[type];
  return listeners?.length ?? 0;
}
