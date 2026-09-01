/**
 * Pure contract shared by browser/CDP acceptance and source tests. Playwright
 * runs a built preview server, while Vitest deliberately excludes `tests/e2e`;
 * keeping this assertion here gives deterministic source coverage without
 * presenting a browser-runtime run as implementation evidence.
 */
export interface HistoryStartObservation {
  /** CDP frame/loader ownership; absent only for legacy single-page callers. */
  readonly contextId?: string;
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

export interface HistoryStartContext {
  /** Stable page navigation context (`frameId:loaderId`). */
  readonly contextId: string;
  /** The first successful history request is bootstrap, not cadence evidence. */
  readonly bootstrap: number;
  /** Settled successful 200 starts after that context's bootstrap. */
  readonly starts: readonly number[];
}

/**
 * Assert actual settled 200-history *start* intervals, not request counts.
 * The bound intentionally rejects early starts and delays beyond the declared
 * measurement budget; callers choose the budget for their environment. CDP
 * timestamps are compared directly on their monotonic clock: no Date.now()
 * conversion tolerance is added to this real late bound.
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
  const starts = settledSuccessfulHistoryStarts(records);
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

/**
 * Preserve page ownership before comparing cadence. A fresh page's bootstrap
 * never becomes an artificial interval with the previous page's final poll.
 */
export function historyStartsByContext(
  records: readonly HistoryStartObservation[]
): readonly HistoryStartContext[] {
  const grouped = new Map<string, number[]>();
  for (const record of records) {
    if (!isSettledSuccessfulHistoryStart(record)) continue;
    const contextId = record.contextId ?? 'legacy-single-page';
    const starts = grouped.get(contextId) ?? [];
    starts.push(record.requestTimestamp);
    grouped.set(contextId, starts);
  }
  return [...grouped.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([contextId, starts]) => {
      const ordered = starts.sort((left, right) => left - right);
      return {
        contextId,
        bootstrap: ordered[0]!,
        starts: ordered.slice(1),
      };
    });
}

function settledSuccessfulHistoryStarts(
  records: readonly HistoryStartObservation[]
): number[] {
  return records
    .filter(isSettledSuccessfulHistoryStart)
    .map((record) => record.requestTimestamp)
    .sort((left, right) => left - right);
}

function isSettledSuccessfulHistoryStart(
  record: HistoryStartObservation
): boolean {
  return (
    record.url === '/api/monitoring/history' &&
    record.terminalOutcome === 'finished' &&
    record.status === 200 &&
    Number.isFinite(record.requestTimestamp)
  );
}
