import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TimeSeriesChart } from './TimeSeriesChart';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const uplotMock = vi.hoisted(() => {
  const created: { options: uPlot.Options; data: unknown }[] = [];
  class MockUPlot {
    readonly root = document.createElement('div');
    readonly setData = vi.fn();
    readonly setSize = vi.fn();
    readonly destroy = vi.fn();
    constructor(options: uPlot.Options, data: unknown, target: HTMLElement) {
      this.root.append(document.createElement('canvas'));
      target.append(this.root);
      created.push({ options, data });
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

const latencySeries: readonly TimeSeriesDefinition[] = [
  {
    key: 'latency',
    label: 'Latency',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
];

const packetLossSeries: readonly TimeSeriesDefinition[] = [
  {
    key: 'packetLoss',
    label: 'Packet loss',
    color: '#b42318',
    unit: 'percent',
    display: 'signed',
  },
];

const rows: readonly TimeSeriesRow[] = [
  { timestamp: '2026-08-29T12:00:00Z', epochSeconds: 1, values: [10, null] },
  { timestamp: '2026-08-29T12:00:01Z', epochSeconds: 2, values: [20, -5] },
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

describe('TimeSeriesChart constructor options', () => {
  it('passes throughput order, sign, colors, units, gaps, and zero baseline', () => {
    render(
      <TimeSeriesChart
        accessibleName="Throughput chart"
        rows={rows}
        series={series}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );

    expect(screen.getByRole('img', { name: 'Throughput chart' })).toBeVisible();
    expect(uplotMock.created[0].data).toEqual([
      [1, 2],
      [10, 20],
      [null, -5],
    ]);
    expect(uplotMock.created[0].options.series).toMatchObject([
      {},
      { label: 'Download', stroke: '#1769aa', spanGaps: false },
      { label: 'Upload', stroke: '#177a55', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 12.34)).toBe('12.34 Mbps');
    expect(formatSeriesValue(2, -5.5)).toBe('5.5 Mbps');
    expect(formatSeriesValue(2, null)).toBe('Unavailable');
    expect(formatSeriesValue(2, Number.POSITIVE_INFINITY)).toBe('Unavailable');
    const range = uplotMock.created[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 9]);
  });

  it('passes latency unit formatting without changing label identity', () => {
    render(
      <TimeSeriesChart
        accessibleName="Latency chart"
        rows={rows}
        series={latencySeries}
        yRange="auto"
        zeroBaseline
        emptyText="No data"
      />
    );

    expect(uplotMock.created[0].options.series).toMatchObject([
      {},
      { label: 'Latency', stroke: '#1769aa', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 15)).toBe('15 ms');
    expect(formatSeriesValue(1, Number.NaN)).toBe('Unavailable');
    expect(formatSeriesValue(1, undefined)).toBe('Unavailable');
  });

  it('passes packet-loss unit formatting and fixed y-domain exactly', () => {
    render(
      <TimeSeriesChart
        accessibleName="Packet Loss chart"
        rows={rows}
        series={packetLossSeries}
        yRange={[0, 100]}
        zeroBaseline
        emptyText="No data"
      />
    );

    expect(uplotMock.created[0].options.series).toMatchObject([
      {},
      { label: 'Packet loss', stroke: '#b42318', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 2)).toBe('2 percent');
    expect(formatSeriesValue(1, 2.345)).toBe('2.345 percent');
    const range = uplotMock.created[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 100]);
  });
});

function formatSeriesValue(seriesIndex: number, value: unknown): string {
  const seriesOptions = uplotMock.created[0].options.series?.[seriesIndex];
  const formatter = seriesOptions?.value;
  expect(formatter).toEqual(expect.any(Function));
  return String(
    typeof formatter === 'function'
      ? formatter({} as uPlot, value as number, seriesIndex, 0)
      : formatter
  );
}
