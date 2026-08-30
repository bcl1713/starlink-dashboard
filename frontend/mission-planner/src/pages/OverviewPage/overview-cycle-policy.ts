import { HTTP_SLOTS, type OverviewHttpSlot } from './overview-data-reducer';
import type { UseOverviewDataOptions } from './overview-data-types';
import { safeNow } from './overview-freshness';
import {
  beginOverviewCycle,
  clearOverviewResetPending,
  isOverviewCycleResetReady,
  isOverviewLifecycleCurrent,
  type OverviewCycleReason,
  type OverviewLifecycle,
} from './overview-lifecycle';

const PERIODS = {
  telemetry: 1,
  pois: 1,
  satellites: 1,
  missionEvents: 1,
  activeLink: 1,
  route: 5,
  groundEntryPoint: 30,
  history: 10,
} as const satisfies Record<OverviewHttpSlot, number>;

export function beginOverviewCyclePlan(
  lifecycle: OverviewLifecycle,
  reason: OverviewCycleReason,
  current: Pick<UseOverviewDataOptions, 'cadence' | 'now' | 'visibility'>,
  anchors: Map<OverviewHttpSlot, number>
): {
  generation: number;
  nowMs: number | null;
  selected: readonly OverviewHttpSlot[];
} {
  const generation = beginOverviewCycle(lifecycle);
  const blocked =
    (reason === 'scheduled' || reason === 'visibility') &&
    (current.cadence === 'paused' || safeHidden(current.visibility));
  if (
    lifecycle.invalidated ||
    !isOverviewLifecycleCurrent(lifecycle, generation) ||
    blocked
  ) {
    return { generation, nowMs: null, selected: [] };
  }
  const nowMs = safeNow(current.now ?? Date.now);
  if (nowMs === null) return { generation, nowMs, selected: [] };
  if (isOverviewCycleResetReady(lifecycle, generation)) {
    resetOverviewAnchors(anchors, nowMs);
    clearOverviewResetPending(lifecycle, generation);
    if (reason !== 'manual') return { generation, nowMs, selected: [] };
  }
  return {
    generation,
    nowMs,
    selected: dueSlots(reason, current.cadence, anchors, nowMs),
  };
}

export function dueSlots(
  reason: OverviewCycleReason,
  cadence: UseOverviewDataOptions['cadence'],
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number
): OverviewHttpSlot[] {
  if (reason === 'manual' || reason === 'bootstrap') return [...HTTP_SLOTS];
  if (cadence === 'paused') return [];
  return HTTP_SLOTS.filter((slot) => {
    const previous = anchors.get(slot);
    const period = Math.max(cadence, PERIODS[slot]) * 1000;
    return previous === undefined || Math.max(0, nowMs - previous) >= period;
  });
}

export const cadenceSeconds = (cadence: UseOverviewDataOptions['cadence']) =>
  cadence === 'paused' ? 30 : cadence;

export function safeHidden(
  visibility: UseOverviewDataOptions['visibility']
): boolean {
  try {
    return visibility?.isHidden() ?? false;
  } catch {
    return false;
  }
}

export function resetOverviewAnchors(
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number
): void {
  HTTP_SLOTS.forEach((slot) => anchors.set(slot, nowMs));
}

export function resetAnchorsAt(
  anchors: Map<OverviewHttpSlot, number>,
  now: () => number
): boolean {
  const nowMs = safeNow(now);
  if (nowMs === null) return false;
  resetOverviewAnchors(anchors, nowMs);
  return true;
}
