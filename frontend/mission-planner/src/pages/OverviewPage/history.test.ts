import { describe, expect, it } from 'vitest';
import { appendSample, mergeHistory, summarizeWindow } from './history';

describe('overview history', () => {
  it('keeps a deduplicated bounded thirty minute ring', () => {
    const now = Date.parse('2026-09-02T12:30:00Z');
    const existing = [
      { timestamp: '2026-09-02T11:59:59Z', value: 1 },
      { timestamp: '2026-09-02T12:10:00Z', value: 2 },
    ];
    const merged = mergeHistory(
      existing,
      [
        { timestamp: '2026-09-02T12:10:00Z', value: 3 },
        { timestamp: '2026-09-02T12:30:00Z', value: 4 },
      ],
      now
    );

    expect(merged).toEqual([
      { timestamp: '2026-09-02T12:10:00Z', value: 3 },
      { timestamp: '2026-09-02T12:30:00Z', value: 4 },
    ]);
    expect(appendSample(merged, merged[1], now)).toHaveLength(2);
  });

  it('computes finite five minute current min average and max', () => {
    const summary = summarizeWindow(
      [
        { timestamp: '2026-09-02T12:25:00Z', value: 10 },
        { timestamp: '2026-09-02T12:29:00Z', value: 20 },
        { timestamp: '2026-09-02T12:30:00Z', value: 30 },
      ],
      Date.parse('2026-09-02T12:30:00Z'),
      300
    );

    expect(summary).toEqual({ current: 30, min: 10, average: 20, max: 30 });
  });
});
