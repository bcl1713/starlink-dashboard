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

const rows: readonly TimeSeriesRow[] = [
  { timestamp: '2026-08-29T12:00:00Z', epochSeconds: 1, values: [10] },
  { timestamp: '2026-08-29T12:00:01Z', epochSeconds: 2, values: [null] },
];

beforeEach(() => {
  resetUPlotMock();
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

    expect(createdPlots).toHaveLength(0);
    MockResizeObserver.callbacks[0]?.([], {} as ResizeObserver);

    expect(createdPlots).toHaveLength(1);
    expect(screen.getByRole('img', { name: 'Latency chart' })).toBe(
      createdPlots[0].root
    );
    expect(container.querySelector('canvas')).toHaveAttribute(
      'aria-hidden',
      'true'
    );
    expect(createdPlots[0].data).toEqual([
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
    expect(createdPlots[0].setData).not.toHaveBeenCalled();

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
    expect(createdPlots[0].setData).toHaveBeenCalledTimes(1);
  });

  it('keeps the mounted plot for semantically equal recreated structure', () => {
    const { rerender } = render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={[...series]}
        yRange={[0, 100]}
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
    const observerCount = MockResizeObserver.callbacks.length;
    const root = createdPlots[0].root;

    rerender(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series.map((definition) => ({ ...definition }))}
        yRange={[0, 100]}
        zeroBaseline
        emptyText="No data"
      />
    );

    expect(createdPlots).toHaveLength(1);
    expect(createdPlots[0].root).toBe(root);
    expect(createdPlots[0].destroy).not.toHaveBeenCalled();
    expect(MockResizeObserver.callbacks).toHaveLength(observerCount);
  });

  it('remounts deliberate structural changes when the parent changes key', () => {
    const renderChart = (key: string, nextSeries = series) => (
      <TimeSeriesChart
        key={key}
        accessibleName="Latency chart"
        rows={rows}
        series={nextSeries}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    const { rerender } = render(renderChart('latency'));
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
      renderChart('throughput', [
        ...series,
        {
          key: 'jitter',
          label: 'Jitter',
          color: '#177a55',
          unit: 'ms',
          display: 'signed',
        },
      ])
    );
    const nextHost = screen.getByTestId('time-series-chart-host');
    vi.spyOn(nextHost, 'getBoundingClientRect').mockReturnValue({
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
    MockResizeObserver.callbacks[1]?.([], {} as ResizeObserver);

    expect(createdPlots).toHaveLength(2);
    expect(createdPlots[0].destroy).toHaveBeenCalledTimes(1);
    expect(createdPlots[1].destroy).not.toHaveBeenCalled();
  });

  it('sends six distinct post-creation row references without recreating', () => {
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

    for (let index = 0; index < 6; index += 1) {
      rerender(
        <TimeSeriesChart
          accessibleName="Latency chart"
          rows={[{ ...rows[0], values: [index] }]}
          series={series}
          yRange="auto"
          zeroBaseline
          emptyText="No data"
        />
      );
    }

    expect(createdPlots).toHaveLength(1);
    expect(createdPlots[0].setData).toHaveBeenCalledTimes(6);
  });

  it('encodes domain, zero baseline, colors, and spanGaps in constructor options', () => {
    render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series}
        yRange={[0, 100]}
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

    expect(createdPlots[0].options).toMatchObject({
      scales: { y: { range: expect.any(Function) } },
      series: [{}, { label: 'Latency', stroke: '#1769aa', spanGaps: false }],
    });
  });
});
