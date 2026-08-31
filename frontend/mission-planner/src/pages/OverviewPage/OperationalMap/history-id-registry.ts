import type { OverviewGeometryPoint } from '../geometry';
import type {
  OperationalFeature,
  VectorLayerId,
} from './operational-map-types';

export interface HistoryRun {
  readonly hemisphere: 'west' | 'east';
  readonly points: readonly OverviewGeometryPoint[];
  readonly sourcePoints: readonly OverviewGeometryPoint[];
  readonly timestamps: readonly string[];
}

interface PriorHistoryRun {
  readonly id: string;
  readonly hemisphere: 'west' | 'east';
  readonly timestamps: readonly string[];
}

export interface HistoryIdRegistry {
  readonly reconcile: (
    runs: readonly HistoryRun[]
  ) => readonly OperationalFeature[];
}

export function createHistoryIdRegistry(): HistoryIdRegistry {
  let nextId = 1;
  let previous: PriorHistoryRun[] = [];
  return {
    reconcile(runs) {
      const assignments = assignHistoryIds(runs, previous, () => nextId++);
      const features = runs.map((run, index) => ({
        id: assignments[index],
        layerId: `position-history-${run.hemisphere}` as VectorLayerId,
        kind: 'history-segment',
        label: `Position history ${run.hemisphere}`,
        geometry: {
          type: 'line',
          points: run.points,
          sourcePoints: run.sourcePoints,
        },
        details: [{ label: 'Samples', value: String(run.sourcePoints.length) }],
      })) satisfies OperationalFeature[];
      previous = runs.map((run, index) => ({
        id: features[index].id,
        hemisphere: run.hemisphere,
        timestamps: run.timestamps,
      }));
      return features;
    },
  };
}

function assignHistoryIds(
  runs: readonly HistoryRun[],
  previous: readonly PriorHistoryRun[],
  next: () => number
): string[] {
  const assigned = new Map<number, string>();
  const usedPrior = new Set<string>();
  const candidates = previous
    .flatMap((prior) =>
      runs.map((run, index) => ({
        index,
        prior,
        overlap: overlapTimestamps(prior.timestamps, run.timestamps),
        run,
      }))
    )
    .filter(
      (item) =>
        item.prior.hemisphere === item.run.hemisphere && item.overlap.length
    )
    .sort(
      (left, right) =>
        right.overlap.length - left.overlap.length ||
        left.prior.id.localeCompare(right.prior.id) ||
        left.index - right.index
    );
  for (const candidate of candidates) {
    if (assigned.has(candidate.index) || usedPrior.has(candidate.prior.id)) {
      continue;
    }
    assigned.set(candidate.index, candidate.prior.id);
    usedPrior.add(candidate.prior.id);
  }
  for (const [index, run] of runs.entries()) {
    if (assigned.has(index)) continue;
    const candidates = previous
      .map((prior) => ({
        prior,
        overlap: overlapTimestamps(prior.timestamps, run.timestamps),
      }))
      .filter(
        (item) =>
          item.prior.hemisphere === run.hemisphere &&
          item.overlap.length &&
          !usedPrior.has(item.prior.id)
      )
      .sort(
        (left, right) =>
          right.overlap.length - left.overlap.length ||
          left.prior.id.localeCompare(right.prior.id)
      );
    const id = candidates[0]?.prior.id ?? `history:${run.hemisphere}:${next()}`;
    assigned.set(index, id);
    usedPrior.add(id);
  }
  return runs.map((_, index) => assigned.get(index) ?? '');
}

function overlapTimestamps(
  previous: readonly string[],
  next: readonly string[]
): string[] {
  const nextSet = new Set(next);
  return previous.filter((stamp) => nextSet.has(stamp));
}
