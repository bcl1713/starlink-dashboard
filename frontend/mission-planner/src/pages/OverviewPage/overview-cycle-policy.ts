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

// The one global timer can arrive just before a history slot-relative boundary.
// Admit only this bounded scheduler jitter so a 5s history cadence does not
// silently become 10s; anchors still advance on every actual attempt.
const HISTORY_PHASE_JITTER_MS = 50;

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
    const jitter = slot === 'history' ? HISTORY_PHASE_JITTER_MS : 0;
    return (
      previous === undefined || Math.max(0, nowMs - previous) >= period - jitter
    );
  });
}

export const cadenceSeconds = (cadence: UseOverviewDataOptions['cadence']) =>
  cadence === 'paused' ? 30 : cadence;

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
