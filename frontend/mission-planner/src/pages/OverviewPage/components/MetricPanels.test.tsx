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
    expect(screen.getByText('Current')).toBeVisible();
    expect(screen.getByText('Mean')).toBeVisible();
    expect(screen.queryByText('Min')).not.toBeInTheDocument();
    expect(screen.queryByText('Max')).not.toBeInTheDocument();
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

  it('keeps upload current and mean visible in compact throughput summaries', () => {
    render(
      <ThroughputPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending={false}
        presentation="compact"
      />
    );

    expect(screen.getByText('Download current')).toBeVisible();
    expect(screen.getByText('Download mean')).toBeVisible();
    expect(screen.getByText('Upload current')).toBeVisible();
    expect(screen.getByText('Upload mean')).toBeVisible();
    expect(screen.queryByText('Upload max')).not.toBeInTheDocument();
  });

  it.each([
    ['2026-08-29T12:30:00Z', 99, 'Normal'],
    ['2026-08-29T12:30:01Z', 100, 'Warning'],
    ['2026-08-29T12:30:02Z', 200, 'Critical'],
    ['2026-08-29T12:30:03Z', -1, 'Unavailable'],
    ['2026-08-29T12:30:04Z', Number.POSITIVE_INFINITY, 'Unavailable'],
  ])('renders exact latency threshold %s %s', (timestamp, value, label) => {
    render(
      <NetworkLatencyPanel
        slot={slot(
          history([
            { metric: 'latency_ms', samples: samples([[timestamp, value]]) },
          ])
        )}
        now={timestamp}
        retryPending={false}
      />
    );

    expect(
      screen.getByRole('region', { name: 'Network Latency' })
    ).toHaveTextContent(label);
  });

  it.each([
    ['2026-08-29T12:30:00Z', 1, 'Normal'],
    ['2026-08-29T12:30:01Z', 2, 'Warning'],
    ['2026-08-29T12:30:02Z', 5, 'Critical'],
    ['2026-08-29T12:30:03Z', -1, 'Unavailable'],
    ['2026-08-29T12:30:04Z', Number.POSITIVE_INFINITY, 'Unavailable'],
    ['2026-08-29T12:30:05Z', 101, 'Unavailable'],
    ['2026-08-29T12:30:03Z', Number.NaN, 'Unavailable'],
  ])('renders exact packet loss threshold %s %s', (timestamp, value, label) => {
    render(
      <PacketLossPanel
        slot={slot(
          history([
            { metric: 'packet_loss_percent', samples: [{ timestamp, value }] },
          ])
        )}
        now={timestamp}
        retryPending={false}
      />
    );

    expect(
      screen.getByRole('region', { name: 'Packet Loss' })
    ).toHaveTextContent(label);
  });
});
