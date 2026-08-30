import { describe, expect, it } from 'vitest';

import {
  buildLatencyPanelData,
  buildPacketLossPanelData,
  buildThroughputPanelData,
} from './metric-panel-data';
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
    expect(first.summary).not.toBe(second.summary);
    expect(Object.isFrozen(first.tableRows)).toBe(true);
    expect(Object.isFrozen(first.summary)).toBe(true);
  });

  it('returns detached throughput summaries in empty result graphs', () => {
    const first = buildThroughputPanelData(history([]), 'invalid');
    const second = buildThroughputPanelData(history([]), 'invalid');

    expect(first.download).not.toBe(first.upload);
    expect(first.download).not.toBe(second.download);
    expect(Object.isFrozen(first.download)).toBe(true);
    expect(Object.isFrozen(first.upload)).toBe(true);
  });

  it('returns empty shapes for missing and duplicate canonical permutations', () => {
    const duplicate = history([
      { metric: 'latency_ms', samples: [] },
      { metric: 'latency_ms', samples: [] },
      { metric: 'throughput_down_mbps', samples: [] },
      { metric: 'throughput_down_mbps', samples: [] },
      { metric: 'throughput_up_mbps', samples: [] },
      { metric: 'packet_loss_percent', samples: [] },
      { metric: 'packet_loss_percent', samples: [] },
    ]);

    expect(
      buildLatencyPanelData(history([]), '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
    expect(
      buildLatencyPanelData(duplicate, '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
    expect(
      buildThroughputPanelData(history([]), '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
    expect(
      buildThroughputPanelData(duplicate, '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
    expect(
      buildPacketLossPanelData(history([]), '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
    expect(
      buildPacketLossPanelData(duplicate, '2026-08-29T12:00:00Z').chartRows
    ).toHaveLength(0);
  });
});
