import { StrictMode } from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';
import {
  MockResizeObserver,
  createdPlots,
  resetUPlotMock,
  uplotMockFlags,
} from './uplot.mock';

vi.mock('uplot', async () => ({
  default: (await import('./uplot.mock')).MockUPlot,
}));

const series: readonly TimeSeriesDefinition[] = [
  {
    key: 'download',
    label: 'Download',
    color: '#1769aa',
    unit: 'Mbps',
    display: 'magnitude',
  },
  {
    key: 'upload',
    label: 'Upload',
    color: '#177a55',
    unit: 'Mbps',
    display: 'magnitude',
  },
];

const rows: readonly TimeSeriesRow[] = [
  { timestamp: '2026-08-29T12:00:00Z', epochSeconds: 1, values: [10, null] },
  { timestamp: '2026-08-29T12:00:01Z', epochSeconds: 2, values: [20, -5] },
];

beforeEach(() => {
  resetUPlotMock();
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('uPlot lifecycle matrix', () => {
  it('matches StrictMode rehearsal create/destroy and leaves one live instance', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
      domRect(640, 240)
    );
    const { unmount } = render(
      <StrictMode>
        <TimeSeriesChart
          accessibleName="Throughput chart"
          rows={rows}
          series={series}
          yRange="auto"
          zeroBaseline
          emptyText="No data"
        />
      </StrictMode>
    );
    MockResizeObserver.callbacks.forEach((callback) =>
      callback([], {} as ResizeObserver)
    );

    expect(createdPlots).toHaveLength(2);
    expect(createdPlots[0].destroy).toHaveBeenCalledTimes(1);
    expect(createdPlots[1].destroy).not.toHaveBeenCalled();

    unmount();
    expect(createdPlots[1].destroy).toHaveBeenCalledTimes(1);
  });

  it('ignores invalid dimensions, rounds and clamps valid size changes', () => {
    const { unmount } = renderChart();
    const host = screen.getByTestId('time-series-chart-host');
    const rect = vi.spyOn(host, 'getBoundingClientRect');
    rect.mockReturnValue(domRect(0, Number.NaN));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockReturnValue(domRect(-1, 240));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockReturnValue(domRect(Number.POSITIVE_INFINITY, 240));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockImplementationOnce(() => {
      throw new Error('measurement failed');
    });
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockReturnValue(domRect(120.4, 900.6));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockReturnValue(domRect(120.4, 900.6));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    rect.mockReturnValue(domRect(5000, 100));
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);

    expect(createdPlots).toHaveLength(1);
    expect(createdPlots[0].options).toMatchObject({
      width: 240,
      height: 800,
    });
    expect(createdPlots[0].setSize).toHaveBeenCalledTimes(1);
    expect(createdPlots[0].setSize).toHaveBeenCalledWith({
      width: 4096,
      height: 160,
    });
    unmount();
  });

  it('keeps textual fallback through observer and constructor failures', () => {
    MockResizeObserver.throwConstructor = true;
    const first = renderChart([]);
    expect(screen.getByText('No data')).toBeVisible();
    expect(createdPlots).toHaveLength(0);
    first.unmount();

    createdPlots.length = 0;
    MockResizeObserver.throwConstructor = false;
    MockResizeObserver.throwObserve = true;
    uplotMockFlags.throwConstructor = true;
    renderChart([]);
    sizeHost(640, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(screen.getByText('No data')).toBeVisible();
    expect(createdPlots).toHaveLength(0);
  });

  it('cleans up once after setData, setSize, and destroy failures', () => {
    const { rerender, unmount } = renderChart();
    sizeHost(640, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    createdPlots[0].setSize.mockImplementationOnce(() => {
      throw new Error('setSize failed');
    });
    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(createdPlots[0].destroy).toHaveBeenCalledTimes(1);

    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    createdPlots[1].setData.mockImplementationOnce(() => {
      throw new Error('setData failed');
    });
    rerenderChart(rerender, [
      { timestamp: '2026-08-29T12:00:02Z', epochSeconds: 3, values: [30, -6] },
    ]);
    expect(createdPlots[1].destroy).toHaveBeenCalledTimes(1);

    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(createdPlots).toHaveLength(3);
    createdPlots[2].destroy.mockImplementationOnce(() => {
      throw new Error('destroy failed');
    });
    unmount();
    expect(createdPlots[2].destroy).toHaveBeenCalledTimes(1);
  });

  it('survives observer observe and measurement hostility with fallback text', () => {
    MockResizeObserver.throwObserve = true;
    const first = renderChart([]);
    expect(MockResizeObserver.callbacks).toHaveLength(1);
    expect(screen.getByText('No data')).toBeVisible();
    first.unmount();

    MockResizeObserver.throwObserve = false;
    renderChart([]);
    const host = screen.getByTestId('time-series-chart-host');
    vi.spyOn(host, 'getBoundingClientRect').mockImplementation(() => {
      throw new Error('measurement failed');
    });
    MockResizeObserver.callbacks.at(-1)?.([], {} as ResizeObserver);

    expect(screen.getByText('No data')).toBeVisible();
    expect(createdPlots).toHaveLength(0);
  });
});

function renderChart(nextRows: readonly TimeSeriesRow[] = rows) {
  return render(
    <TimeSeriesChart
      accessibleName="Throughput chart"
      rows={nextRows}
      series={series}
      yRange="auto"
      zeroBaseline
      emptyText="No data"
    />
  );
}

function rerenderChart(
  rerender: ReturnType<typeof render>['rerender'],
  nextRows: readonly TimeSeriesRow[]
) {
  rerender(
    <TimeSeriesChart
      accessibleName="Throughput chart"
      rows={nextRows}
      series={series}
      yRange="auto"
      zeroBaseline
      emptyText="No data"
    />
  );
}

function sizeHost(width: number, height: number): void {
  vi.spyOn(
    screen.getByTestId('time-series-chart-host'),
    'getBoundingClientRect'
  ).mockReturnValue(domRect(width, height));
}

function domRect(width: number, height: number): DOMRect {
  return {
    width,
    height,
    x: 0,
    y: 0,
    top: 0,
    right: width,
    bottom: height,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect;
}
