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
