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
  installMatchMedia,
  layerCount,
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
    expect(first.groups).toHaveLength(11);
    expect(first.radar).toBeInstanceOf(L.GridLayer);
    expect(first.basemap).toBeInstanceOf(L.TileLayer);
    expect(first.features.get('current-position')).toBeInstanceOf(L.Marker);
    expect(first.features.get('route:west:route-west:0')).toBeInstanceOf(
      L.Polyline
    );
    expect(radarGridLayerTestInternals.managers).toHaveLength(1);

    fireEvent.click(
      screen.getByRole('button', { name: 'Enable map interaction' })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Current position' }));
    fireEvent.click(screen.getByRole('button', { name: 'Measure distance' }));
    act(() => expectMap(map).fire('click', { latlng: L.latLng(39, -104) }));
    const disclosure = document.querySelector('details');
    expect(disclosure?.open).toBe(true);
    const center = expectMap(map).getCenter();
    const zoom = expectMap(map).getZoom();
    const baselineAdds = addLayer.mock.calls.length;
    const baselineRemoves = removeLayer.mock.calls.length;
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
      expect(
        screen.getAllByText(/no distance selected|0.0 nautical miles/)
      ).not.toHaveLength(0);
      expect(
        screen.getByRole('button', { name: 'Return to page scrolling' })
      ).toBeInTheDocument();
      expect(disclosure?.open).toBe(true);
    }

    rerender(
      <OperationalMap {...props} radarRefreshToken={2} snapshot={snapshot(6)} />
    );
    await flush();
    expectSameOwnership(collectOwnership(expectMap(map)), first);
    expect(addLayer.mock.calls.length).toBe(baselineAdds);
    expect(removeLayer.mock.calls.length).toBe(baselineRemoves);
    expect(fitBounds).not.toHaveBeenCalled();
    expect(setLatLng).toHaveBeenCalled();
    expect(setLatLngs).toHaveBeenCalled();
    expect(setStyle).toHaveBeenCalled();
    expect(setIcon).toHaveBeenCalled();
    expect(media.listeners).toHaveLength(1);
  });

  it('settles production radar manager and Leaflet ownership over repeated enable cycles', async () => {
    const urls = trackObjectUrls();
    let map: L.Map | null = null;
    const props = mapProps({ onMapReady: (next) => (map = next) });
    const { rerender, unmount } = render(<OperationalMap {...props} />);
    await flush();
    const radar = only(radarGridLayerTestInternals.layers);
    const manager = only(radarGridLayerTestInternals.managers);
    const baselineEvents = leafletEventCount(expectMap(map));
    const baselineLayers = layerCount(expectMap(map));

    for (let count = 0; count < 20; count += 1) {
      const tile = createRadarTile(
        radar,
        { z: 1, x: count, y: 0 } as L.Coords,
        vi.fn()
      );
      await flush();
      tile.dispatchEvent(new Event('load'));
      await flush();
      rerender(<OperationalMap {...props} radarEnabled={false} />);
      await flush();
      expect(manager.stats()).toEqual({
        inFlight: 0,
        tracked: 0,
        objectUrls: 0,
      });
      expect(urls.active).toHaveLength(0);
      expect(layerCount(expectMap(map))).toBe(baselineLayers - 1);
      rerender(<OperationalMap {...props} radarEnabled={true} />);
      await flush();
      expect(leafletEventCount(expectMap(map))).toBe(baselineEvents);
    }

    unmount();
    await flush();
    expect(radarGridLayerTestInternals.managers).toHaveLength(0);
    expect(radarGridLayerTestInternals.layers).toHaveLength(0);
    expect(urls.active).toHaveLength(0);
  });
});
