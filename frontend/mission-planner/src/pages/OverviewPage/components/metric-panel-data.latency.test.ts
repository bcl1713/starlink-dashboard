import { describe, expect, it } from 'vitest';

import { buildLatencyPanelData } from './metric-panel-data';
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
});
