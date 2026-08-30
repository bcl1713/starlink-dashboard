import { HTTP_SLOTS, type OverviewHttpSlot } from './overview-data-reducer';
import type { UseOverviewDataOptions } from './overview-data-types';
import { safeNow } from './overview-freshness';
import { dueSlots, safeHidden } from './overview-requests';

export type OverviewCycleReason =
  | 'scheduled'
  | 'manual'
  | 'bootstrap'
  | 'visibility';

export class OverviewLifecycle {
  mounted = false;
  generation = 0;
  activeCycles = 0;
  resetPending = false;
  invalidated = false;
  invalidation: Promise<void> = Promise.resolve();
  private releaseInvalidation = () => {};

  constructor() {
    this.renew();
  }

  renew(): void {
    let released = false;
    this.invalidated = false;
    this.invalidation = new Promise<void>((resolve) => {
      this.releaseInvalidation = () => {
        if (released) return;
        released = true;
        resolve();
      };
    });
  }

  invalidate(): void {
    this.invalidated = true;
    this.releaseInvalidation();
  }
}

export function isOverviewLifecycleCurrent(
  lifecycle: OverviewLifecycle,
  generation: number
): boolean {
  return lifecycle.mounted && lifecycle.generation === generation;
}

export function mountOverviewLifecycle(lifecycle: OverviewLifecycle): number {
  if (lifecycle.invalidated) lifecycle.renew();
  lifecycle.mounted = true;
  lifecycle.generation += 1;
  return lifecycle.generation;
}

export function invalidateOverviewLifecycle(
  lifecycle: OverviewLifecycle
): void {
  lifecycle.mounted = false;
  lifecycle.generation += 1;
  lifecycle.invalidate();
}

export function beginOverviewCycle(lifecycle: OverviewLifecycle): number {
  lifecycle.activeCycles += 1;
  return lifecycle.generation;
}

export function beginOverviewCyclePlan(
  lifecycle: OverviewLifecycle,
  reason: OverviewCycleReason,
  current: Pick<UseOverviewDataOptions, 'cadence' | 'now' | 'visibility'>,
  anchors: Map<OverviewHttpSlot, number>
) {
  const generation = beginOverviewCycle(lifecycle);
  if (
    lifecycle.invalidated ||
    !isOverviewLifecycleCurrent(lifecycle, generation) ||
    ((reason === 'scheduled' || reason === 'visibility') &&
      (current.cadence === 'paused' || safeHidden(current.visibility)))
  ) {
    return { generation, nowMs: null, selected: [] };
  }
  const nowMs = safeNow(current.now ?? Date.now);
  if (nowMs === null) return { generation, nowMs, selected: [] };
  const didReset = applyCycleReset(
    lifecycle,
    generation,
    anchors,
    nowMs,
    reason
  );
  return {
    generation,
    nowMs,
    selected: didReset ? [] : dueSlots(reason, current.cadence, anchors, nowMs),
  };
}

export function finishOverviewCycle(
  lifecycle: OverviewLifecycle,
  generation: number,
  anchors: Map<OverviewHttpSlot, number>,
  now: () => number
): void {
  lifecycle.activeCycles = Math.max(0, lifecycle.activeCycles - 1);
  resetOverviewAnchorsWhenIdle(lifecycle, generation, anchors, now);
}

export function markOverviewResetPending(lifecycle: OverviewLifecycle): void {
  lifecycle.resetPending = true;
}

export function resetOverviewAnchorsWhenIdle(
  lifecycle: OverviewLifecycle,
  generation: number,
  anchors: Map<OverviewHttpSlot, number>,
  now: () => number
): boolean {
  if (
    !isOverviewLifecycleCurrent(lifecycle, generation) ||
    !lifecycle.resetPending ||
    lifecycle.activeCycles !== 0 ||
    lifecycle.invalidated
  ) {
    return false;
  }
  const nowMs = safeNow(now);
  if (nowMs === null) return false;
  resetOverviewAnchors(anchors, nowMs);
  lifecycle.resetPending = false;
  return true;
}

function applyCycleReset(
  lifecycle: OverviewLifecycle,
  generation: number,
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number,
  reason: OverviewCycleReason
): boolean {
  if (
    !isOverviewLifecycleCurrent(lifecycle, generation) ||
    !lifecycle.resetPending
  ) {
    return false;
  }
  if (lifecycle.activeCycles === 1) {
    resetOverviewAnchors(anchors, nowMs);
    lifecycle.resetPending = false;
  }
  return reason !== 'manual';
}

export async function raceOverviewLifecycle<T>(
  promise: Promise<T>,
  lifecycle: OverviewLifecycle
): Promise<T> {
  const obsolete = { ok: false, error: null, obsolete: true } as T;
  if (lifecycle.invalidated) {
    void promise.catch(() => undefined);
    return obsolete;
  }
  return Promise.race([
    promise,
    lifecycle.invalidation.then(() => {
      void promise.catch(() => undefined);
      return obsolete;
    }),
  ]);
}

function resetOverviewAnchors(
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number
): void {
  HTTP_SLOTS.forEach((slot) => anchors.set(slot, nowMs));
}
