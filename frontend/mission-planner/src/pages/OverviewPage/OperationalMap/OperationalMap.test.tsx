import { createRef } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { describe, expect, it, vi } from 'vitest';

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

describe('OperationalMap', () => {
  it('keeps one map instance and exposes explicit fit/focus controls', async () => {
    const onMapReady = vi.fn();
    const ref = createRef<OperationalMapHandle>();
    const props = mapProps({ onMapReady });
    const { rerender } = render(<OperationalMap ref={ref} {...props} />);

    await act(async () => undefined);
    const map = ref.current?.getMap();
    expect(map).toBeTruthy();
    expect(onMapReady).toHaveBeenCalledTimes(1);
    for (let count = 0; count < 5; count += 1) {
      rerender(
        <OperationalMap
          ref={ref}
          {...props}
          snapshot={makeOverviewSnapshot()}
        />
      );
    }
    expect(ref.current?.getMap()).toBe(map);
    expect(onMapReady).toHaveBeenCalledTimes(1);

    expect(() =>
      ref.current?.focusCoordinates({
        latitude: 39,
        longitude: -104,
        zoom: 8,
        motion: 'reduced-aware',
      })
    ).not.toThrow();
    expect(() =>
      ref.current?.focusCoordinates({
        latitude: 91,
        longitude: -104,
        zoom: 8,
        motion: 'reduced-aware',
      })
    ).not.toThrow();
    expect(() => ref.current?.fitToAvailableLayers()).not.toThrow();
  });

  it('renders disclosure controls, feature details, and text safely', () => {
    const onRadarEnabledChange = vi.fn();
    const retryRadar = vi.fn();
    render(
      <OperationalMap
        {...mapProps({
          onRadarEnabledChange,
          retryRadar,
          snapshot: makeOverviewSnapshot({
            radarPhase: 'error',
            radarError: true,
          }),
        })}
        radarEnabled={false}
      />
    );

    expect(screen.getAllByRole('checkbox')).toHaveLength(12);
    fireEvent.click(screen.getByLabelText('Weather Radar'));
    expect(onRadarEnabledChange).toHaveBeenCalledWith(true);
    fireEvent.click(
      screen.getByRole('button', { name: 'Retry weather radar' })
    );
    expect(retryRadar).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /Departure <script>/ }));
    expect(screen.getAllByText('Departure <script>').length).toBeGreaterThan(0);
    expect(screen.getByText(/Category: departure/)).toBeInTheDocument();
    expect(screen.getByText(/ETA seconds: 120/)).toBeInTheDocument();
    expect(document.body.querySelector('script')).toBeNull();
    expect(
      screen.getByText('Operational map textual equivalent')
    ).toBeInTheDocument();
  });

  it('keeps the scrollable map summary keyboard reachable', () => {
    render(<OperationalMap {...mapProps()} />);
    const summary = screen.getByLabelText('Map status and layer summary');
    expect(summary).toHaveAttribute('tabindex', '0');
  });

  it.each([
    [0, '0deg'],
    [90, '90deg'],
    [359, '359deg'],
    [450, '90deg'],
    [-10, '350deg'],
  ])(
    'applies initial aircraft heading %s after marker mount',
    async (heading, expected) => {
      render(
        <OperationalMap
          {...mapProps({ snapshot: makeOverviewSnapshot({ heading }) })}
        />
      );

      await act(async () => undefined);
      const aircraft = document.querySelector('.operational-map__aircraft');
      expect(aircraft).toBeInstanceOf(HTMLElement);
      expect(
        (aircraft as HTMLElement).style.getPropertyValue('--aircraft-heading')
      ).toBe(expected);
    }
  );

  it('keeps basemap status independent and recovers on tile load', async () => {
    let map: L.Map | null = null;
    render(
      <OperationalMap {...mapProps({ onMapReady: (next) => (map = next) })} />
    );
    await act(async () => undefined);
    const basemap = findBasemap(map);

    expect(screen.getByText(/Basemap: loading/)).toBeInTheDocument();
    act(() => {
      basemap.fire('tileerror', { error: new Error('<img src=x>') });
    });
    expect(screen.getByText(/Basemap: unavailable/)).toBeInTheDocument();
    expect(
      screen.getByText(/Unable to load basemap tiles/)
    ).toBeInTheDocument();
    expect(document.body.querySelector('img[src="x"]')).toBeNull();

    act(() => {
      basemap.fire('tileload');
    });
    expect(screen.getByText(/Basemap: ready/)).toBeInTheDocument();
  });

  it('locks mobile interaction until activation and restores on Escape', () => {
    const restoreMatchMedia = installMatchMedia(false);
    render(<OperationalMap {...mapProps()} />);

    const activate = screen.getByRole('button', {
      name: 'Enable map interaction',
    });
    expect(activate).toBeInTheDocument();
    fireEvent.click(activate);
    expect(
      screen.getByRole('button', { name: 'Return to page scrolling' })
    ).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(
      screen.getByRole('button', { name: 'Enable map interaction' })
    ).toHaveFocus();
    restoreMatchMedia();
  });
});

function mapProps(
  overrides: Partial<React.ComponentProps<typeof OperationalMap>> = {}
): React.ComponentProps<typeof OperationalMap> {
  return {
    snapshot: makeOverviewSnapshot({
      routeWest: [
        { latitude: 39, longitude: -104 },
        { latitude: 40, longitude: -103 },
      ],
    }),
    radarEnabled: true,
    radarRefreshToken: 1,
    retryRadar: vi.fn(),
    reportRadarResult: vi.fn(),
    onRadarEnabledChange: vi.fn(),
    ...overrides,
  };
}

function findBasemap(map: L.Map | null): L.TileLayer {
  let basemap: L.TileLayer | null = null;
  map?.eachLayer((layer) => {
    if (
      layer instanceof L.TileLayer &&
      layer.options.pane === 'operational-basemap'
    ) {
      basemap = layer;
    }
  });
  if (!basemap) throw new Error('Missing basemap layer');
  return basemap;
}

function installMatchMedia(matches: boolean) {
  const original = window.matchMedia;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  window.matchMedia = vi.fn(
    (query: string): MediaQueryList =>
      ({
        matches,
        media: query,
        onchange: null,
        addEventListener: (
          _type: string,
          listener: EventListenerOrEventListenerObject
        ) => {
          if (typeof listener === 'function') {
            listeners.add(listener as (event: MediaQueryListEvent) => void);
          }
        },
        removeEventListener: (
          _type: string,
          listener: EventListenerOrEventListenerObject
        ) => {
          if (typeof listener === 'function') {
            listeners.delete(listener as (event: MediaQueryListEvent) => void);
          }
        },
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }) as MediaQueryList
  );
  return () => {
    window.matchMedia = original;
  };
}
