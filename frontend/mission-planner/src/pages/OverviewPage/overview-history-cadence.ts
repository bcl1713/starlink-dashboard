/**
 * Pure contract shared by browser/CDP acceptance and source tests. Playwright
 * runs a built preview server, while Vitest deliberately excludes `tests/e2e`;
 * keeping this assertion here gives deterministic source coverage without
 * presenting a browser-runtime run as implementation evidence.
 */
export interface HistoryStartObservation {
  readonly url: string;
  readonly requestTimestamp: number;
  readonly terminalOutcome: 'finished' | 'failed' | 'pending';
  readonly status: number | null;
}

export interface HistoryCadenceContract {
  /** CDP monotonic timestamp units are seconds. */
  readonly intervalSeconds: number;
  /** Timer/service delay is permitted only after the nominal interval. */
  readonly maxLateJitterSeconds: number;
}

/**
 * Assert actual settled 200-history *start* intervals, not request counts.
 * The bound intentionally rejects early starts and delays beyond the declared
 * measurement budget; callers choose the budget for their environment.
 */
export function assertSettledSuccessfulHistoryStartDeltas(
  records: readonly HistoryStartObservation[],
  contract: HistoryCadenceContract
): void {
  if (
    !Number.isFinite(contract.intervalSeconds) ||
    contract.intervalSeconds <= 0 ||
    !Number.isFinite(contract.maxLateJitterSeconds) ||
    contract.maxLateJitterSeconds < 0
  ) {
    throw new Error('Invalid history cadence contract');
  }
  const starts = records
    .filter(
      (record) =>
        record.url === '/api/monitoring/history' &&
        record.terminalOutcome === 'finished' &&
        record.status === 200 &&
        Number.isFinite(record.requestTimestamp)
    )
    .map((record) => record.requestTimestamp)
    .sort((left, right) => left - right);
  if (starts.length < 2) {
    throw new Error('Fewer than two settled successful history starts');
  }
  for (let index = 1; index < starts.length; index += 1) {
    const delta = starts[index]! - starts[index - 1]!;
    if (delta < contract.intervalSeconds) {
      throw new Error(
        `History start delta ${delta}s is early; expected at least ${contract.intervalSeconds}s`
      );
    }
    if (delta > contract.intervalSeconds + contract.maxLateJitterSeconds) {
      throw new Error(
        `History start delta ${delta}s is late; expected at most ${contract.intervalSeconds + contract.maxLateJitterSeconds}s`
      );
    }
  }
}
