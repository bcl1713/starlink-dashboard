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
  it('passes ordered data, null gaps, colors, domain and zero-baseline range', () => {
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
    expect(uplotMock.created[0].options.series).toEqual([
      {},
      { label: 'Download', stroke: '#1769aa', spanGaps: false },
      { label: 'Upload', stroke: '#177a55', spanGaps: false },
    ]);
    const range = uplotMock.created[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 9]);
  });

  it('passes fixed y-domain exactly when configured', () => {
    render(
      <TimeSeriesChart
        accessibleName="Packet Loss chart"
        rows={rows}
        series={series}
        yRange={[0, 100]}
        zeroBaseline
        emptyText="No data"
      />
    );

    const range = uplotMock.created[0].options.scales?.y?.range;
    expect(
      typeof range === 'function' ? range({} as uPlot, 4, 9, 'y') : null
    ).toEqual([0, 100]);
  });
});
