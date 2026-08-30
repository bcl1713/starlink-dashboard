import { describe, expect, it } from 'vitest';

import { buildLatencyPanelData } from './metric-panel-data';
import {
  buildLinearLatencyPanel,
  type LatencyProjectionInstrumentation,
} from './metric-panel-latency';
import { history, NOW, samples } from './metric-panel-test-fixtures';

describe('buildLatencyPanelData', () => {
  it('uses canonical latency samples for rolling rows and immutable summaries', () => {
    const input = history([
      {
        metric: 'packet_loss_percent',
        samples: samples([['2026-08-29T12:29:00Z', 99]]),
      },
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
    ]);

    const data = buildLatencyPanelData(input, NOW);

    expect(data.summary).toEqual({
      current: 200,
      min: 100,
      mean: 150,
      max: 200,
    });
    expect(data.tableRows.map((row) => row.timestamp)).toEqual([
      '2026-08-29T12:24:59Z',
      '2026-08-29T12:25:00Z',
      '2026-08-29T12:26:00Z',
      '2026-08-29T12:27:00Z',
      '2026-08-29T12:30:00Z',
    ]);
    expect(data.chartRows.map((row) => row.values)).toEqual([
      [300, 300, 300, 300],
      [100, 100, 200, 300],
      [null, 100, 200, 300],
      [null, 100, 200, 300],
      [200, 100, 150, 200],
    ]);
    expect(Object.isFrozen(data)).toBe(true);
    expect(Object.isFrozen(data.chartRows[0].values)).toBe(true);
    expect(data.chartRows).not.toBe(input.series[1].samples);
  });

  it('returns unavailable rows for duplicate or missing canonical latency series', () => {
    expect(
      buildLatencyPanelData(
        history([
          { metric: 'latency_ms', samples: [] },
          { metric: 'latency_ms', samples: [] },
        ]),
        NOW
      )
    ).toEqual({
      chartRows: [],
      tableRows: [],
      summary: { current: null, min: null, mean: null, max: null },
    });
    expect(buildLatencyPanelData(history([]), 'invalid')).toEqual({
      chartRows: [],
      tableRows: [],
      summary: { current: null, min: null, mean: null, max: null },
    });
  });

  it('uses exact timestamp arithmetic for five-minute rolling membership', () => {
    const data = buildLatencyPanelData(
      history([
        {
          metric: 'latency_ms',
          samples: samples([
            ['2026-08-29T12:25:00.0000000Z', 100],
            ['2026-08-29T12:30:00.0000001Z', 200],
          ]),
        },
      ]),
      '2026-08-29T12:30:00.0000001Z'
    );

    expect(data.tableRows[1].values).toEqual([200, 200, 200, 200]);
    expect(data.summary).toEqual({
      current: 200,
      min: 200,
      mean: 200,
      max: 200,
    });
  });

  it('keeps exact inclusive boundaries with adversarial fractional instants', () => {
    const data = buildLatencyPanelData(
      history([
        {
          metric: 'latency_ms',
          samples: samples([
            ['2026-08-29T12:24:59.9999999Z', 10],
            ['2026-08-29T12:25:00.0000000Z', 20],
            ['2026-08-29T12:25:00.0000001Z', 30],
            ['2026-08-29T12:30:00.0000000Z', null],
            ['2026-08-29T12:30:00.0000001Z', 40],
          ]),
        },
      ]),
      '2026-08-29T12:30:00.0000001Z'
    );

    expect(data.tableRows.map((row) => row.values)).toEqual([
      [10, 10, 10, 10],
      [20, 10, 15, 20],
      [30, 10, 20, 30],
      [null, 20, 25, 30],
      [40, 30, 35, 40],
    ]);
    expect(data.summary).toEqual({
      current: 40,
      min: 30,
      mean: 35,
      max: 40,
    });
  });

  it('returns finite means for large finite retained values', () => {
    const data = buildLatencyPanelData(
      history([
        {
          metric: 'latency_ms',
          samples: samples([
            ['2026-08-29T12:29:59Z', Number.MAX_VALUE],
            ['2026-08-29T12:30:00Z', Number.MAX_VALUE],
          ]),
        },
      ]),
      NOW
    );

    expect(data.summary.mean).toBe(Number.MAX_VALUE);
    expect(data.tableRows[1].values[2]).toBe(Number.MAX_VALUE);
  });

  it('caps latency history and projects 1801 samples with linear visits', () => {
    const instrumentation: LatencyProjectionInstrumentation = {
      parsed: 0,
      visited: 0,
      enqueued: 0,
      dequeued: 0,
      minQueueOperations: 0,
      maxQueueOperations: 0,
    };
    const data = buildLinearLatencyPanel(
      Array.from({ length: 1801 }, (_, index) => ({
        timestamp: secondTimestamp(index + 1),
        value: index + 1,
      })),
      instrumentation
    );

    expect(data.tableRows).toHaveLength(1801);
    expect(data.tableRows[0].timestamp).toBe('2026-08-29T12:00:01Z');
    expect(data.summary.current).toBe(1801);
    expect(data.tableRows.at(-1)?.values).toEqual([1801, 1501, 1651, 1801]);
    expect(instrumentation.parsed).toBe(1801);
    expect(instrumentation.visited).toBe(1801);
    expect(instrumentation.enqueued).toBe(1801);
    expect(instrumentation.dequeued).toBe(1500);
    expect(instrumentation.minQueueOperations).toBeLessThanOrEqual(3602);
    expect(instrumentation.maxQueueOperations).toBeLessThanOrEqual(3602);
  });

  it('treats nonfinite and negative latency as null without poisoning summaries', () => {
    const data = buildLatencyPanelData(
      history([
        {
          metric: 'latency_ms',
          samples: [
            { timestamp: '2026-08-29T12:29:58Z', value: Number.NaN },
            { timestamp: '2026-08-29T12:29:59Z', value: Infinity },
            { timestamp: '2026-08-29T12:30:00Z', value: -1 },
            { timestamp: '2026-08-29T12:30:01Z', value: 10 },
          ],
        },
      ]),
      '2026-08-29T12:30:01Z'
    );

    expect(data.tableRows.map((row) => row.values[0])).toEqual([
      null,
      null,
      null,
      10,
    ]);
    expect(data.summary).toEqual({ current: 10, min: 10, mean: 10, max: 10 });
  });
});

function secondTimestamp(offset: number): string {
  const minute = Math.floor(offset / 60);
  const second = offset % 60;
  return `2026-08-29T12:${String(minute).padStart(2, '0')}:${String(
    second
  ).padStart(2, '0')}Z`;
}
