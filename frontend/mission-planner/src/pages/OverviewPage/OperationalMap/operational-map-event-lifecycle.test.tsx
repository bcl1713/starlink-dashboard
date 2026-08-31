import { createRef } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { OperationalMap, type OperationalMapHandle } from './OperationalMap';
import { makeOverviewSnapshot } from './test-fixtures';

vi.mock('../../../services/monitoring', () => ({
  getRainViewerRadarTile: vi.fn(() =>
    Promise.resolve({
      bytes: new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer,
      frameTimestamp: '1777294800',
    })
  ),
}));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('OperationalMap production event lifecycle', () => {
  it('invokes actual map.invalidateSize with pan false from ResizeObserver', async () => {
    let resize: ResizeObserverCallback | null = null;
    class TrackingResizeObserver {
      observe = vi.fn();
      disconnect = vi.fn();
      constructor(callback: ResizeObserverCallback) {
        resize = callback;
      }
    }
    vi.stubGlobal('ResizeObserver', TrackingResizeObserver);
    const ref = createRef<OperationalMapHandle>();
    render(<OperationalMap ref={ref} {...mapProps()} />);
    await act(async () => undefined);
    const map = ref.current?.getMap();
    const invalidate = vi.spyOn(map as L.Map, 'invalidateSize');

    act(() => {
      resize?.([], {} as ResizeObserver);
    });

    expect(invalidate).toHaveBeenCalledExactlyOnceWith({ pan: false });
  });

  it('runs initial fit once after valid bounds and keeps explicit fit separate', async () => {
    const ref = createRef<OperationalMapHandle>();
    const fitBounds = vi.spyOn(L.Map.prototype, 'fitBounds');
    const props = mapProps({
      snapshot: makeOverviewSnapshot({
        routeWest: [
          { latitude: 39, longitude: -104 },
          { latitude: 40, longitude: -103 },
        ],
      }),
    });
    const { rerender } = render(<OperationalMap ref={ref} {...props} />);
    await act(async () => undefined);

    expect(fitBounds).toHaveBeenCalledTimes(1);
    rerender(<OperationalMap ref={ref} {...props} />);
    await act(async () => undefined);
    expect(fitBounds).toHaveBeenCalledTimes(1);
    ref.current?.fitToAvailableLayers();
    expect(fitBounds).toHaveBeenCalledTimes(2);
  });

  it('ignores invalid focus without calling Leaflet setView', async () => {
    const ref = createRef<OperationalMapHandle>();
    const setView = vi.spyOn(L.Map.prototype, 'setView');
    render(<OperationalMap ref={ref} {...mapProps()} />);
    await act(async () => undefined);
    setView.mockClear();

    ref.current?.focusCoordinates({
      latitude: 91,
      longitude: -104,
      zoom: 8,
      motion: 'reduced-aware',
    });

    expect(setView).not.toHaveBeenCalled();
  });

  it('measures mouse map events with map.distance and clears the polyline output', async () => {
    const ref = createRef<OperationalMapHandle>();
    render(<OperationalMap ref={ref} {...mapProps()} />);
    await act(async () => undefined);
    const map = ref.current?.getMap() as L.Map;
    const distance = vi.spyOn(map, 'distance').mockReturnValue(185.2);

    fireEvent.click(screen.getByRole('button', { name: 'Measure distance' }));
    act(() => {
      map.fire('click', { latlng: L.latLng(0, 0) });
      map.fire('click', { latlng: L.latLng(0, 1) });
    });

    expect(distance).toHaveBeenCalled();
    expect(screen.getAllByText(/0.1 nautical miles/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Undo point' }));
    expect(screen.getAllByText(/no distance selected/).length).toBeGreaterThan(
      0
    );
    fireEvent.click(screen.getByRole('button', { name: 'Clear measurement' }));
    expect(screen.getAllByText(/no distance selected/).length).toBeGreaterThan(
      0
    );
  });

  it('uses actual matchMedia listeners for mobile lock and removes them on unmount', () => {
    const listeners = new Set<(event: MediaQueryListEvent) => void>();
    const add = vi.fn(
      (_type: string, listener: EventListenerOrEventListenerObject) => {
        if (typeof listener === 'function')
          listeners.add(listener as (event: MediaQueryListEvent) => void);
      }
    );
    const remove = vi.fn(
      (_type: string, listener: EventListenerOrEventListenerObject) => {
        if (typeof listener === 'function')
          listeners.delete(listener as (event: MediaQueryListEvent) => void);
      }
    );
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      media: '(min-width: 768px)',
      onchange: null,
      addEventListener: add,
      removeEventListener: remove,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const { unmount } = render(<OperationalMap {...mapProps()} />);

    expect(add).toHaveBeenCalledWith('change', expect.any(Function));
    expect(
      screen.getByRole('button', { name: 'Enable map interaction' })
    ).toBeInTheDocument();
    expect(listeners).toHaveLength(1);
    unmount();
    expect(remove).toHaveBeenCalledWith('change', expect.any(Function));
    expect(listeners).toHaveLength(0);
  });
});

function mapProps(
  overrides: Partial<React.ComponentProps<typeof OperationalMap>> = {}
): React.ComponentProps<typeof OperationalMap> {
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
