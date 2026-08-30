import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
];

beforeEach(() => {
  resetUPlotMock();
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
});

afterEach(() => vi.unstubAllGlobals());

describe('uPlot lifecycle', () => {
  it('matches create/destroy and observe/disconnect across 20 mount cycles', () => {
    for (let index = 0; index < 20; index += 1) {
      const { unmount } = render(
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
      MockResizeObserver.instances[index].callback([], {} as ResizeObserver);
      unmount();
    }

    expect(createdPlots).toHaveLength(20);
    expect(
      createdPlots.every((plot) => plot.destroy.mock.calls.length === 1)
    ).toBe(true);
    expect(
      MockResizeObserver.instances.every(
        (observer) => observer.disconnect.mock.calls.length === 1
      )
    ).toBe(true);
  });

  it('disconnects an observer once when observe throws', () => {
    MockResizeObserver.throwObserve = true;

    const { unmount } = render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );

    unmount();

    expect(MockResizeObserver.instances[0].disconnect).toHaveBeenCalledTimes(1);
  });

  it('destroys the actual plot once when setData or setSize throws', () => {
    const { rerender, unmount } = render(
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
    const size = {
      width: 640,
      height: 240,
      x: 0,
      y: 0,
      top: 0,
      right: 640,
      bottom: 240,
      left: 0,
      toJSON: () => ({}),
    };
    vi.spyOn(host, 'getBoundingClientRect').mockReturnValue(size);
    MockResizeObserver.instances[0].callback([], {} as ResizeObserver);
    createdPlots[0].setData.mockImplementationOnce(() => {
      throw new Error('setData failed');
    });

    rerender(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={[{ ...rows[0], values: [11] }]}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );
    unmount();

    expect(createdPlots[0].destroy).toHaveBeenCalledTimes(1);
  });
});
