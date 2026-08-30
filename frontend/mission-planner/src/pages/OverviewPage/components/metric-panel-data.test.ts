import { describe, expect, it } from 'vitest';

import { buildLatencyPanelData } from './metric-panel-data';
import { history, samples } from './metric-panel-test-fixtures';

describe('metric panel adapter edge cases', () => {
  it('keeps distinct exact table instants but collapses numeric chart collisions to later exact instant', () => {
    const data = buildLatencyPanelData(
      history([
        {
          metric: 'latency_ms',
          samples: samples([
            ['2026-08-29T12:00:00.0000000000000000001Z', 10],
            ['2026-08-29T12:00:00.0000000000000000002Z', 20],
          ]),
        },
      ]),
      '2026-08-29T12:00:01Z'
    );

    expect(data.tableRows).toHaveLength(2);
    expect(data.chartRows).toHaveLength(1);
    expect(data.chartRows[0].timestamp).toBe(
      '2026-08-29T12:00:00.0000000000000000002Z'
    );
    expect(data.chartRows[0].values[0]).toBe(20);
  });

  it('returns fresh frozen empty results for invalid now', () => {
    const first = buildLatencyPanelData(history([]), 'invalid');
    const second = buildLatencyPanelData(history([]), 'invalid');

    expect(first).toEqual({
      chartRows: [],
      tableRows: [],
      summary: { current: null, min: null, mean: null, max: null },
    });
    expect(first).not.toBe(second);
    expect(Object.isFrozen(first.tableRows)).toBe(true);
  });
});
