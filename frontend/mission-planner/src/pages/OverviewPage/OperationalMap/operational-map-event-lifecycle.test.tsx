import { createRef, StrictMode } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OperationalMap, type OperationalMapHandle } from './OperationalMap';
import {
  flush,
  installMatchMedia,
  layerEventCount,
  layerEventTypeCount,
  mapProps,
  pointerLikeEvent,
  validBoundsSnapshot,
} from './operational-map-event-test-harness';
import { radarGridLayerTestInternals } from './radar-grid-layer-test-internals';

function requireMap(map: L.Map | null): L.Map {
  if (!map) throw new Error('Expected map instance.');
  return map;
}

function eventCallCount(
  calls: readonly (readonly unknown[])[],
  type: string
): number {
  return calls.filter(([eventType]) => eventType === type).length;
}

const radarService = vi.hoisted(() => vi.fn());

vi.mock('../../../services/monitoring', () => ({
  getRainViewerRadarTile: radarService,
}));

beforeEach(() => {
  radarService.mockResolvedValue({
    bytes: new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer,
    frameTimestamp: '1777294800',
  });
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    configurable: true,
    value: vi.fn(() => Promise.resolve()),
  });
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:event');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('OperationalMap production event lifecycle', () => {
  it('invalidates through the production ResizeObserver and disconnects safely', async () => {
    const observers: ResizeObserverCallback[] = [];
    const disconnect = vi.fn();
    class TrackingResizeObserver {
      observe = vi.fn();
      disconnect = disconnect;
      constructor(callback: ResizeObserverCallback) {
        observers.push(callback);
      }
    }
    vi.stubGlobal('ResizeObserver', TrackingResizeObserver);
    const ref = createRef<OperationalMapHandle>();
    const { unmount } = render(<OperationalMap ref={ref} {...mapProps()} />);
    await flush();
    const map = ref.current?.getMap() as L.Map;
    const invalidate = vi.spyOn(map, 'invalidateSize');

    act(() => observers[0]([], {} as ResizeObserver));
    expect(invalidate).toHaveBeenCalledExactlyOnceWith({ pan: false });
    invalidate.mockImplementation(() => {
      throw new Error('hostile resize');
    });
    expect(() => observers[0]([], {} as ResizeObserver)).not.toThrow();
    unmount();
    expect(disconnect).toHaveBeenCalledTimes(1);
  });

  it('fits and focuses only through valid production viewport calls', async () => {
    const media = installMatchMedia({ wide: true, reduced: true });
    const ref = createRef<OperationalMapHandle>();
    const fitBounds = vi.spyOn(L.Map.prototype, 'fitBounds');
    const setView = vi.spyOn(L.Map.prototype, 'setView');
    const props = mapProps({ snapshot: validBoundsSnapshot(0) });
    const { rerender } = render(<OperationalMap ref={ref} {...props} />);
    await flush();

    expect(fitBounds).toHaveBeenCalledTimes(1);
    expect(fitBounds.mock.calls[0][1]).toMatchObject({
      animate: false,
      maxZoom: 8,
      padding: [24, 24],
    });
    const center = ref.current?.getMap()?.getCenter();
    const zoom = ref.current?.getMap()?.getZoom();
    for (let count = 0; count < 5; count += 1) {
      rerender(
        <OperationalMap
          ref={ref}
          {...props}
          snapshot={validBoundsSnapshot(count + 1)}
        />
      );
      await flush();
    }
    expect(fitBounds).toHaveBeenCalledTimes(1);
    expect(ref.current?.getMap()?.getCenter()).toEqual(center);
    expect(ref.current?.getMap()?.getZoom()).toBe(zoom);

    ref.current?.fitToAvailableLayers();
    expect(fitBounds).toHaveBeenCalledTimes(2);
    expect(fitBounds.mock.calls[1][1]).toMatchObject({ animate: false });
    setView.mockClear();
    ref.current?.focusCoordinates({
      latitude: 40,
      longitude: -105,
      zoom: 8,
      motion: 'reduced-aware',
    });
    expect(setView).toHaveBeenCalledTimes(1);
    expect(setView.mock.calls[0][0]).toEqual([40, -105]);
    expect(setView.mock.calls[0][1]).toBe(8);
    expect(setView.mock.calls[0][2]).toMatchObject({ animate: false });

    setView.mockClear();
    ref.current?.focusCoordinates({
      latitude: 91,
      longitude: -105,
      zoom: 8,
      motion: 'reduced-aware',
    });
    ref.current?.focusCoordinates({
      latitude: 40,
      longitude: -105,
      zoom: 7 as 8,
      motion: 'reduced-aware',
    });
    setView.mockImplementation(() => {
      throw new Error('unavailable map');
    });
    expect(() =>
      ref.current?.focusCoordinates({
        latitude: 40,
        longitude: -105,
        zoom: 8,
        motion: 'reduced-aware',
      })
    ).not.toThrow();
    expect(setView).toHaveBeenCalledTimes(1);
    expect(media.listeners).toHaveLength(1);
  });

  it('drives measurement through Leaflet click events and one mutable polyline', async () => {
    const created: L.Polyline[] = [];
    const originalPolyline = L.polyline;
    vi.spyOn(L, 'polyline').mockImplementation((latlngs, options) => {
      const line = originalPolyline(latlngs, options);
      if (options && 'dashArray' in options && options.dashArray === '4 4') {
        created.push(line);
      }
      return line;
    });
    const ref = createRef<OperationalMapHandle>();
    const { rerender, unmount } = render(
      <OperationalMap ref={ref} {...mapProps()} />
    );
    await flush();
    const map = ref.current?.getMap() as L.Map;
    const distance = vi.spyOn(map, 'distance').mockReturnValue(185.2);
    const setLatLngs = vi.spyOn(L.Polyline.prototype, 'setLatLngs');

    fireEvent.click(screen.getByRole('button', { name: 'Measure distance' }));
    act(() => {
      map.fire('click', {
        latlng: L.latLng(0, 0),
        originalEvent: new MouseEvent('click'),
      });
      map.fire('click', {
        latlng: L.latLng(0, 1),
        originalEvent: pointerLikeEvent(),
      });
    });
    await flush();

    expect(created).toHaveLength(1);
    expect(distance).toHaveBeenCalled();
    expect(setLatLngs).toHaveBeenCalled();
    expect(map.hasLayer(created[0])).toBe(true);
    expect(screen.getAllByText(/0.1 nautical miles/)).not.toHaveLength(0);
    rerender(
      <OperationalMap ref={ref} {...mapProps({ radarRefreshToken: 2 })} />
    );
    await flush();
    expect(map.hasLayer(created[0])).toBe(true);
    rerender(
      <OperationalMap ref={ref} {...mapProps({ radarRefreshToken: 3 })} />
    );
    await flush();
    expect(map.hasLayer(created[0])).toBe(true);
    unmount();
    await flush();
    expect(map.hasLayer(created[0])).toBe(false);
  });

  it('keeps responsive listeners balanced under StrictMode and relocks on Escape', async () => {
    const media = installMatchMedia({ wide: false, reduced: false });
    const resize = installResizeObserver();
    const mapOn = vi.spyOn(L.Map.prototype, 'on');
    const mapOff = vi.spyOn(L.Map.prototype, 'off');
    let map: L.Map | null = null;
    const { rerender, unmount } = render(
      <StrictMode>
        <OperationalMap {...mapProps({ onMapReady: (next) => (map = next) })} />
      </StrictMode>
    );
    await flush();
    const activeMap = requireMap(map);
    const container = activeMap.getContainer();
    const radar = [...radarGridLayerTestInternals.layers][0];
    const mapEvents = layerEventCount(activeMap);
    const radarEvents = layerEventCount(radar);
    const handlers = [
      activeMap.dragging,
      activeMap.touchZoom,
      activeMap.doubleClickZoom,
      activeMap.scrollWheelZoom,
      activeMap.boxZoom,
      activeMap.keyboard,
    ];
    expect(handlers.every((handler) => !handler.enabled())).toBe(true);
    expect(container.tabIndex).toBe(-1);
    expect(media.listeners).toHaveLength(1);
    expect(resize.created - resize.disconnected).toBe(1);
    expect(resize.live).toBe(1);

    act(() => media.setWide(true));
    expect(handlers.every((handler) => handler.enabled())).toBe(true);
    expect(container.tabIndex).toBe(0);
    act(() => media.setWide(false));
    expect(handlers.every((handler) => !handler.enabled())).toBe(true);
    expect(container.tabIndex).toBe(-1);
    const activation = screen.getByRole('button', {
      name: 'Enable map interaction',
    });
    activation.focus();
    expect(document.activeElement).toBe(activation);
    fireEvent.click(
      screen.getByRole('button', { name: 'Enable map interaction' })
    );
    expect(handlers.every((handler) => handler.enabled())).toBe(true);
    expect(container.tabIndex).toBe(0);
    container.focus();
    expect(document.activeElement).toBe(container);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(handlers.every((handler) => !handler.enabled())).toBe(true);
    expect(container.tabIndex).toBe(-1);
    expect(document.activeElement).toBe(activation);
    rerender(
      <StrictMode>
        <OperationalMap {...mapProps({ onMapReady: (next) => (map = next) })} />
      </StrictMode>
    );
    await flush();
    expect(layerEventCount(activeMap)).toBe(mapEvents);
    expect(layerEventCount(radar)).toBeLessThanOrEqual(radarEvents);
    expect(layerEventTypeCount(radar, 'tileunload')).toBe(1);
    expect(media.listeners).toHaveLength(1);
    expect(resize.live).toBe(1);
    unmount();
    expect(media.add).toHaveBeenCalledTimes(media.remove.mock.calls.length);
    expect(media.listeners).toHaveLength(0);
    expect(resize.created).toBe(resize.disconnected);
    expect(resize.live).toBe(0);
    const mapOnCalls = mapOn.mock.calls;
    const mapOffCalls = mapOff.mock.calls;
    expect(eventCallCount(mapOnCalls, 'moveend zoomend')).toBe(
      eventCallCount(mapOffCalls, 'moveend zoomend')
    );
    expect(radarGridLayerTestInternals.layers).toHaveLength(0);
  });
});

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
