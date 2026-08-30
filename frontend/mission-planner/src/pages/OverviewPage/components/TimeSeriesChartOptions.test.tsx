import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { TimeSeriesChart } from './TimeSeriesChart';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';
import { MockResizeObserver, createdPlots, resetUPlotMock } from './uplot.mock';

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
    expect(createdPlots[0].data).toEqual([
      [1, 2],
      [10, 20],
      [null, -5],
    ]);
    expect(createdPlots[0].options).toMatchObject({
      series: [
        {},
        { label: 'Download', stroke: '#1769aa', spanGaps: false },
        { label: 'Upload', stroke: '#177a55', spanGaps: false },
      ],
    });
    expect(createdPlots[0].options.series).toMatchObject([
      {},
      { label: 'Download', stroke: '#1769aa', spanGaps: false },
      { label: 'Upload', stroke: '#177a55', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 12.34)).toBe('12.34 Mbps');
    expect(formatSeriesValue(2, -5.5)).toBe('5.5 Mbps');
    expect(formatSeriesValue(2, null)).toBe('Unavailable');
    expect(formatSeriesValue(2, Number.POSITIVE_INFINITY)).toBe('Unavailable');
    const range = createdPlots[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 9]);
  });

  it('passes public latency panel order, colors, ms units, gaps, and auto domain', () => {
    render(
      <NetworkLatencyPanel
        slot={slot(
          history([
            {
              metric: 'latency_ms',
              samples: samples([
                ['2026-08-29T12:24:59Z', 300],
                ['2026-08-29T12:25:00Z', 100],
                ['2026-08-29T12:26:00Z', null],
                ['2026-08-29T12:27:00Z', -1],
                ['2026-08-29T12:30:00Z', 200],
              ]),
            },
          ])
        )}
        now={NOW}
        retryPending={false}
      />
    );

    expect(
      screen.getByRole('img', { name: 'Network Latency chart' })
    ).toBeVisible();
    expect(createdPlots[0].data).toEqual([
      [1788006299, 1788006300, 1788006360, 1788006420, 1788006600],
      [300, 100, null, null, 200],
      [300, 100, 100, 100, 100],
      [300, 200, 200, 200, 150],
      [300, 300, 300, 300, 200],
    ]);
    expect(createdPlots[0].options.series).toMatchObject([
      {},
      { label: 'Current', stroke: '#1769aa', spanGaps: false },
      { label: 'Min (5m)', stroke: '#177a55', spanGaps: false },
      { label: 'Avg (5m)', stroke: '#a96900', spanGaps: false },
      { label: 'Max (5m)', stroke: '#b42318', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 15)).toBe('15 ms');
    expect(formatSeriesValue(2, 12.5)).toBe('12.5 ms');
    expect(formatSeriesValue(3, 0)).toBe('0 ms');
    expect(formatSeriesValue(4, 99)).toBe('99 ms');
    expect(formatSeriesValue(1, null)).toBe('Unavailable');
    expect(formatSeriesValue(1, Number.NaN)).toBe('Unavailable');
    expect(formatSeriesValue(1, undefined)).toBe('Unavailable');
    expect(formatSeriesValue(4, Number.NEGATIVE_INFINITY)).toBe('Unavailable');
    const range = createdPlots[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 9]);
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

    expect(createdPlots[0].options.series).toMatchObject([
      {},
      { label: 'Packet loss', stroke: '#b42318', spanGaps: false },
    ]);
    expect(formatSeriesValue(1, 2)).toBe('2 percent');
    expect(formatSeriesValue(1, 2.345)).toBe('2.345 percent');
    const range = createdPlots[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 100]);
  });
});

function formatSeriesValue(seriesIndex: number, value: unknown): string {
  const seriesOptions = createdPlots[0].options.series?.[seriesIndex];
  const formatter = seriesOptions?.value;
  expect(formatter).toEqual(expect.any(Function));
  return String(
    typeof formatter === 'function'
      ? formatter({} as uPlot, value as number, seriesIndex, 0)
      : formatter
  );
}
