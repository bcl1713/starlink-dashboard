import { describe, expect, it } from 'vitest';

import { assertSettledSuccessfulHistoryStartDeltas } from './overview-history-cadence';

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
    ).toThrow('Fewer than two');
  });
});

function historyStart(requestTimestamp: number) {
  return {
    url: '/api/monitoring/history',
    requestTimestamp,
    terminalOutcome: 'finished' as const,
    status: 200,
  };
}
