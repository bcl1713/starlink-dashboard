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

  it('rejects duplicate upload even when download is canonical and unique', () => {
    const duplicateUpload = history([
      {
        metric: 'throughput_down_mbps',
        samples: samples([['2026-08-29T12:00:00Z', 10]]),
      },
      {
        metric: 'throughput_up_mbps',
        samples: samples([['2026-08-29T12:00:00Z', 1]]),
      },
      {
        metric: 'throughput_up_mbps',
        samples: samples([['2026-08-29T12:00:01Z', 2]]),
      },
    ]);

    expect(
      buildThroughputPanelData(duplicateUpload, '2026-08-29T12:00:01Z')
    ).toEqual({
      chartRows: [],
      tableRows: [],
      download: { current: null, min: null, mean: null, max: null },
      upload: { current: null, min: null, mean: null, max: null },
    });
  });

  it.each([
    [
      'latency',
      () =>
        buildLatencyPanelData(
          history([
            {
              metric: 'latency_ms',
              samples: samples([
                ['2026-08-29T12:00:00+01:00', 1],
                ['2026-08-29T11:00:01Z', 2],
              ]),
            },
          ]),
          '2026-08-29T11:00:01Z'
        ).tableRows,
    ],
    [
      'throughput',
      () =>
        buildThroughputPanelData(
          history([
            {
              metric: 'throughput_down_mbps',
              samples: samples([
                ['2026-08-29T12:00:00+01:00', 1],
                ['2026-08-29T11:00:01Z', 2],
              ]),
            },
            {
              metric: 'throughput_up_mbps',
              samples: samples([
                ['2026-08-29T12:00:00+01:00', 1],
                ['2026-08-29T11:00:01Z', 2],
              ]),
            },
          ]),
          '2026-08-29T11:00:01Z'
        ).tableRows,
    ],
    [
      'packet loss',
      () =>
        buildPacketLossPanelData(
          history([
            {
              metric: 'packet_loss_percent',
              samples: samples([
                ['2026-08-29T12:00:00+01:00', 1],
                ['2026-08-29T11:00:01Z', 2],
              ]),
            },
          ]),
          '2026-08-29T11:00:01Z'
        ).tableRows,
    ],
  ])('orders offset-equivalent samples through %s adapter', (_name, build) => {
    const rows = build();

    expect(rows.map((row) => row.timestamp)).toEqual([
      '2026-08-29T12:00:00+01:00',
      '2026-08-29T11:00:01Z',
    ]);
    expect(rows.every((row) => Number.isFinite(row.epochSeconds))).toBe(true);
  });

  it.each([
    ['0000', '0000-01-01T00:00:00-01:00'],
    ['9999', '9999-12-31T23:59:59.999999999+00:00'],
  ])('projects year %s endpoint through each adapter', (_year, timestamp) => {
    const latencyRows = buildLatencyPanelData(
      history([{ metric: 'latency_ms', samples: samples([[timestamp, 1]]) }]),
      timestamp
    ).tableRows;
    const throughputRows = buildThroughputPanelData(
      history([
        {
          metric: 'throughput_down_mbps',
          samples: samples([[timestamp, 1]]),
        },
        { metric: 'throughput_up_mbps', samples: samples([[timestamp, 1]]) },
      ]),
      timestamp
    ).tableRows;
    const packetRows = buildPacketLossPanelData(
      history([
        { metric: 'packet_loss_percent', samples: samples([[timestamp, 1]]) },
      ]),
      timestamp
    ).tableRows;

    for (const rows of [latencyRows, throughputRows, packetRows]) {
      expect(rows[0].timestamp).toBe(timestamp);
      expect(Number.isFinite(rows[0].epochSeconds)).toBe(true);
    }
  });
});
