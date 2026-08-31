import { describe, expect, it } from 'vitest';

import { buildLatencyPanelData } from './metric-panel-data';
import {
  buildLinearLatencyPanel,
  type LatencyProjectionInstrumentation,
} from './metric-panel-latency';
import { history } from './metric-panel-test-fixtures';

describe('latency exact mean performance', () => {
  it('keeps exact mean work bounded for 1801 in-window exponent bins', () => {
    const instrumentation = makeInstrumentation();
    const distinctExponentSamples = Array.from(
      { length: 1801 },
      (_, index) => ({
        timestamp: millisecondTimestamp(index),
        value: 2 ** (-1022 + index),
      })
    );
    const direct = buildLinearLatencyPanel(
      distinctExponentSamples,
      instrumentation
    );
    const adapted = buildLatencyPanelData(
      history([{ metric: 'latency_ms', samples: distinctExponentSamples }]),
      millisecondTimestamp(1800)
    );

    expect(direct.tableRows).toHaveLength(1801);
    expect(direct.chartRows).toHaveLength(1801);
    expect(direct.summary.current).toBe(2 ** 778);
    expect(direct.summary.mean).not.toBeNull();
    expect(Number.isFinite(direct.summary.mean)).toBe(true);
    expect(Object.is(direct.summary.mean, -0)).toBe(false);
    expect(adapted.summary.current).toBe(2 ** 778);
    expect(adapted.summary.mean).toBe(direct.summary.mean);
    expect(adapted.tableRows.at(-1)?.values[2]).toBe(direct.summary.mean);
    expect(instrumentation).toMatchObject({
      parsed: 1801,
      visited: 1801,
      enqueued: 1801,
      dequeued: 0,
      meanAdds: 1801,
      meanRemoves: 0,
      meanReads: 1801,
    });
    expect(instrumentation.minQueueOperations).toBeLessThanOrEqual(3602);
    expect(instrumentation.maxQueueOperations).toBeLessThanOrEqual(3602);
  });
});

function makeInstrumentation(): LatencyProjectionInstrumentation {
  return {
    parsed: 0,
    visited: 0,
    enqueued: 0,
    dequeued: 0,
    minQueueOperations: 0,
    maxQueueOperations: 0,
    meanAdds: 0,
    meanRemoves: 0,
    meanReads: 0,
  };
}

function millisecondTimestamp(index: number): string {
  const totalMilliseconds = index * 166;
  const minute = Math.floor(totalMilliseconds / 60000);
  const second = Math.floor((totalMilliseconds % 60000) / 1000);
  const millisecond = totalMilliseconds % 1000;
  return `2026-08-29T12:${String(minute).padStart(2, '0')}:${String(
    second
  ).padStart(2, '0')}.${String(millisecond).padStart(3, '0')}Z`;
}
