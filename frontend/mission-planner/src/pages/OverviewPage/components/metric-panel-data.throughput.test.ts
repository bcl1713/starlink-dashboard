import { describe, expect, it } from 'vitest';

import { buildThroughputPanelData } from './metric-panel-data';
import { history, NOW, samples } from './metric-panel-test-fixtures';

describe('buildThroughputPanelData', () => {
  it('aligns bounded download and upload samples with upload negative only in chart rows', () => {
    const data = buildThroughputPanelData(
      history([
        {
          metric: 'throughput_up_mbps',
          samples: samples([
            ['2026-08-29T12:29:00Z', 5],
            ['2026-08-29T12:30:00Z', 10],
          ]),
        },
        {
          metric: 'throughput_down_mbps',
          samples: samples([
            ['2026-08-29T12:28:00Z', 100],
            ['2026-08-29T12:30:00Z', 200],
          ]),
        },
      ]),
      NOW
    );

    expect(data.chartRows.map((row) => row.values)).toEqual([
      [100, null],
      [null, -5],
      [200, -10],
    ]);
    expect(data.tableRows.map((row) => row.values)).toEqual([
      [100, null],
      [null, 5],
      [200, 10],
    ]);
    expect(data.tableRows[2].timestamp).toBe('2026-08-29T12:30:00Z');
    expect(data.download).toEqual({
      current: 200,
      min: 100,
      mean: 150,
      max: 200,
    });
    expect(data.upload).toEqual({
      current: 10,
      min: 5,
      mean: 7.5,
      max: 10,
    });
  });

  it('uses download spelling when download and upload are the same instant', () => {
    const data = buildThroughputPanelData(
      history([
        {
          metric: 'throughput_up_mbps',
          samples: samples([['2026-08-29T12:30:00.0Z', 10]]),
        },
        {
          metric: 'throughput_down_mbps',
          samples: samples([['2026-08-29T12:30:00.00Z', 20]]),
        },
      ]),
      NOW
    );

    expect(data.tableRows).toHaveLength(1);
    expect(data.tableRows[0]).toMatchObject({
      timestamp: '2026-08-29T12:30:00.00Z',
      values: [20, 10],
    });
    expect(data.chartRows[0].values).toEqual([20, -10]);
  });

  it('retains the union of independently capped download and upload series', () => {
    const data = buildThroughputPanelData(
      history([
        {
          metric: 'throughput_down_mbps',
          samples: Array.from({ length: 1802 }, (_, index) => ({
            timestamp: fractionalTimestamp(index, 0),
            value: index,
          })),
        },
        {
          metric: 'throughput_up_mbps',
          samples: Array.from({ length: 1802 }, (_, index) => ({
            timestamp: fractionalTimestamp(index, 5),
            value: index,
          })),
        },
      ]),
      NOW
    );

    expect(data.tableRows).toHaveLength(3602);
    expect(data.tableRows[0].timestamp).toBe('2026-08-29T12:00:00.20Z');
    expect(data.tableRows[1].timestamp).toBe('2026-08-29T12:00:00.25Z');
    expect(data.download.current).toBe(1801);
    expect(data.upload.current).toBe(1801);
  });

  it('keeps large finite throughput means finite and rejects invalid values', () => {
    const data = buildThroughputPanelData(
      history([
        {
          metric: 'throughput_down_mbps',
          samples: [
            { timestamp: '2026-08-29T12:29:58Z', value: Number.MAX_VALUE },
            { timestamp: '2026-08-29T12:29:59Z', value: Number.MAX_VALUE },
            { timestamp: '2026-08-29T12:30:00Z', value: -1 },
          ],
        },
        {
          metric: 'throughput_up_mbps',
          samples: [
            { timestamp: '2026-08-29T12:29:58Z', value: Number.NaN },
            { timestamp: '2026-08-29T12:29:59Z', value: Infinity },
            { timestamp: '2026-08-29T12:30:00Z', value: 5 },
          ],
        },
      ]),
      NOW
    );

    expect(data.download.mean).toBe(Number.MAX_VALUE);
    expect(data.upload).toEqual({ current: 5, min: 5, mean: 5, max: 5 });
    expect(data.tableRows.map((row) => row.values)).toEqual([
      [Number.MAX_VALUE, null],
      [Number.MAX_VALUE, null],
      [null, 5],
    ]);
  });
});

function fractionalTimestamp(index: number, extraTenths: number): string {
  const tenths = index + 1;
  const totalSeconds = Math.floor(tenths / 10);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const fraction = tenths % 10;
  return `2026-08-29T12:${String(minutes).padStart(2, '0')}:${String(
    seconds
  ).padStart(2, '0')}.${fraction}${extraTenths}Z`;
}
