import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { GroundEntryPointPanel } from './GroundEntryPointPanel';
import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { ObstructionGauge } from './ObstructionGauge';
import { PacketLossPanel } from './PacketLossPanel';
import { POIQuickReference } from './POIQuickReference';
import { ThroughputPanel } from './ThroughputPanel';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';
import type {
  GroundEntryPoint,
  OverviewStatus,
  POIETAResponse,
} from '../../../types/monitoring';

vi.mock('uplot', () => ({ default: vi.fn() }));

const metricHistory = history([
  { metric: 'latency_ms', samples: samples([['2026-08-29T12:30:00Z', 10]]) },
  {
    metric: 'throughput_down_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 10]]),
  },
  {
    metric: 'throughput_up_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 1]]),
  },
  {
    metric: 'packet_loss_percent',
    samples: samples([['2026-08-29T12:30:00Z', 1]]),
  },
]);

describe('panel heading propagation', () => {
  it('passes h3 through all six overview panels with one heading each', () => {
    render(
      <>
        <NetworkLatencyPanel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
          headingAs="h3"
        />
        <ThroughputPanel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
          headingAs="h3"
        />
        <PacketLossPanel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
          headingAs="h3"
        />
        <ObstructionGauge
          slot={slot({
            obstruction: { obstruction_percent: 1 },
          } as OverviewStatus)}
          retryPending={false}
          headingAs="h3"
        />
        <GroundEntryPointPanel
          slot={slot({
            available: true,
            display: 'Seattle POP',
            city: 'Seattle',
            region: 'WA',
            country: 'US',
            latitude: 47,
            longitude: -122,
            observed_at: '2026-08-29T12:30:00Z',
            generated_at: '2026-08-29T12:30:01Z',
          } as GroundEntryPoint)}
          retryPending={false}
          headingAs="h3"
        />
        <POIQuickReference
          slot={slot({
            total: 0,
            timestamp: '2026-08-29T12:30:00Z',
            pois: [],
          } as POIETAResponse)}
          retryPending={false}
          headingAs="h3"
        />
      </>
    );

    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(6);
    expect(screen.queryAllByRole('heading', { level: 2 })).toHaveLength(0);
  });
});
