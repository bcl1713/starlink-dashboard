import { describe, expect, it } from 'vitest';

import { buildPacketLossPanelData } from './metric-panel-data';
import { history, NOW, samples } from './metric-panel-test-fixtures';

describe('buildPacketLossPanelData', () => {
  it('keeps percent samples in range and converts invalid values to null gaps', () => {
    const data = buildPacketLossPanelData(
      history([
        {
          metric: 'packet_loss_percent',
          samples: samples([
            ['2026-08-29T12:27:00Z', 1],
            ['2026-08-29T12:28:00Z', 101],
            ['2026-08-29T12:29:00Z', -1],
            ['2026-08-29T12:30:00Z', 5],
          ]),
        },
      ]),
      NOW
    );

    expect(data.chartRows.map((row) => row.values)).toEqual([
      [1],
      [null],
      [null],
      [5],
    ]);
    expect(data.summary).toEqual({ current: 5, mean: 3, max: 5 });
  });
});
