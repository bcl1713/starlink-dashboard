import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const uplotMock = vi.hoisted(() => {
  const createdPlots: {
    root: HTMLDivElement;
    setData: ReturnType<typeof vi.fn>;
    setSize: ReturnType<typeof vi.fn>;
    destroy: ReturnType<typeof vi.fn>;
    options: unknown;
    data: unknown;
    target: HTMLElement;
  }[] = [];
  class MockUPlot {
    readonly root = document.createElement('div');
    readonly setData = vi.fn();
    readonly setSize = vi.fn();
    readonly destroy = vi.fn();
    readonly options: unknown;
    readonly data: unknown;
    readonly target: HTMLElement;

    constructor(options: unknown, data: unknown, target: HTMLElement) {
      this.options = options;
      this.data = data;
      this.target = target;
      this.root.append(document.createElement('canvas'));
      target.append(this.root);
      createdPlots.push(this);
    }
  }
  return { createdPlots, MockUPlot };
});

vi.mock('uplot', () => ({ default: uplotMock.MockUPlot }));

const series: readonly TimeSeriesDefinition[] = [
  {
    key: 'latency',
    label: 'Latency',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
];

const rows: readonly TimeSeriesRow[] = [
  { timestamp: '2026-08-29T12:00:00Z', epochSeconds: 1, values: [10] },
  { timestamp: '2026-08-29T12:00:01Z', epochSeconds: 2, values: [null] },
];

class MockResizeObserver {
  static callbacks: ResizeObserverCallback[] = [];
  observe = vi.fn();
  disconnect = vi.fn();
  constructor(callback: ResizeObserverCallback) {
    MockResizeObserver.callbacks.push(callback);
  }
}

beforeEach(() => {
  uplotMock.createdPlots.length = 0;
  MockResizeObserver.callbacks = [];
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
});

describe('TimeSeriesChart', () => {
  it('creates after valid size, labels one img root, and preserves null gaps', () => {
    const { container } = render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    const host = screen.getByTestId('time-series-chart-host');
    vi.spyOn(host, 'getBoundingClientRect').mockReturnValue({
      width: 640,
      height: 240,
      x: 0,
      y: 0,
      top: 0,
      right: 640,
      bottom: 240,
      left: 0,
      toJSON: () => ({}),
    });

    expect(uplotMock.createdPlots).toHaveLength(0);
    MockResizeObserver.callbacks[0]?.([], {} as ResizeObserver);

    expect(uplotMock.createdPlots).toHaveLength(1);
    expect(screen.getByRole('img', { name: 'Latency chart' })).toBe(
      uplotMock.createdPlots[0].root
    );
    expect(container.querySelector('canvas')).toHaveAttribute(
      'aria-hidden',
      'true'
    );
    expect(uplotMock.createdPlots[0].data).toEqual([
      [1, 2],
      [10, null],
    ]);
  });

  it('updates data by rows identity without recreating for duplicate references', () => {
    const { rerender } = render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    const host = screen.getByTestId('time-series-chart-host');
    vi.spyOn(host, 'getBoundingClientRect').mockReturnValue({
      width: 640,
      height: 240,
      x: 0,
      y: 0,
      top: 0,
      right: 640,
      bottom: 240,
      left: 0,
      toJSON: () => ({}),
    });
    MockResizeObserver.callbacks[0]?.([], {} as ResizeObserver);
    rerender(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    expect(uplotMock.createdPlots[0].setData).not.toHaveBeenCalled();

    const nextRows = [{ ...rows[0], values: [11] }] as const;
    rerender(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={nextRows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    expect(uplotMock.createdPlots[0].setData).toHaveBeenCalledTimes(1);
  });
});
