import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import {
  collectOwnership,
  createRadarTile,
  expectMap,
  expectSameOwnership,
  flush,
  installImageListenerTracker,
  installMatchMedia,
  layerCount,
  layerEventCount,
  layerEventTypeCount,
  leafletEventCount,
  mapProps,
  only,
  snapshot,
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
  vi.spyOn(URL, 'createObjectURL').mockImplementation(
    () => `blob:lifecycle-${Math.random()}`
  );
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  radarGridLayerTestInternals.reset();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  radarGridLayerTestInternals.reset();
});

describe('OperationalMap production lifecycle ownership', () => {
  it('keeps production map ownership stable through five data rerenders then one manual token', async () => {
    const media = installMatchMedia(false);
    const measureLines: L.Polyline[] = [];
    const originalPolyline = L.polyline;
    vi.spyOn(L, 'polyline').mockImplementation((latlngs, options) => {
      const line = originalPolyline(latlngs, options);
      if (options?.dashArray === '4 4') measureLines.push(line);
      return line;
    });
    const addLayer = vi.spyOn(L.LayerGroup.prototype, 'addLayer');
    const removeLayer = vi.spyOn(L.LayerGroup.prototype, 'removeLayer');
    const setLatLng = vi.spyOn(L.Marker.prototype, 'setLatLng');
    const setLatLngs = vi.spyOn(L.Polyline.prototype, 'setLatLngs');
    const setStyle = vi.spyOn(L.Polyline.prototype, 'setStyle');
    const setIcon = vi.spyOn(L.Marker.prototype, 'setIcon');
    const fitBounds = vi.spyOn(L.Map.prototype, 'fitBounds');
    let map: L.Map | null = null;
    const props = mapProps({ onMapReady: (next) => (map = next) });
    const { rerender } = render(<OperationalMap {...props} />);
    await flush();

    const first = collectOwnership(expectMap(map));
    const activeRoute = first.features.get(
      'route:west:route-west:0'
    ) as L.Polyline;
    const activeLink = first.features.get(
      'active-link:normal:sat-a:0'
    ) as L.Polyline;
    const currentPosition = first.features.get('current-position') as L.Marker;
    expect(first.groups).toHaveLength(11);
    expect(first.radar).toBeInstanceOf(L.GridLayer);
    expect(first.basemap).toBeInstanceOf(L.TileLayer);
    expect(currentPosition).toBeInstanceOf(L.Marker);
    expect(activeRoute).toBeInstanceOf(L.Polyline);
    expect(radarGridLayerTestInternals.managers).toHaveLength(1);
    const distance = vi
      .spyOn(expectMap(map), 'distance')
      .mockReturnValue(185.2);

    fireEvent.click(
      screen.getByRole('button', { name: 'Enable map interaction' })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Current position' }));
    const pointA = L.latLng(39, -104);
    const pointB = L.latLng(39, -103.998);
    fireEvent.click(screen.getByRole('button', { name: 'Measure distance' }));
    act(() => {
      expectMap(map).fire('click', { latlng: pointA });
      expectMap(map).fire('click', { latlng: pointB });
    });
    await flush();
    expect(measureLines).toHaveLength(1);
    expect(distance).toHaveBeenCalled();
    const measureLine = measureLines[0];
    expect(expectMap(map).hasLayer(measureLine)).toBe(true);
    expect(measureLine.getLatLngs()).toEqual([pointA, pointB]);
    expect(
      screen.getByRole('button', { name: 'Measure distance' })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getAllByText(/0.1 nautical miles/)).not.toHaveLength(0);
    const disclosure = document.querySelector('details');
    expect(disclosure?.open).toBe(true);
    const center = expectMap(map).getCenter();
    const zoom = expectMap(map).getZoom();
    addLayer.mockClear();
    removeLayer.mockClear();
    setLatLng.mockClear();
    setLatLngs.mockClear();
    setStyle.mockClear();
    setIcon.mockClear();
    fitBounds.mockClear();

    for (let count = 0; count < 5; count += 1) {
      rerender(
        <OperationalMap
          {...props}
          radarRefreshToken={1}
          snapshot={snapshot(count + 1)}
        />
      );
      await flush();
      expectSameOwnership(collectOwnership(expectMap(map)), first);
      expect(expectMap(map).getCenter()).toEqual(center);
      expect(expectMap(map).getZoom()).toBe(zoom);
      expect(
        screen.getByRole('heading', { name: 'Current position' })
      ).toBeInTheDocument();
      expect(expectMap(map).hasLayer(measureLine)).toBe(true);
      expect(measureLine.getLatLngs()).toEqual([pointA, pointB]);
      expect(
        screen.getByRole('button', { name: 'Measure distance' })
      ).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getAllByText(/0.1 nautical miles/)).not.toHaveLength(0);
      expect(
        screen.getByRole('button', { name: 'Return to page scrolling' })
      ).toBeInTheDocument();
      expect(disclosure?.open).toBe(true);
    }
    expect(addLayer).not.toHaveBeenCalled();
    expect(removeLayer).not.toHaveBeenCalled();
    expect(setLatLng).toHaveBeenCalledWith([39, -104]);
    expect(setLatLng.mock.contexts).toContain(currentPosition);
    expect(setLatLngs.mock.contexts).toContain(activeRoute);
    expect(setLatLngs.mock.contexts).toContain(activeLink);
    expect(setStyle.mock.contexts).toContain(activeRoute);
    expect(setIcon.mock.contexts).toContain(currentPosition);

    rerender(
      <OperationalMap {...props} radarRefreshToken={2} snapshot={snapshot(6)} />
    );
    await flush();
    expectSameOwnership(collectOwnership(expectMap(map)), first);
    expect(addLayer).not.toHaveBeenCalled();
    expect(removeLayer).not.toHaveBeenCalled();
    expect(fitBounds).not.toHaveBeenCalled();
    expect(expectMap(map).hasLayer(measureLine)).toBe(true);
    expect(measureLine.getLatLngs()).toEqual([pointA, pointB]);
    expect(screen.getAllByText(/0.1 nautical miles/)).not.toHaveLength(0);
    expect(media.listeners).toHaveLength(1);
  });

  it('settles production radar manager and Leaflet ownership over repeated enable cycles', async () => {
    const urls = trackObjectUrls();
    const media = installMatchMedia(false);
    const imageListeners = installImageListenerTracker();
    let pendingMicrotasks = 0;
    const realQueueMicrotask = globalThis.queueMicrotask;
    vi.stubGlobal('queueMicrotask', (callback: VoidFunction) => {
      pendingMicrotasks += 1;
      realQueueMicrotask(() => {
        try {
          callback();
        } finally {
          pendingMicrotasks -= 1;
        }
      });
    });
    let map: L.Map | null = null;
    const retryRadar = vi.fn();
    const reportRadarResult = vi.fn();
    const props = mapProps({
      onMapReady: (next) => (map = next),
      reportRadarResult,
      retryRadar,
      snapshot: snapshot(0, true),
    });
    const { rerender, unmount } = render(<OperationalMap {...props} />);
    await flush();
    const radar = only(radarGridLayerTestInternals.layers);
    const manager = only(radarGridLayerTestInternals.managers);
    const baselineEvents = leafletEventCount(expectMap(map));
    const baselineRadarEvents = layerEventCount(radar);
    const baselineLayers = layerCount(expectMap(map));
    const baselineMediaListeners = media.listeners.size;
    const baselineReports = reportRadarResult.mock.calls.length;
    const baselineCreateUrls = urls.created.length;
    const baselineFocus = document.activeElement;

    for (let count = 0; count < 20; count += 1) {
      const tile = createRadarTile(
        radar,
        { z: 1, x: count, y: 0 } as L.Coords,
        vi.fn()
      );
      await flush();
      tile.dispatchEvent(new Event('load'));
      await flush();
      expect(imageListeners.activeFor(tile)).toBeGreaterThan(0);
      expect(manager.stats().tracked).toBeGreaterThan(0);
      const beforeToken = urls.created.length;
      rerender(
        <OperationalMap
          {...props}
          radarEnabled={true}
          radarRefreshToken={count + 2}
        />
      );
      await flush();
      await flush();
      expect(urls.created.length).toBeGreaterThan(beforeToken);
      tile.dispatchEvent(new Event('load'));
      await flush();
      fireEvent.click(
        screen.getByRole('button', { name: 'Retry weather radar' })
      );
      expect(retryRadar).toHaveBeenCalledTimes(count + 1);
      rerender(<OperationalMap {...props} radarEnabled={false} />);
      await flush();
      expect(manager.stats()).toEqual({
        inFlight: 0,
        tracked: 0,
        objectUrls: 0,
      });
      expect(imageListeners.activeFor(tile)).toBe(0);
      expect(urls.active).toHaveLength(0);
      expect(layerCount(expectMap(map))).toBe(baselineLayers - 1);
      expect(layerEventCount(radar)).toBeLessThanOrEqual(baselineRadarEvents);
      expect(layerEventTypeCount(radar, 'tileunload')).toBe(1);
      expect(media.listeners.size).toBe(baselineMediaListeners);
      expect(pendingMicrotasks).toBe(0);
      rerender(<OperationalMap {...props} radarEnabled={true} />);
      await flush();
      expect(leafletEventCount(expectMap(map))).toBe(baselineEvents);
      expect(layerCount(expectMap(map))).toBe(baselineLayers);
      expect(reportRadarResult.mock.calls.length).toBeGreaterThanOrEqual(
        baselineReports
      );
      expect(urls.created.length).toBeGreaterThanOrEqual(baselineCreateUrls);
      expect(urls.active.size).toBe(manager.stats().objectUrls);
      expect(document.activeElement).toBe(baselineFocus);
    }

    unmount();
    await flush();
    expect(radarGridLayerTestInternals.managers).toHaveLength(0);
    expect(radarGridLayerTestInternals.layers).toHaveLength(0);
    expect(urls.active).toHaveLength(0);
    expect(media.remove).toHaveBeenCalledTimes(media.add.mock.calls.length);
    expect(media.listeners).toHaveLength(0);
    expect(pendingMicrotasks).toBe(0);
  });
});
