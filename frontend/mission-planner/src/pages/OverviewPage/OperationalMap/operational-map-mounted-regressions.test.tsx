import { StrictMode } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import L from 'leaflet';
import { describe, expect, it, vi } from 'vitest';

import { OperationalMap } from './OperationalMap';
import { createDefaultLayerVisibility } from './operational-map-contract';
import { makeOverviewSnapshot } from './test-fixtures';

vi.mock('../../../services/monitoring', () => ({
  getRainViewerRadarTile: vi.fn(() =>
    Promise.resolve({
      bytes: new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer,
      frameTimestamp: '1777294800',
    })
  ),
}));

function eventCallCount(
  calls: readonly (readonly unknown[])[],
  type: string
): number {
  return calls.filter(([eventType]) => eventType === type).length;
}

describe('OperationalMap mounted regressions', () => {
  it('replays StrictMode setup with one basemap and scale through callback changes', async () => {
    let map: L.Map | null = null;
    const firstReady = vi.fn((next: L.Map) => {
      map = next;
    });
    const secondReady = vi.fn((next: L.Map) => {
      map = next;
    });
    const tileOn = vi.spyOn(L.TileLayer.prototype, 'on');
    const tileOff = vi.spyOn(L.TileLayer.prototype, 'off');
    const props = mapProps({ onMapReady: firstReady });
    const { rerender, unmount } = render(
      <StrictMode>
        <OperationalMap {...props} />
      </StrictMode>
    );
    await act(async () => undefined);

    expect(countBasemaps(map)).toBe(1);
    expect(document.querySelectorAll('.leaflet-control-scale')).toHaveLength(1);
    rerender(
      <StrictMode>
        <OperationalMap {...props} onMapReady={secondReady} />
      </StrictMode>
    );
    await act(async () => undefined);

    expect(countBasemaps(map)).toBe(1);
    expect(document.querySelectorAll('.leaflet-control-scale')).toHaveLength(1);
    unmount();

    const onCalls = tileOn.mock.calls;
    const offCalls = tileOff.mock.calls;
    expect(eventCallCount(offCalls, 'tileload')).toBe(
      eventCallCount(onCalls, 'tileload')
    );
    expect(eventCallCount(offCalls, 'tileerror')).toBe(
      eventCallCount(onCalls, 'tileerror')
    );
  });

  it('reveals a hidden aircraft marker with the latest heading and no recreation', async () => {
    const marker = vi.spyOn(L, 'marker');
    const visibility = { ...createDefaultLayerVisibility() };
    visibility['current-position-layer'] = false;
    const props = mapProps({
      initialLayerVisibility: visibility,
      snapshot: makeOverviewSnapshot({ heading: 0 }),
    });
    const { rerender } = render(<OperationalMap {...props} />);
    await act(async () => undefined);
    expect(document.querySelector('.operational-map__aircraft')).toBeNull();

    rerender(
      <OperationalMap
        {...props}
        snapshot={makeOverviewSnapshot({ heading: 90 })}
      />
    );
    fireEvent.click(screen.getByLabelText('Current position'));
    await act(async () => undefined);

    const aircraft = document.querySelector('.operational-map__aircraft');
    expect(
      marker.mock.calls.filter(
        (call) => call[1]?.pane === 'current-position-layer'
      )
    ).toHaveLength(1);
    expect(
      (aircraft as HTMLElement).style.getPropertyValue('--aircraft-heading')
    ).toBe('90deg');
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

function countBasemaps(map: L.Map | null): number {
  let count = 0;
  map?.eachLayer((layer) => {
    if (
      layer instanceof L.TileLayer &&
      layer.options.pane === 'operational-basemap'
    ) {
      count += 1;
    }
  });
  return count;
}
