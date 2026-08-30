import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { GroundEntryPointPanel } from './GroundEntryPointPanel';
import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { ObstructionGauge } from './ObstructionGauge';
import { PacketLossPanel } from './PacketLossPanel';
import { POIQuickReference } from './POIQuickReference';
import { ThroughputPanel } from './ThroughputPanel';
import { history, NOW, poi, samples, slot } from './metric-panel-test-fixtures';
import type { OverviewSourceSlot } from '../overview-data-types';
import type {
  GroundEntryPoint,
  MonitoringHistory,
  OverviewStatus,
  POIETAResponse,
} from '../../../types/monitoring';

vi.mock('uplot', () => ({ default: vi.fn() }));

const monitoringHistory = history([
  {
    metric: 'latency_ms',
    samples: samples([['2026-08-29T12:30:00Z', 120]]),
  },
  {
    metric: 'throughput_down_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 40]]),
  },
  {
    metric: 'throughput_up_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 8]]),
  },
  {
    metric: 'packet_loss_percent',
    samples: samples([['2026-08-29T12:30:00Z', 1]]),
  },
]);

const obstruction = {
  obstruction: { obstruction_percent: 4 },
} as OverviewStatus;

const gep: GroundEntryPoint = {
  available: true,
  observed_at: '2026-08-29T12:00:00Z',
  generated_at: '2026-08-29T12:00:01Z',
  display: 'Seattle POP',
  city: 'Seattle',
  region: 'WA',
  country: 'US',
  latitude: 47.6,
  longitude: -122.3,
};

const pois: POIETAResponse = {
  total: 1,
  timestamp: '2026-08-29T12:00:00Z',
  pois: [poi({ poi_id: 'poi-1', name: 'Waypoint One', eta_seconds: 60 })],
};

describe('public panel retry and live-region contract', () => {
  it('covers NetworkLatencyPanel retained retry behavior', async () => {
    await assertRetryMatrix(
      'Network Latency',
      'Warning',
      monitoringHistory,
      (nextSlot, retryPending, onRetry) => (
        <NetworkLatencyPanel
          slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
          now={NOW}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('covers ThroughputPanel retained retry behavior', async () => {
    await assertRetryMatrix(
      'Download/Upload Throughput',
      'Magnitude display',
      monitoringHistory,
      (nextSlot, retryPending, onRetry) => (
        <ThroughputPanel
          slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
          now={NOW}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('covers PacketLossPanel retained retry behavior', async () => {
    await assertRetryMatrix(
      'Packet Loss',
      'Normal',
      monitoringHistory,
      (nextSlot, retryPending, onRetry) => (
        <PacketLossPanel
          slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
          now={NOW}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('covers ObstructionGauge retained retry behavior', async () => {
    await assertRetryMatrix(
      'Obstruction %',
      'Normal',
      obstruction,
      (nextSlot, retryPending, onRetry) => (
        <ObstructionGauge
          slot={nextSlot as OverviewSourceSlot<OverviewStatus>}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('covers GroundEntryPointPanel retained retry behavior', async () => {
    await assertRetryMatrix(
      'Ground Entry Point',
      'Seattle POP',
      gep,
      (nextSlot, retryPending, onRetry) => (
        <GroundEntryPointPanel
          slot={nextSlot as OverviewSourceSlot<GroundEntryPoint>}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('covers POIQuickReference retained retry behavior', async () => {
    await assertRetryMatrix(
      'POI Quick Reference (Top 5)',
      'Waypoint One',
      pois,
      (nextSlot, retryPending, onRetry) => (
        <POIQuickReference
          slot={nextSlot as OverviewSourceSlot<POIETAResponse>}
          retryPending={retryPending}
          onRetry={onRetry}
        />
      )
    );
  });

  it('keeps GEP source errors ahead of available:false projection', () => {
    const unavailableGep = { ...gep, available: false } as GroundEntryPoint;
    render(
      <GroundEntryPointPanel
        slot={stateSlot(unavailableGep, { phase: 'error' })}
        retryPending={false}
        onRetry={vi.fn()}
      />
    );

    const panel = region('Ground Entry Point');
    expect(panel).toHaveTextContent('Source refresh failed.');
    expect(panel).toHaveTextContent('Retry');
    expectNoLocalAnnouncement(panel);
  });
});

async function assertRetryMatrix<T>(
  title: string,
  retainedText: string,
  data: T,
  renderPanel: (
    nextSlot: OverviewSourceSlot<unknown>,
    retryPending: boolean,
    onRetry: () => Promise<void>
  ) => React.ReactNode
): Promise<void> {
  const onRetry = vi.fn().mockResolvedValue(undefined);
  const { container, rerender } = render(
    renderPanel(stateSlot(data, { phase: 'error' }), false, onRetry)
  );
  expect(region(title)).toHaveTextContent('Source refresh failed.');
  expect(region(title)).toHaveTextContent(retainedText);
  expectNoLocalAnnouncement(container);

  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(onRetry).toHaveBeenCalledTimes(1);

  rerender(renderPanel(stateSlot(data, { phase: 'stale' }), false, onRetry));
  expect(region(title)).toHaveTextContent('Stale');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(onRetry).toHaveBeenCalledTimes(2);
  expectNoLocalAnnouncement(container);

  rerender(renderPanel(stateSlot(data, { phase: 'error' }), true, onRetry));
  const disabledRetry = screen.getByRole('button', { name: 'Retry' });
  expect(disabledRetry).toBeDisabled();
  fireEvent.click(disabledRetry);
  expect(onRetry).toHaveBeenCalledTimes(2);
  expectNoLocalAnnouncement(container);

  const rejectedRetry = vi.fn().mockRejectedValue(new Error('retry failed'));
  const unhandled = vi.fn();
  window.addEventListener('unhandledrejection', unhandled);
  rerender(
    renderPanel(stateSlot(data, { phase: 'error' }), false, rejectedRetry)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await Promise.resolve();
  window.removeEventListener('unhandledrejection', unhandled);
  expect(rejectedRetry).toHaveBeenCalledTimes(1);
  expect(unhandled).not.toHaveBeenCalled();
  expect(region(title)).toHaveTextContent('Source refresh failed.');
  expect(region(title)).toHaveTextContent(retainedText);
  expectNoLocalAnnouncement(container);
}

function region(title: string): HTMLElement {
  return screen.getByRole('region', { name: title });
}

function expectNoLocalAnnouncement(container: HTMLElement): void {
  expect(container.querySelector('[aria-live], [role="status"]')).toBeNull();
}

function stateSlot<T>(
  data: T | undefined,
  overrides: Partial<OverviewSourceSlot<T>> = {}
): OverviewSourceSlot<T> {
  const base = slot(data);
  const phase = overrides.phase ?? base.phase;
  return {
    ...base,
    ...overrides,
    phase,
    pending:
      overrides.pending ??
      (phase === 'refreshing' || phase === 'initial-loading'),
    paused: overrides.paused ?? phase === 'paused',
    freshness: overrides.freshness ?? (phase === 'stale' ? 'stale' : 'fresh'),
    error:
      overrides.error ??
      (phase === 'error'
        ? { code: 'request-failed', message: 'Source refresh failed.' }
        : null),
  };
}
