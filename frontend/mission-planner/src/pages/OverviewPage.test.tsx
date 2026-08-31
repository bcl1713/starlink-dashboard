import { fireEvent, render, screen, within } from '@testing-library/react';
import { forwardRef, useImperativeHandle } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { OverviewDataSnapshot } from './OverviewPage/overview-data-types';
import { makeOverviewSnapshot } from './OverviewPage/OperationalMap/test-fixtures';
import { OverviewPage } from './OverviewPage';

const mocks = vi.hoisted(() => ({
  snapshot: null as OverviewDataSnapshot | null,
  manualRefresh: vi.fn(),
  retryRadar: vi.fn(),
  reportRadarResult: vi.fn(),
  focusCoordinates: vi.fn(),
  useOverviewData: vi.fn(),
  panelProps: [] as { name: string; props: Record<string, unknown> }[],
  setMapProps: vi.fn(),
}));

vi.mock('./OverviewPage/useOverviewClock', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./OverviewPage/useOverviewClock')>()),
  useOverviewClock: () => new Date('2026-08-31T05:00:00.000Z'),
}));

vi.mock('./OverviewPage/useOverviewData', () => ({
  useOverviewData: (options: unknown) => mocks.useOverviewData(options),
}));

vi.mock('./OverviewPage/OperationalMap', () => ({
  OperationalMap: forwardRef((_props: Record<string, unknown>, ref) => {
    mocks.setMapProps(_props);
    useImperativeHandle(ref, () => ({
      fitToAvailableLayers: vi.fn(),
      focusCoordinates: mocks.focusCoordinates,
      getMap: () => null,
    }));
    return <div data-testid="operational-map">Map tree</div>;
  }),
}));

vi.mock('./OverviewPage/components/NetworkLatencyPanel', () => ({
  NetworkLatencyPanel: (props: Record<string, unknown>) =>
    panel('Network Latency', props),
}));
vi.mock('./OverviewPage/components/ThroughputPanel', () => ({
  ThroughputPanel: (props: Record<string, unknown>) =>
    panel('Throughput', props),
}));
vi.mock('./OverviewPage/components/PacketLossPanel', () => ({
  PacketLossPanel: (props: Record<string, unknown>) =>
    panel('Packet Loss', props),
}));
vi.mock('./OverviewPage/components/ObstructionGauge', () => ({
  ObstructionGauge: (props: Record<string, unknown>) =>
    panel('Obstruction', props),
}));
vi.mock('./OverviewPage/components/GroundEntryPointPanel', () => ({
  GroundEntryPointPanel: (props: Record<string, unknown>) => {
    mocks.panelProps.push({ name: 'Ground Entry Point', props });
    return (
      <article>
        <h3>Ground Entry Point</h3>
        <button
          type="button"
          onClick={() =>
            (
              props.onFocusCoordinates as (coordinates: {
                latitude: number;
                longitude: number;
              }) => void
            )({ latitude: 39.7392, longitude: -104.9903 })
          }
        >
          Focus map
        </button>
      </article>
    );
  },
}));
vi.mock('./OverviewPage/components/POIQuickReference', () => ({
  POIQuickReference: (props: Record<string, unknown>) =>
    panel('POI Quick Reference', props),
}));

function panel(name: string, props: Record<string, unknown>) {
  mocks.panelProps.push({ name, props });
  const Heading = props.headingAs === 'h3' ? 'h3' : 'h2';
  return (
    <article>
      <Heading>{name}</Heading>
      <button type="button" onClick={() => (props.onRetry as () => void)()}>
        Retry {name}
      </button>
    </article>
  );
}

function setup(snapshot = makeOverviewSnapshot()) {
  mocks.snapshot = { ...snapshot, announcement: 'Route recovered.' };
  mocks.useOverviewData.mockReturnValue({
    snapshot: mocks.snapshot,
    controller: {
      isManualRefreshPending: false,
      manualRefresh: mocks.manualRefresh,
      radarRefreshToken: 7,
      retryRadar: mocks.retryRadar,
      reportRadarResult: mocks.reportRadarResult,
    },
  });
  render(<OverviewPage />);
}

describe('OverviewPage composition', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => store.set(key, value),
        clear: () => store.clear(),
      },
    });
    mocks.manualRefresh.mockReset();
    mocks.retryRadar.mockReset();
    mocks.reportRadarResult.mockReset();
    mocks.focusCoordinates.mockReset();
    mocks.useOverviewData.mockReset();
    mocks.panelProps = [];
    mocks.setMapProps.mockReset();
  });

  it('owns data preferences, summary, one live region, and exact panel slots', () => {
    setup();

    expect(mocks.useOverviewData).toHaveBeenCalledWith({
      cadence: 1,
      poiFilter: 'departure,arrival',
      radarEnabled: true,
    });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Operations Overview'
    );
    expect(screen.getByText(/Telemetry fresh/)).toBeVisible();
    expect(screen.getByText(/No active route/)).toBeVisible();
    expect(screen.getByText(/39.0000/)).toBeVisible();
    expect(screen.getByText(/Latency Normal/)).toBeVisible();

    const liveRegions = document.querySelectorAll(
      '[aria-live="polite"][aria-atomic="true"]'
    );
    expect(liveRegions).toHaveLength(1);
    expect(liveRegions[0]).toHaveTextContent('Route recovered.');

    expect(mocks.panelProps.map((item) => item.name)).toEqual([
      'Ground Entry Point',
      'Obstruction',
      'Packet Loss',
      'POI Quick Reference',
      'Network Latency',
      'Throughput',
    ]);
    const latency = mocks.panelProps.find(
      (item) => item.name === 'Network Latency'
    );
    expect(latency?.props.slot).toBe(mocks.snapshot?.history);
    expect(latency?.props.now).toBe('2026-08-31T05:00:00.000Z');
    expect(latency?.props.presentation).toBe('compact');
    expect(latency?.props.headingAs).toBe('h2');
  });

  it('wires map radar ownership, retries, preferences, and GEP focus handle', () => {
    setup();
    const controls = screen.getByRole('button', { name: 'Overview controls' });
    fireEvent.click(controls);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    fireEvent.click(
      screen.getByRole('button', { name: 'Retry Network Latency' })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Focus map' }));

    expect(mocks.manualRefresh).toHaveBeenCalledTimes(2);
    const mapProps = mocks.setMapProps.mock.calls.at(-1)?.[0];
    expect(mapProps?.snapshot).toBe(mocks.snapshot);
    expect(mapProps?.radarEnabled).toBe(true);
    expect(mapProps?.radarRefreshToken).toBe(7);
    expect(mapProps?.retryRadar).toBe(mocks.retryRadar);
    expect(mapProps?.reportRadarResult).toBe(mocks.reportRadarResult);
    expect(mocks.focusCoordinates).toHaveBeenCalledWith({
      latitude: 39.7392,
      longitude: -104.9903,
      zoom: 8,
      motion: 'reduced-aware',
    });
    expect(
      within(screen.getByRole('region', { name: 'World clocks' })).getByText(
        'UTC (Zulu)'
      )
    ).toBeVisible();
    expect(
      screen.queryByRole('checkbox', { name: 'Weather radar' })
    ).toBeNull();
  });
});
