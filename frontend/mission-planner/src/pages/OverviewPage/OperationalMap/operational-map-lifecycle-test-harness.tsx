import { act } from '@testing-library/react';
import L from 'leaflet';
import { expect, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import { makeOverviewSnapshot } from './test-fixtures';

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

export function snapshot(offset: number) {
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
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('min-width') ? matches : false,
    media: query,
    onchange: null,
    addEventListener: (
      _type: string,
      listener: EventListenerOrEventListenerObject
    ) => {
      if (typeof listener === 'function') listeners.add(listener as never);
    },
    removeEventListener: (
      _type: string,
      listener: EventListenerOrEventListenerObject
    ) => {
      if (typeof listener === 'function') listeners.delete(listener as never);
    },
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
  return { listeners };
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
    radar as unknown as {
      createTile(coords: L.Coords, done: () => void): HTMLElement;
    }
  ).createTile(coords, done) as HTMLImageElement;
}

export function trackObjectUrls() {
  let next = 0;
  const active = new Set<string>();
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
    const url = `blob:owned-${(next += 1)}`;
    active.add(url);
    return url;
  });
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url) => {
    active.delete(url);
  });
  return { active };
}

export function leafletEventCount(map: L.Map): number {
  return Object.values(
    (map as unknown as { _events?: Record<string, unknown[]> })._events ?? {}
  ).reduce((total, listeners) => total + listeners.length, 0);
}

export function layerCount(map: L.Map): number {
  let count = 0;
  map.eachLayer(() => (count += 1));
  return count;
}
