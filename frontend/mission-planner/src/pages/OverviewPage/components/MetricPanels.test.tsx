import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { PacketLossPanel } from './PacketLossPanel';
import { ThroughputPanel } from './ThroughputPanel';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';

vi.mock('uplot', () => ({ default: vi.fn() }));

const metricHistory = history([
  {
    metric: 'latency_ms',
    samples: samples([['2026-08-29T12:30:00Z', 200]]),
  },
  {
    metric: 'throughput_down_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 100]]),
  },
  {
    metric: 'throughput_up_mbps',
    samples: samples([['2026-08-29T12:30:00Z', 10]]),
  },
  {
    metric: 'packet_loss_percent',
    samples: samples([['2026-08-29T12:30:00Z', 5]]),
  },
]);

describe('metric history panels', () => {
  it('renders latency threshold, h3 heading, compact host, and disclosure table', () => {
    render(
      <NetworkLatencyPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending={false}
        presentation="compact"
        headingAs="h3"
      />
    );

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      'Network Latency'
    );
    expect(screen.getByText('Critical')).toBeVisible();
    const host = screen.getByTestId('time-series-chart-host');
    expect(host).toHaveClass('min-h-[var(--time-series-chart-height,240px)]');
    expect(host.parentElement?.parentElement).toHaveStyle({
      '--time-series-chart-height': '180px',
    });
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('2026-08-29 12:30:00 UTC')).toBeVisible();
  });

  it('renders throughput magnitude text and packet loss critical boundary', () => {
    render(
      <>
        <ThroughputPanel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
        />
        <PacketLossPanel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
        />
      </>
    );

    expect(
      screen.getByText(/Download 100 Mbps \/ Upload 10 Mbps/)
    ).toBeVisible();
    expect(
      screen.getByRole('region', { name: 'Packet Loss' })
    ).toHaveTextContent('Critical');
  });
});
