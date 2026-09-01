import type { UseOverviewDataOptions } from './overview-data-types';
import { safeNow } from './overview-freshness';
import {
  beginOverviewCycle,
  finishOverviewCycle,
  isOverviewLifecycleCurrent,
  type OverviewLifecycle,
} from './overview-lifecycle';
import { HTTP_SLOTS, type OverviewHttpSlot } from './overview-sources';
import { safeHidden } from './overview-visibility';

export type OverviewCycleReason =
  | 'scheduled'
  | 'manual'
  | 'bootstrap'
  | 'visibility';

const PERIODS = {
  telemetry: 1,
  pois: 1,
  satellites: 1,
  missionEvents: 1,
  activeLink: 1,
  route: 5,
  groundEntryPoint: 30,
  history: 5,
} as const satisfies Record<OverviewHttpSlot, number>;

export function beginOverviewCyclePlan(
  lifecycle: OverviewLifecycle,
  reason: OverviewCycleReason,
  current: Pick<UseOverviewDataOptions, 'cadence' | 'now' | 'visibility'>,
  anchors: Map<OverviewHttpSlot, number>,
  historyScheduleNow: number | null = nowMsOrNull(current.now ?? Date.now)
): {
  generation: number;
  nowMs: number | null;
  selected: readonly OverviewHttpSlot[];
  historyAnchorResetTo: number | null;
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
    return {
      generation,
      nowMs: null,
      selected: [],
      historyAnchorResetTo: null,
    };
  }
  const nowMs = safeNow(current.now ?? Date.now);
  if (nowMs === null) {
    return { generation, nowMs, selected: [], historyAnchorResetTo: null };
  }
  let historyAnchorResetTo: number | null = null;
  if (isOverviewCycleResetReady(lifecycle, generation)) {
    resetOverviewAnchors(anchors, nowMs, historyScheduleNow);
    historyAnchorResetTo = historyScheduleNow;
    clearOverviewResetPending(lifecycle, generation);
    if (reason !== 'manual') {
      return { generation, nowMs, selected: [], historyAnchorResetTo };
    }
  }
  return {
    generation,
    nowMs,
    selected: dueSlots(
      reason,
      current.cadence,
      anchors,
      nowMs,
      historyScheduleNow
    ),
    historyAnchorResetTo,
  };
}

export function nextHistoryDueAt(
  cadence: UseOverviewDataOptions['cadence'],
  anchors: ReadonlyMap<OverviewHttpSlot, number>
): number | null {
  if (cadence === 'paused') return null;
  const anchor = anchors.get('history');
  if (anchor === undefined) return null;
  return anchor + Math.max(cadence, PERIODS.history) * 1000;
}

export function dueSlots(
  reason: OverviewCycleReason,
  cadence: UseOverviewDataOptions['cadence'],
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number,
  historyScheduleNow: number | null = nowMs
): OverviewHttpSlot[] {
  if (cadence === 'paused' && reason !== 'manual' && reason !== 'bootstrap') {
    return [];
  }
  const cadenceSeconds = cadence === 'paused' ? 0 : cadence;
  return HTTP_SLOTS.filter((slot) => {
    const previous = anchors.get(slot);
    if (slot === 'history') {
      // Once history has a monotonic anchor, no reason may bypass that
      // deadline. A failed clock is deliberately not treated as due.
      if (previous === undefined) return true;
      if (historyScheduleNow === null) return false;
      const period = Math.max(cadenceSeconds, PERIODS.history) * 1000;
      return Math.max(0, historyScheduleNow - previous) >= period;
    }
    if (reason === 'manual' || reason === 'bootstrap') return true;
    const period = Math.max(cadenceSeconds, PERIODS[slot]) * 1000;
    return previous === undefined || Math.max(0, nowMs - previous) >= period;
  });
}

function nowMsOrNull(now: () => number): number | null {
  try {
    const value = now();
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

export const cadenceSeconds = (cadence: UseOverviewDataOptions['cadence']) =>
  cadence === 'paused' ? 30 : cadence;

export function resetOverviewAnchors(
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number,
  historyScheduleNow: number | null = null
): void {
  HTTP_SLOTS.filter((slot) => slot !== 'history').forEach((slot) =>
    anchors.set(slot, nowMs)
  );
  if (historyScheduleNow !== null) anchors.set('history', historyScheduleNow);
}

export function resetAnchorsAt(
  anchors: Map<OverviewHttpSlot, number>,
  now: () => number,
  historyScheduleNow: () => number
): boolean {
  const nowMs = safeNow(now);
  if (nowMs === null) return false;
  resetOverviewAnchors(anchors, nowMs, nowMsOrNull(historyScheduleNow));
  return true;
}

export function markOverviewResetPending(lifecycle: OverviewLifecycle): void {
  lifecycle.resetPending = true;
}

export function resetOverviewAnchorsWhenIdle(
  lifecycle: OverviewLifecycle,
  generation: number,
  reset: () => boolean
): void {
  if (!isOverviewResetReady(lifecycle, generation)) return;
  if (!reset()) return;
  clearOverviewResetPending(lifecycle, generation);
}

export function finishOverviewCyclePlan(
  lifecycle: OverviewLifecycle,
  generation: number,
  reset: () => boolean
): void {
  finishOverviewCycle(lifecycle);
  resetOverviewAnchorsWhenIdle(lifecycle, generation, reset);
}

function isOverviewResetReady(
  lifecycle: OverviewLifecycle,
  generation: number
): boolean {
  return (
    isOverviewLifecycleCurrent(lifecycle, generation) &&
    lifecycle.resetPending &&
    lifecycle.activeCycles === 0 &&
    !lifecycle.invalidated
  );
}

function isOverviewCycleResetReady(
  lifecycle: OverviewLifecycle,
  generation: number
): boolean {
  return (
    isOverviewLifecycleCurrent(lifecycle, generation) &&
    lifecycle.resetPending &&
    lifecycle.activeCycles === 1 &&
    !lifecycle.invalidated
  );
}

function clearOverviewResetPending(
  lifecycle: OverviewLifecycle,
  generation: number
): void {
  if (isOverviewLifecycleCurrent(lifecycle, generation)) {
    lifecycle.resetPending = false;
  }
}
