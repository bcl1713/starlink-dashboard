import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { PacketLossPanel } from './PacketLossPanel';
import { ThroughputPanel } from './ThroughputPanel';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';
import type { HistoryMetricPanelProps } from './metric-panel-types';

const uplotMock = vi.hoisted(() => {
  const created: { root: HTMLDivElement; destroy: ReturnType<typeof vi.fn> }[] =
    [];
  class MockUPlot {
    readonly root = document.createElement('div');
    readonly setData = vi.fn();
    readonly setSize = vi.fn();
    readonly destroy = vi.fn();
    constructor(_options: unknown, _data: unknown, target: HTMLElement) {
      target.append(this.root);
      created.push(this);
    }
  }
  return { created, MockUPlot };
});

vi.mock('uplot', () => ({ default: uplotMock.MockUPlot }));

class MockResizeObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  constructor() {}
}

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
  uplotMock.created.length = 0;
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
      const root = uplotMock.created[0].root;
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

      expect(uplotMock.created).toHaveLength(1);
      expect(uplotMock.created[0].root).toBe(root);
      expect(uplotMock.created[0].destroy).not.toHaveBeenCalled();
      expect(screen.getByRole('table')).toBeVisible();
      expect(
        screen.getByTestId('time-series-chart-host').parentElement
          ?.parentElement
      ).toHaveStyle('--time-series-chart-height: 180px');
    }
  );
});
