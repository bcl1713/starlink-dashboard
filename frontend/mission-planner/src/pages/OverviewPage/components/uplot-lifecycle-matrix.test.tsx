import { StrictMode } from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const uplotMock = vi.hoisted(() => {
  const created: {
    root: HTMLDivElement;
    setData: ReturnType<typeof vi.fn>;
    setSize: ReturnType<typeof vi.fn>;
    destroy: ReturnType<typeof vi.fn>;
    options: unknown;
    data: unknown;
  }[] = [];
  const flags = { throwConstructor: false };
  class MockUPlot {
    readonly root = document.createElement('div');
    readonly setData = vi.fn();
    readonly setSize = vi.fn();
    readonly destroy = vi.fn();
    readonly options: unknown;
    readonly data: unknown;
    constructor(options: unknown, data: unknown, target: HTMLElement) {
      if (flags.throwConstructor) throw new Error('constructor failed');
      this.options = options;
      this.data = data;
      this.root.append(document.createElement('canvas'));
      target.append(this.root);
      created.push(this);
    }
  }
  return { created, flags, MockUPlot };
});

vi.mock('uplot', () => ({ default: uplotMock.MockUPlot }));

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

class MockResizeObserver {
  static callbacks: ResizeObserverCallback[] = [];
  static throwConstructor = false;
  static throwObserve = false;
  observe = vi.fn(() => {
    if (MockResizeObserver.throwObserve) throw new Error('observe failed');
  });
  disconnect = vi.fn();
  constructor(callback: ResizeObserverCallback) {
    if (MockResizeObserver.throwConstructor) throw new Error('observer failed');
    MockResizeObserver.callbacks.push(callback);
  }
}

beforeEach(() => {
  uplotMock.created.length = 0;
  uplotMock.flags.throwConstructor = false;
  MockResizeObserver.callbacks = [];
  MockResizeObserver.throwConstructor = false;
  MockResizeObserver.throwObserve = false;
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

    expect(uplotMock.created).toHaveLength(2);
    expect(uplotMock.created[0].destroy).toHaveBeenCalledTimes(1);
    expect(uplotMock.created[1].destroy).not.toHaveBeenCalled();

    unmount();
    expect(uplotMock.created[1].destroy).toHaveBeenCalledTimes(1);
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

    expect(uplotMock.created).toHaveLength(1);
    expect(uplotMock.created[0].options).toMatchObject({
      width: 240,
      height: 800,
    });
    expect(uplotMock.created[0].setSize).toHaveBeenCalledTimes(1);
    expect(uplotMock.created[0].setSize).toHaveBeenCalledWith({
      width: 4096,
      height: 160,
    });
    unmount();
  });

  it('keeps textual fallback through observer and constructor failures', () => {
    MockResizeObserver.throwConstructor = true;
    const first = renderChart([]);
    expect(screen.getByText('No data')).toBeVisible();
    expect(uplotMock.created).toHaveLength(0);
    first.unmount();

    uplotMock.created.length = 0;
    MockResizeObserver.throwConstructor = false;
    MockResizeObserver.throwObserve = true;
    uplotMock.flags.throwConstructor = true;
    renderChart([]);
    sizeHost(640, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(screen.getByText('No data')).toBeVisible();
    expect(uplotMock.created).toHaveLength(0);
  });

  it('cleans up once after setData, setSize, and destroy failures', () => {
    const { rerender, unmount } = renderChart();
    sizeHost(640, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    uplotMock.created[0].setSize.mockImplementationOnce(() => {
      throw new Error('setSize failed');
    });
    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(uplotMock.created[0].destroy).toHaveBeenCalledTimes(1);

    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    uplotMock.created[1].setData.mockImplementationOnce(() => {
      throw new Error('setData failed');
    });
    rerenderChart(rerender, [
      { timestamp: '2026-08-29T12:00:02Z', epochSeconds: 3, values: [30, -6] },
    ]);
    expect(uplotMock.created[1].destroy).toHaveBeenCalledTimes(1);

    sizeHost(700, 240);
    MockResizeObserver.callbacks[0]([], {} as ResizeObserver);
    expect(uplotMock.created).toHaveLength(3);
    uplotMock.created[2].destroy.mockImplementationOnce(() => {
      throw new Error('destroy failed');
    });
    unmount();
    expect(uplotMock.created[2].destroy).toHaveBeenCalledTimes(1);
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
    expect(uplotMock.created).toHaveLength(0);
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
