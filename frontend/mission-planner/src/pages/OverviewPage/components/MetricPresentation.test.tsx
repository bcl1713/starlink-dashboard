import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { PacketLossPanel } from './PacketLossPanel';
import { ThroughputPanel } from './ThroughputPanel';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';
import type { HistoryMetricPanelProps } from './metric-panel-types';
import { MockResizeObserver, createdPlots, resetUPlotMock } from './uplot.mock';

vi.mock('uplot', async () => ({
  default: (await import('./uplot.mock')).MockUPlot,
}));

const metricHistory = history([
  {
    metric: 'latency_ms',
    samples: samples([['2026-08-29T12:30:00Z', 100]]),
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
    samples: samples([['2026-08-29T12:30:00Z', 2]]),
  },
]);

const panels: readonly [
  string,
  (props: HistoryMetricPanelProps) => React.ReactNode,
][] = [
  ['Network Latency', NetworkLatencyPanel],
  ['Download/Upload Throughput', ThroughputPanel],
  ['Packet Loss', PacketLossPanel],
];

beforeEach(() => {
  resetUPlotMock();
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    width: 640,
    height: 240,
    x: 0,
    y: 0,
    top: 0,
    right: 640,
    bottom: 240,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('history panel presentation', () => {
  it.each(panels)(
    'preserves %s chart root and disclosure state across presentation changes',
    (_title, Panel) => {
      const { rerender } = render(
        <Panel slot={slot(metricHistory)} now={NOW} retryPending={false} />
      );
      const root = createdPlots[0].root;
      fireEvent.click(screen.getByRole('button', { name: 'History' }));
      expect(screen.getByRole('table')).toBeVisible();

      rerender(
        <Panel
          slot={slot(metricHistory)}
          now={NOW}
          retryPending={false}
          presentation="compact"
        />
      );

      expect(createdPlots).toHaveLength(1);
      expect(createdPlots[0].root).toBe(root);
      expect(createdPlots[0].destroy).not.toHaveBeenCalled();
      expect(screen.getByRole('table')).toBeVisible();
      expect(
        screen.getByTestId('time-series-chart-host').parentElement
          ?.parentElement
      ).toHaveStyle('--time-series-chart-height: 180px');
    }
  );
});
