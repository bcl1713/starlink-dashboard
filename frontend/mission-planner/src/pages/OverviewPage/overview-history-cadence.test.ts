import { describe, expect, it } from 'vitest';

import {
  assertSettledSuccessfulHistoryStartDeltas,
  historyStartsByContext,
} from './overview-history-cadence';

describe('assertSettledSuccessfulHistoryStartDeltas', () => {
  it('accepts settled successful history starts within the declared late jitter budget', () => {
    expect(() =>
      assertSettledSuccessfulHistoryStartDeltas(
        [historyStart(5.019), historyStart(10.019), historyStart(15.038)],
        { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
      )
    ).not.toThrow();
  });

  it('rejects early, over-late, and non-settled observations rather than counting requests', () => {
    expect(() =>
      assertSettledSuccessfulHistoryStartDeltas(
        [historyStart(5), historyStart(9.999)],
        { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
      )
    ).toThrow('early');
    expect(() =>
      assertSettledSuccessfulHistoryStartDeltas(
        [historyStart(5), historyStart(10.051)],
        { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
      )
    ).toThrow('late');
    expect(() =>
      assertSettledSuccessfulHistoryStartDeltas(
        [historyStart(5), { ...historyStart(10), terminalOutcome: 'pending' }],
        { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
      )
    ).toThrow('History request did not settle successfully');
    expect(() =>
      assertSettledSuccessfulHistoryStartDeltas(
        [historyStart(5), { ...historyStart(10), status: 429 }],
        { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
      )
    ).toThrow('History request did not settle successfully');
  });

  it('keeps page contexts separate and excludes each context bootstrap', () => {
    const contexts = historyStartsByContext([
      historyStart(100, 'desktop'),
      historyStart(105, 'desktop'),
      historyStart(110, 'desktop'),
      historyStart(110.981574, 'mobile'),
      historyStart(115.981574, 'mobile'),
      historyStart(120.981574, 'mobile'),
    ]);

    expect(contexts).toEqual([
      { contextId: 'desktop', bootstrap: 100, starts: [105, 110] },
      {
        contextId: 'mobile',
        bootstrap: 110.981574,
        starts: [115.981574, 120.981574],
      },
    ]);
    for (const context of contexts) {
      expect(() =>
        assertSettledSuccessfulHistoryStartDeltas(
          context.starts.map((requestTimestamp) =>
            historyStart(requestTimestamp)
          ),
          { intervalSeconds: 5, maxLateJitterSeconds: 0.05 }
        )
      ).not.toThrow();
    }
  });
});

function historyStart(requestTimestamp: number, contextId?: string) {
  return {
    ...(contextId ? { contextId } : {}),
    url: '/api/monitoring/history',
    requestTimestamp,
    terminalOutcome: 'finished' as const,
    status: 200,
  };
}
