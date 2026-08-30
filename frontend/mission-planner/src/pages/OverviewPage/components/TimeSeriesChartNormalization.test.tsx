import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';
import { MockResizeObserver, createdPlots, resetUPlotMock } from './uplot.mock';

vi.mock('uplot', async () => ({
  default: (await import('./uplot.mock')).MockUPlot,
}));

const series: readonly TimeSeriesDefinition[] = [
  {
    key: 'latency',
    label: 'Latency',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
];

beforeEach(() => {
  resetUPlotMock();
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

    expect(createdPlots[0].data).toEqual([
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

    expect(createdPlots[0].setData).toHaveBeenCalledWith([[5], [null]]);
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
