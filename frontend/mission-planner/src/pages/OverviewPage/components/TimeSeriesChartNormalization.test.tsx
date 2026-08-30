import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const uplotMock = vi.hoisted(() => {
  const createdPlots: {
    root: HTMLDivElement;
    setData: ReturnType<typeof vi.fn>;
    data: unknown;
  }[] = [];
  class MockUPlot {
    readonly root = document.createElement('div');
    readonly setData = vi.fn();
    readonly setSize = vi.fn();
    readonly destroy = vi.fn();
    readonly data: unknown;

    constructor(_options: unknown, data: unknown, target: HTMLElement) {
      this.data = data;
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

describe('TimeSeriesChart public row normalization', () => {
  it('normalizes hostile rows for constructor and setData without mutating inputs', () => {
    const hostileRows = Object.freeze([
      Object.freeze({
        timestamp: 'bad-x',
        epochSeconds: Number.NaN,
        values: Object.freeze([1, 2]),
      }),
      Object.freeze({
        timestamp: 'short-values',
        epochSeconds: 3,
        values: Object.freeze([Number.POSITIVE_INFINITY]),
      }),
      Object.freeze({
        timestamp: 'long-values',
        epochSeconds: 4,
        values: Object.freeze([undefined, -Infinity, 99]),
      }),
    ]) as readonly unknown[] as readonly TimeSeriesRow[];

    const { rerender } = renderChart(hostileRows);
    sizeHost();
    MockResizeObserver.callbacks[0]?.([], {} as ResizeObserver);

    expect(uplotMock.createdPlots[0].data).toEqual([
      [3, 4],
      [null, null],
    ]);
    expect(hostileRows[2].values).toHaveLength(3);

    const updateRows = Object.freeze([
      Object.freeze({
        timestamp: 'drop-infinite-x',
        epochSeconds: Number.POSITIVE_INFINITY,
        values: Object.freeze([7]),
      }),
      Object.freeze({
        timestamp: 'missing-slot',
        epochSeconds: 5,
        values: Object.freeze([]),
      }),
    ]) as readonly unknown[] as readonly TimeSeriesRow[];
    rerender(renderChartElement(updateRows));

    expect(uplotMock.createdPlots[0].setData).toHaveBeenCalledWith([
      [5],
      [null],
    ]);
  });
});

function renderChart(rows: readonly TimeSeriesRow[]) {
  return render(renderChartElement(rows));
}

function renderChartElement(rows: readonly TimeSeriesRow[]) {
  return (
    <TimeSeriesChart
      accessibleName="Latency chart"
      rows={rows}
      series={series}
      yRange="auto"
      zeroBaseline
      emptyText="No data"
    />
  );
}

function sizeHost(): void {
  vi.spyOn(
    screen.getByTestId('time-series-chart-host'),
    'getBoundingClientRect'
  ).mockReturnValue({
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
}
