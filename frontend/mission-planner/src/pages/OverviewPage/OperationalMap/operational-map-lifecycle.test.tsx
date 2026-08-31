import { act, render } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, describe, expect, it, type MockInstance, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
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

describe('OperationalMap lifecycle', () => {
  it('keeps vector groups, radar, and basemap identities across data and token rerenders', async () => {
    let map: L.Map | null = null;
    const props = mapProps({ onMapReady: (next) => (map = next) });
    const { rerender } = render(<OperationalMap {...props} />);
    await act(async () => undefined);

    const first = collectLayerIdentities(map);
    expect(first.groups).toHaveLength(11);
    expect(first.radar).toBeTruthy();
    expect(first.basemap).toBeTruthy();

    for (let count = 0; count < 5; count += 1) {
      rerender(
        <OperationalMap
          {...props}
          radarRefreshToken={count + 2}
          snapshot={makeOverviewSnapshot({
            history: [
              ['2026-08-29T12:00:00Z', 10 + count, -10],
              ['2026-08-29T12:00:01Z', 11 + count, -11],
            ],
          })}
        />
      );
      await act(async () => undefined);
      const next = collectLayerIdentities(map);
      expect(next.groups).toEqual(first.groups);
      expect(next.radar).toBe(first.radar);
      expect(next.basemap).toBe(first.basemap);
    }
  });

  it('returns listener, observer, map, layer, inflight, and URL counters to baseline over 20 mounts', async () => {
    let activeObservers = 0;
    class TrackingResizeObserver {
      observe = vi.fn();
      disconnect = vi.fn(() => {
        activeObservers -= 1;
      });
      constructor() {
        activeObservers += 1;
      }
    }
    vi.stubGlobal('ResizeObserver', TrackingResizeObserver);
    const addDocument = vi.spyOn(document, 'addEventListener');
    const removeDocument = vi.spyOn(document, 'removeEventListener');
    const createObjectURL = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:lifecycle');
    const revokeObjectURL = vi
      .spyOn(URL, 'revokeObjectURL')
      .mockImplementation(() => undefined);

    for (let index = 0; index < 20; index += 1) {
      const { unmount } = render(<OperationalMap {...mapProps()} />);
      await act(async () => undefined);
      unmount();
      await act(async () => undefined);

      expect(document.querySelectorAll('.leaflet-container')).toHaveLength(0);
      expect(document.querySelectorAll('.leaflet-layer')).toHaveLength(0);
      expect(activeObservers).toBe(0);
      expect(createObjectURL).toHaveBeenCalledTimes(
        revokeObjectURL.mock.calls.length
      );
      expect(listenerDelta(addDocument, removeDocument, 'keydown')).toBe(0);
    }
  });
});

function collectLayerIdentities(map: L.Map | null) {
  const groups: number[] = [];
  let radar: L.Layer | null = null;
  let basemap: L.Layer | null = null;
  map?.eachLayer((layer) => {
    if (layer instanceof L.TileLayer) basemap = layer;
    else if (layer instanceof L.GridLayer) radar = layer;
    else if (layer instanceof L.LayerGroup) groups.push(L.Util.stamp(layer));
  });
  return { groups: groups.sort((left, right) => left - right), radar, basemap };
}

function listenerDelta(
  add: MockInstance<typeof document.addEventListener>,
  remove: MockInstance<typeof document.removeEventListener>,
  type: string
): number {
  return (
    add.mock.calls.filter((call) => call[0] === type).length -
    remove.mock.calls.filter((call) => call[0] === type).length
  );
}

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
