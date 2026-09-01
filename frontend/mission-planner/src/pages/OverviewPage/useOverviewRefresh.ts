import { useCallback, useEffect, useRef, useState } from 'react';
import type { OverviewRefreshCadence } from './preferences';

export type OverviewRefreshReason = 'scheduled' | 'manual';
export interface UseOverviewRefreshOptions {
  cadence: OverviewRefreshCadence;
  onRefresh(reason: OverviewRefreshReason): Promise<void>;
  now?: () => number;
  /** Monotonic clock paired with `nextScheduledAt`, never UI freshness. */
  scheduledNow?: () => number;
  /** Absolute slot-relative deadline; must be finite and later than now. */
  nextScheduledAt?: () => number | null;
}
export interface OverviewRefreshController {
  readonly isManualRefreshPending: boolean;
  manualRefresh(): Promise<void>;
}

const UNMOUNTED_ERROR = 'Overview refresh unmounted';

function nextDelay(
  cadence: OverviewRefreshCadence,
  now: () => number,
  nextScheduledAt?: () => number | null,
  scheduledNow: () => number = now
): number | null {
  if (cadence === 'paused') {
    return null;
  }
  const interval = cadence * 1000;
  let current: number;
  try {
    current = now();
  } catch {
    return null;
  }
  if (!Number.isFinite(current)) {
    return null;
  }
  const remainder = ((current % interval) + interval) % interval;
  const cadenceDelay = remainder === 0 ? interval : interval - remainder;
  try {
    const due = nextScheduledAt?.();
    const scheduledCurrent = scheduledNow();
    if (
      due !== null &&
      due !== undefined &&
      Number.isFinite(due) &&
      Number.isFinite(scheduledCurrent)
    ) {
      // An idle overdue slot returns to the global cadence. A coalesced active
      // tick is dispatched directly at settlement, not replayed by this timer.
      if (due <= scheduledCurrent) return cadenceDelay;
      // Keep the global cadence alive; the single timer wakes at whichever
      // deadline is sooner, including the history slot between global ticks.
      return Math.min(cadenceDelay, due - scheduledCurrent);
    }
  } catch {
    // A supplemental slot must never disable the cadence timer.
  }
  return cadenceDelay;
}

export function useOverviewRefresh(
  options: UseOverviewRefreshOptions
): OverviewRefreshController {
  const {
    cadence,
    onRefresh,
    now = Date.now,
    nextScheduledAt,
    scheduledNow = now,
  } = options;
  const latestRef = useRef({ onRefresh, now, nextScheduledAt, scheduledNow });
  const mountedRef = useRef(true);
  const activeRef = useRef(false);
  const pendingScheduledRef = useRef(false);
  const settleActiveRef = useRef<() => void>(() => {});
  const queuedManualRef = useRef<{
    promise: Promise<void>;
    resolve: () => void;
    reject: (error: Error) => void;
  } | null>(null);
  const manualActiveRef = useRef<Promise<void> | null>(null);
  const [isManualRefreshPending, setManualRefreshPending] = useState(false);

  useEffect(() => {
    latestRef.current = { onRefresh, now, nextScheduledAt, scheduledNow };
  }, [nextScheduledAt, onRefresh, now, scheduledNow]);

  const runRefresh = useCallback((reason: OverviewRefreshReason) => {
    return Promise.resolve().then(() => latestRef.current.onRefresh(reason));
  }, []);

  const rerender = useCallback(() => {
    if (mountedRef.current) {
      setManualRefreshPending(
        queuedManualRef.current !== null || manualActiveRef.current !== null
      );
    }
  }, []);

  const runManualQueue = useCallback(() => {
    const queued = queuedManualRef.current;
    if (!queued || !mountedRef.current) {
      return;
    }
    queuedManualRef.current = null;
    activeRef.current = true;
    manualActiveRef.current = queued.promise;
    rerender();
    runRefresh('manual')
      .then(queued.resolve, queued.reject)
      .finally(() => {
        manualActiveRef.current = null;
        rerender();
        settleActiveRef.current();
      })
      .catch(() => {});
  }, [rerender, runRefresh]);

  const manualRefresh = useCallback((): Promise<void> => {
    if (!mountedRef.current) {
      return Promise.reject(new Error(UNMOUNTED_ERROR));
    }
    if (manualActiveRef.current) {
      return manualActiveRef.current;
    }
    if (queuedManualRef.current) {
      return queuedManualRef.current.promise;
    }
    let resolve!: () => void;
    let reject!: (error: Error) => void;
    const promise = new Promise<void>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    queuedManualRef.current = { promise, resolve, reject };
    rerender();
    if (!activeRef.current) {
      runManualQueue();
    }
    return promise;
  }, [rerender, runManualQueue]);

  useEffect(() => {
    mountedRef.current = true;
    let timeout: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    const clearTimer = () => {
      if (timeout !== null) {
        clearTimeout(timeout);
        timeout = null;
      }
    };
    const schedule = (skipOverdueHistory = false) => {
      clearTimer();
      const delay = nextDelay(
        cadence,
        latestRef.current.now,
        skipOverdueHistory ? undefined : latestRef.current.nextScheduledAt,
        latestRef.current.scheduledNow
      );
      if (delay === null || cancelled) {
        return;
      }
      timeout = setTimeout(() => {
        timeout = null;
        if (cancelled) return;
        if (activeRef.current) {
          // Additional ticks collapse into one intent. Keep one ordinary timer
          // armed while the cycle is busy without spinning on an overdue slot.
          pendingScheduledRef.current = true;
          schedule(true);
          return;
        }
        runScheduled();
      }, delay);
    };
    const runScheduled = () => {
      if (cancelled || !mountedRef.current || activeRef.current) return;
      activeRef.current = true;
      // Keep the ordinary cadence armed during the whole cycle. A passed
      // history deadline is coalesced by that active timer.
      schedule(true);
      runRefresh('scheduled')
        .catch(() => {})
        .finally(() => settleActiveRef.current());
    };
    const settleActive = () => {
      activeRef.current = false;
      if (cancelled || !mountedRef.current) return;
      if (pendingScheduledRef.current) {
        pendingScheduledRef.current = false;
        clearTimer();
        runScheduled();
        return;
      }
      if (queuedManualRef.current) {
        runManualQueue();
        return;
      }
      schedule();
    };
    settleActiveRef.current = settleActive;
    schedule();
    return () => {
      cancelled = true;
      clearTimer();
      if (settleActiveRef.current === settleActive) {
        settleActiveRef.current = () => {};
      }
    };
  }, [cadence, nextScheduledAt, now, runManualQueue, runRefresh]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      const queued = queuedManualRef.current;
      if (queued) {
        queuedManualRef.current = null;
        queued.reject(new Error(UNMOUNTED_ERROR));
      }
    };
  }, []);

  return {
    isManualRefreshPending,
    manualRefresh,
  };
}
