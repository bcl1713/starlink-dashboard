import type {
  OverviewDataSnapshot,
  OverviewInitialState,
  OverviewManualResult,
  OverviewSourceKey,
} from './overview-data-types';
import { SOURCE_LABELS, SOURCE_ORDER } from './overview-sources';

export function batchAnnouncement(
  snapshot: OverviewDataSnapshot,
  before: { [K in OverviewSourceKey]: OverviewDataSnapshot[K] },
  after: { [K in OverviewSourceKey]: OverviewDataSnapshot[K] },
  manualResult: OverviewManualResult
): string | null {
  const manual =
    manualResult !== snapshot.manualResult && manualResult === 'success'
      ? 'Manual refresh complete.'
      : manualResult !== snapshot.manualResult && manualResult === 'partial'
        ? 'Manual refresh completed with partial failures.'
        : manualResult !== snapshot.manualResult && manualResult === 'failure'
          ? 'Manual refresh failed.'
          : null;
  if (manual) return dedupe(snapshot.announcement, manual);

  const projected = projectInitial(after);
  const initial =
    snapshot.initialState !== 'ready' && projected === 'ready'
      ? 'Overview ready.'
      : snapshot.initialState !== 'total-error' && projected === 'total-error'
        ? 'Overview data failed to load.'
        : null;
  if (initial) return dedupe(snapshot.announcement, initial);

  for (const kind of ['error', 'stale', 'recovery'] as const) {
    for (const source of SOURCE_ORDER) {
      const previous = before[source];
      const next = after[source];
      const message =
        kind === 'error' && !previous.error && next.error
          ? `${SOURCE_LABELS[source]} refresh failed.`
          : kind === 'stale' &&
              previous.freshness !== 'stale' &&
              next.freshness === 'stale'
            ? `${SOURCE_LABELS[source]} data is stale.`
            : kind === 'recovery' &&
                (previous.error || previous.freshness === 'stale') &&
                !next.error &&
                next.freshness !== 'stale'
              ? `${SOURCE_LABELS[source]} recovered.`
              : null;
      if (message) return dedupe(snapshot.announcement, message);
    }
  }

  return snapshot.announcement;
}

function dedupe(previous: string | null, next: string): string | null {
  return previous === next ? previous : next;
}

function projectInitial(slots: {
  [K in OverviewSourceKey]: OverviewDataSnapshot[K];
}): OverviewInitialState {
  const required = [slots.telemetry, slots.history, slots.pois];
  if (required.some((slot) => slot.data === undefined && slot.error === null)) {
    return 'initial-loading';
  }
  if (required.every((slot) => slot.data === undefined && slot.error)) {
    return 'total-error';
  }
  return Object.values(slots).some((slot) => slot.error)
    ? 'partial-error'
    : 'ready';
}
