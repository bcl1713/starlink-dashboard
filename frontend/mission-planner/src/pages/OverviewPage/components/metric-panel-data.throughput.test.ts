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
});
