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

export function finishOverviewCycle(lifecycle: OverviewLifecycle): void {
  lifecycle.activeCycles = Math.max(0, lifecycle.activeCycles - 1);
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

export function isOverviewResetReady(
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

export function isOverviewCycleResetReady(
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

export function clearOverviewResetPending(
  lifecycle: OverviewLifecycle,
  generation: number
): void {
  if (isOverviewLifecycleCurrent(lifecycle, generation))
    lifecycle.resetPending = false;
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
