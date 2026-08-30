import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { GroundEntryPointPanel } from './GroundEntryPointPanel';
import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { ObstructionGauge } from './ObstructionGauge';
import { POIQuickReference } from './POIQuickReference';
import { PacketLossPanel } from './PacketLossPanel';
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

type PublicPanel = {
  readonly title: string;
  readonly render: (nextSlot: OverviewSourceSlot<unknown>) => React.ReactNode;
  readonly data: unknown;
  readonly readyText: string;
};

const panels: readonly PublicPanel[] = [
  {
    title: 'Network Latency',
    data: monitoringHistory,
    readyText: 'Warning',
    render: (nextSlot) => (
      <NetworkLatencyPanel
        slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
        now={NOW}
        retryPending={false}
      />
    ),
  },
  {
    title: 'Download/Upload Throughput',
    data: monitoringHistory,
    readyText: 'Magnitude display',
    render: (nextSlot) => (
      <ThroughputPanel
        slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
        now={NOW}
        retryPending={false}
      />
    ),
  },
  {
    title: 'Packet Loss',
    data: monitoringHistory,
    readyText: 'Normal',
    render: (nextSlot) => (
      <PacketLossPanel
        slot={nextSlot as OverviewSourceSlot<MonitoringHistory>}
        now={NOW}
        retryPending={false}
      />
    ),
  },
  {
    title: 'Obstruction %',
    data: obstruction,
    readyText: 'Normal',
    render: (nextSlot) => (
      <ObstructionGauge
        slot={nextSlot as OverviewSourceSlot<OverviewStatus>}
        retryPending={false}
      />
    ),
  },
  {
    title: 'Ground Entry Point',
    data: gep,
    readyText: 'Seattle POP',
    render: (nextSlot) => (
      <GroundEntryPointPanel
        slot={nextSlot as OverviewSourceSlot<GroundEntryPoint>}
        retryPending={false}
      />
    ),
  },
  {
    title: 'POI Quick Reference (Top 5)',
    data: pois,
    readyText: 'Waypoint One',
    render: (nextSlot) => (
      <POIQuickReference
        slot={nextSlot as OverviewSourceSlot<POIETAResponse>}
        retryPending={false}
      />
    ),
  },
];

describe('public panel state matrix', () => {
  it.each(panels)(
    'exercises initial, ready, retained, terminal, and timestamp states for $title',
    (panel) => {
      const { rerender } = render(
        panel.render(stateSlot(undefined, { phase: 'initial-loading' }))
      );
      expect(region(panel.title)).toHaveTextContent('Loading');
      expect(region(panel.title)).not.toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data)));
      expect(region(panel.title)).toHaveTextContent('Ready');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data, { pending: true })));
      expect(region(panel.title)).toHaveTextContent('Refreshing');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data, { phase: 'error' })));
      expect(region(panel.title)).toHaveTextContent('Source refresh failed.');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(undefined, { phase: 'error' })));
      expect(region(panel.title)).toHaveTextContent('Source refresh failed.');
      expect(region(panel.title)).not.toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data, { phase: 'stale' })));
      expect(region(panel.title)).toHaveTextContent('Stale');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data, { phase: 'paused' })));
      expect(region(panel.title)).toHaveTextContent('Paused');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(
        panel.render(
          stateSlot(panel.data, {
            phase: 'unavailable',
            availability: 'unavailable',
          })
        )
      );
      expect(region(panel.title)).toHaveTextContent('Unavailable');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);

      rerender(panel.render(stateSlot(panel.data, { sourceTimestamp: null })));
      expect(region(panel.title)).toHaveTextContent(
        'Source timestamp unavailable'
      );

      rerender(panel.render(stateSlot(panel.data)));
      expect(region(panel.title)).toHaveTextContent('Ready');
      expect(region(panel.title)).toHaveTextContent(panel.readyText);
    }
  );
});

function region(title: string): HTMLElement {
  return screen.getByRole('region', { name: title });
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
