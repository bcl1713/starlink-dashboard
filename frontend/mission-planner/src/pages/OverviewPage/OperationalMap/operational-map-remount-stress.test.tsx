import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import {
  OPERATIONAL_LAYERS,
  createDefaultLayerVisibility,
} from './operational-map-contract';
import {
  collectOwnership,
  createRadarTile,
  expectMap,
  flush,
  installImageListenerTracker,
  installMatchMedia,
  layerCount,
  layerEventCount,
  leafletEventCount,
  mapProps,
  only,
  trackObjectUrls,
} from './operational-map-lifecycle-test-harness';
import { radarGridLayerTestInternals } from './radar-grid-layer-test-internals';

const radarService = vi.hoisted(() => vi.fn());
const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer;

vi.mock('../../../services/monitoring', () => ({
  getRainViewerRadarTile: radarService,
}));

beforeEach(() => {
  radarService.mockResolvedValue({
    bytes: png.slice(0),
    frameTimestamp: '1777294800',
  });
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    configurable: true,
    value: vi.fn(() => Promise.resolve()),
  });
  radarGridLayerTestInternals.reset();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  radarGridLayerTestInternals.reset();
});

describe('OperationalMap complete remount ownership', () => {
  it('dirties mount-local UI state then restores fresh defaults over twenty mounts', async () => {
    const urls = trackObjectUrls();
    const media = installMatchMedia(false);
    const imageListeners = installImageListenerTracker();
    const resize = installResizeObserver();
    const microtasks = installMicrotaskTracker();
    const measureLines: L.Polyline[] = [];
    const originalPolyline = L.polyline;
    vi.spyOn(L, 'polyline').mockImplementation((latlngs, options) => {
      const line = originalPolyline(latlngs, options);
      if (options?.dashArray === '4 4') measureLines.push(line);
      return line;
    });
    let previous: ReturnType<typeof collectOwnership> | null = null;

    for (let count = 0; count < 20; count += 1) {
      let map: L.Map | null = null;
      const reportRadarResult = vi.fn();
      const onLayerVisibilityChange = vi.fn();
      const { unmount } = render(
        <OperationalMap
          {...mapProps({
            onMapReady: (next) => (map = next),
            onLayerVisibilityChange,
            reportRadarResult,
          })}
        />
      );
      await flush();

      const activeMap = expectMap(map);
      const ownership = collectOwnership(activeMap);
      expect(ownership.groups).toHaveLength(11);
      expect(ownership.radar).toBeInstanceOf(L.GridLayer);
      expect(ownership.basemap).toBeInstanceOf(L.TileLayer);
      expect(activeMap.getContainer().tabIndex).toBe(-1);
      expect(document.activeElement).toBe(document.body);
      expectFreshMountLocalDefaults(activeMap, measureLines);
      expect(radarGridLayerTestInternals.managers).toHaveLength(1);
      expect(radarGridLayerTestInternals.layers).toHaveLength(1);
      expect(media.listeners).toHaveLength(1);
      expect(resize.created).toBe(count + 1);
      expect(resize.live).toBe(1);
      if (previous) {
        expect(ownership.map).not.toBe(previous.map);
        expect(ownership.radar).not.toBe(previous.radar);
        expect(ownership.basemap).not.toBe(previous.basemap);
        expect(ownership.groups[0]).not.toBe(previous.groups[0]);
      }

      const manager = only(radarGridLayerTestInternals.managers);
      const radar = only(radarGridLayerTestInternals.layers);
      const mapEvents = leafletEventCount(activeMap);
      const radarEvents = layerEventCount(radar);
      const tile = createRadarTile(
        radar,
        { z: 1, x: count, y: 0 } as L.Coords,
        vi.fn()
      );
      await flush();
      tile.dispatchEvent(new Event('load'));
      await flush();
      expect(manager.stats()).toEqual({
        inFlight: 0,
        tracked: 1,
        objectUrls: 1,
      });
      expect(urls.active).toHaveLength(1);
      expect(imageListeners.activeFor(tile)).toBeGreaterThan(0);

      await dirtyMountLocalState(activeMap, measureLines);
      expect(onLayerVisibilityChange).toHaveBeenCalledWith(
        expect.objectContaining({
          'planned-route-west': false,
        })
      );

      unmount();
      await flush();

      expect(manager.stats()).toEqual({
        inFlight: 0,
        tracked: 0,
        objectUrls: 0,
      });
      expect(urls.active).toHaveLength(0);
      expect(new Set(urls.revoked)).toEqual(new Set(urls.created));
      expect(resize.live).toBe(0);
      expect(media.listeners).toHaveLength(0);
      expect(radarGridLayerTestInternals.managers).toHaveLength(0);
      expect(radarGridLayerTestInternals.layers).toHaveLength(0);
      expect(leafletEventCount(activeMap)).toBeLessThanOrEqual(mapEvents);
      expect(layerEventCount(radar)).toBeLessThanOrEqual(radarEvents);
      expect(layerEventTypeCount(radar, 'tileunload')).toBe(1);
      expect(layerCount(activeMap)).toBe(0);
      expect(microtasks.pending).toBe(0);
      expect(imageListeners.activeFor(tile)).toBe(0);
      previous = ownership;
    }

    expect(resize.disconnected).toBe(resize.created);
    expect(media.add).toHaveBeenCalledTimes(media.remove.mock.calls.length);
    expect(urls.active).toHaveLength(0);
  }, 20000);
});

function expectFreshMountLocalDefaults(
  map: L.Map,
  measureLines: readonly L.Polyline[]
): void {
  const defaults = createDefaultLayerVisibility(true);
  expect(
    screen.queryByRole('region', { name: 'Feature details' })
  ).not.toBeInTheDocument();
  expect(document.querySelector('details')?.open).toBe(false);
  for (const layer of OPERATIONAL_LAYERS) {
    if (layer.id === 'weather-radar') continue;
    expect(
      (screen.getByLabelText(layer.label) as HTMLInputElement).checked
    ).toBe(defaults[layer.id]);
  }
  expect(
    screen.getByRole('button', { name: 'Measure distance' })
  ).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getAllByText('Measurement: no distance selected')).toHaveLength(
    2
  );
  const measurementLine = measureLines[measureLines.length - 1];
  expect(measurementLine).toBeInstanceOf(L.Polyline);
  expect(measurementLine.getLatLngs()).toEqual([]);
  expect(map.hasLayer(measurementLine)).toBe(false);
  expect(
    screen.getByRole('button', { name: 'Enable map interaction' })
  ).toBeInTheDocument();
  expect(map.getContainer().tabIndex).toBe(-1);
  expect(document.activeElement).toBe(document.body);
}

async function dirtyMountLocalState(
  map: L.Map,
  measureLines: readonly L.Polyline[]
): Promise<void> {
  const measurementLine = measureLines[measureLines.length - 1];
  expect(measurementLine).toBeInstanceOf(L.Polyline);
  expect(map.hasLayer(measurementLine)).toBe(false);
  vi.spyOn(map, 'distance').mockReturnValue(185.2);

  fireEvent.click(screen.getByRole('button', { name: 'Current position' }));
  expect(
    screen.getByRole('heading', { name: 'Current position' })
  ).toBeInTheDocument();

  fireEvent.click(screen.getByText('Operational layers'));
  expect(document.querySelector('details')?.open).toBe(true);
  fireEvent.click(screen.getByLabelText('Planned Route — western segment'));
  expect(
    screen.getByLabelText('Planned Route — western segment')
  ).not.toBeChecked();

  fireEvent.click(screen.getByRole('button', { name: 'Measure distance' }));
  await flush();
  act(() => {
    map.fire('click', { latlng: L.latLng(39, -104) });
    map.fire('click', { latlng: L.latLng(39, -103.998) });
  });
  await flush();
  expect(measurementLine.getLatLngs()).toHaveLength(2);
  expect(map.hasLayer(measurementLine)).toBe(true);
  expect(
    screen.getByRole('button', { name: 'Measure distance' })
  ).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getAllByText(/0.1 nautical miles/)).not.toHaveLength(0);

  fireEvent.click(
    screen.getByRole('button', { name: 'Enable map interaction' })
  );
  expect(
    screen.getByRole('button', { name: 'Return to page scrolling' })
  ).toBeInTheDocument();
  expect(map.getContainer().tabIndex).toBe(0);
  map.getContainer().focus();
  expect(document.activeElement).toBe(map.getContainer());
}

function installResizeObserver() {
  const state = { created: 0, disconnected: 0, live: 0 };
  class TrackingResizeObserver {
    observe = vi.fn();
    disconnect = vi.fn(() => {
      state.disconnected += 1;
      state.live -= 1;
    });
    constructor() {
      state.created += 1;
      state.live += 1;
    }
  }
  vi.stubGlobal('ResizeObserver', TrackingResizeObserver);
  return state;
}

function installMicrotaskTracker() {
  const state = { pending: 0 };
  const realQueueMicrotask = globalThis.queueMicrotask;
  vi.stubGlobal('queueMicrotask', (callback: VoidFunction) => {
    state.pending += 1;
    realQueueMicrotask(() => {
      try {
        callback();
      } finally {
        state.pending -= 1;
      }
    });
  });
  return state;
}

function layerEventTypeCount(layer: L.Evented, type: string): number {
  const listeners = (
    layer as L.Evented & { readonly _events?: Record<string, unknown[]> }
  )._events?.[type];
  return listeners?.length ?? 0;
}
