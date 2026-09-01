import { act } from '@testing-library/react';
import L from 'leaflet';
import { expect, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import { makeOverviewSnapshot } from './test-fixtures';

type LeafletEventedWithEvents = L.Evented & {
  readonly _events?: Record<string, unknown[]>;
};

interface Ownership {
  readonly map: L.Map;
  readonly groups: readonly L.LayerGroup[];
  readonly radar: L.Layer | null;
  readonly basemap: L.Layer | null;
  readonly features: ReadonlyMap<string, L.Layer>;
}

export function collectOwnership(map: L.Map): Ownership {
  const groups: L.LayerGroup[] = [];
  const features = new Map<string, L.Layer>();
  let radar: L.Layer | null = null;
  let basemap: L.Layer | null = null;
  map.eachLayer((layer) => {
    if (layer instanceof L.TileLayer) basemap = layer;
    else if (layer instanceof L.GridLayer) radar = layer;
    else if (layer instanceof L.LayerGroup) {
      groups.push(layer);
      layer.eachLayer((child) => {
        const feature = (child as { operationalFeature?: { id: string } })
          .operationalFeature;
        if (feature) features.set(feature.id, child);
      });
    }
  });
  return { map, groups, radar, basemap, features };
}

export function expectSameOwnership(
  received: Ownership,
  expected: Ownership
): void {
  expect(received.map).toBe(expected.map);
  expect(received.groups).toEqual(expected.groups);
  expect(received.radar).toBe(expected.radar);
  expect(received.basemap).toBe(expected.basemap);
  for (const [id, layer] of expected.features) {
    expect(received.features.get(id)).toBe(layer);
  }
}

export function mapProps(
  overrides: Partial<React.ComponentProps<typeof OperationalMap>> = {}
) {
  return {
    snapshot: snapshot(0),
    radarEnabled: true,
    radarRefreshToken: 1,
    retryRadar: vi.fn(),
    reportRadarResult: vi.fn(),
    onRadarEnabledChange: vi.fn(),
    ...overrides,
  };
}

export function snapshot(offset: number, radarError = false) {
  return makeOverviewSnapshot({
    heading: 90 + offset,
    routeWest: [
      { latitude: 39 + offset, longitude: -104 },
      { latitude: 40 + offset, longitude: -103 },
    ],
    activeNormal: [
      { latitude: 39 + offset, longitude: -104 },
      { latitude: 1 + offset, longitude: 2 },
    ],
    history: [
      ['2026-08-29T12:00:00Z', 10 + offset, -10],
      ['2026-08-29T12:00:01Z', 11 + offset, -11],
    ],
    radarPhase: radarError ? 'error' : undefined,
    radarError,
  });
}

export async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

export function expectMap(map: L.Map | null): L.Map {
  expect(map).toBeTruthy();
  return map as L.Map;
}

export function installMatchMedia(matches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
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
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('min-width') ? matches : false,
    media: query,
    onchange: null,
    addEventListener: add,
    removeEventListener: remove,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
  return { add, remove, listeners };
}

export function only<T>(set: ReadonlySet<T>): T {
  expect(set).toHaveLength(1);
  return [...set][0];
}

export function createRadarTile(
  radar: L.GridLayer,
  coords: L.Coords,
  done: () => void
): HTMLImageElement {
  return (
    radar as L.GridLayer & {
      createTile(coords: L.Coords, done: () => void): HTMLElement;
    }
  ).createTile(coords, done) as HTMLImageElement;
}

export function trackObjectUrls() {
  let next = 0;
  const active = new Set<string>();
  const created: string[] = [];
  const revoked: string[] = [];
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
    const url = `blob:owned-${(next += 1)}`;
    created.push(url);
    active.add(url);
    return url;
  });
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url) => {
    revoked.push(url);
    active.delete(url);
  });
  return { active, created, revoked };
}

export function leafletEventCount(map: L.Map): number {
  return Object.values((map as LeafletEventedWithEvents)._events ?? {}).reduce(
    (total, listeners) => total + listeners.length,
    0
  );
}

export function layerCount(map: L.Map): number {
  let count = 0;
  map.eachLayer(() => (count += 1));
  return count;
}

export function layerEventCount(layer: L.Evented | null): number {
  if (!layer) return 0;
  return Object.values(
    (layer as LeafletEventedWithEvents)._events ?? {}
  ).reduce((total, listeners) => total + listeners.length, 0);
}

export function layerEventTypeCount(
  layer: L.Evented | null,
  type: string
): number {
  if (!layer) return 0;
  const listeners = (layer as LeafletEventedWithEvents)._events?.[type];
  return listeners?.length ?? 0;
}

export function installImageListenerTracker() {
  const originalAdd = HTMLImageElement.prototype.addEventListener;
  const originalRemove = HTMLImageElement.prototype.removeEventListener;
  const active = new WeakMap<
    HTMLImageElement,
    Map<string, Set<EventListenerOrEventListenerObject>>
  >();
  vi.spyOn(HTMLImageElement.prototype, 'addEventListener').mockImplementation(
    function add(
      this: HTMLImageElement,
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ) {
      const byType = active.get(this) ?? new Map();
      const listeners = byType.get(type) ?? new Set();
      listeners.add(listener);
      byType.set(type, listeners);
      active.set(this, byType);
      return Reflect.apply(originalAdd, this, [
        type,
        listener,
        options,
      ]) as void;
    }
  );
  vi.spyOn(
    HTMLImageElement.prototype,
    'removeEventListener'
  ).mockImplementation(function remove(
    this: HTMLImageElement,
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: boolean | EventListenerOptions
  ) {
    active.get(this)?.get(type)?.delete(listener);
    return Reflect.apply(originalRemove, this, [
      type,
      listener,
      options,
    ]) as void;
  });
  return {
    activeFor(element: HTMLImageElement): number {
      let total = 0;
      active.get(element)?.forEach((listeners) => (total += listeners.size));
      return total;
    },
  };
}
