import { useCallback, useEffect, useRef, useState } from 'react';
import type { OverviewRefreshCadence } from './preferences';

export type OverviewRefreshReason = 'scheduled' | 'manual';
export interface UseOverviewRefreshOptions {
  cadence: OverviewRefreshCadence;
  onRefresh(reason: OverviewRefreshReason): Promise<void>;
  now?: () => number;
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
  nextScheduledAt?: () => number | null
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
    if (
      due !== null &&
      due !== undefined &&
      Number.isFinite(due) &&
      due > current
    ) {
      // Keep the global cadence alive; the single timer wakes at whichever
      // deadline is sooner, including the history slot between global ticks.
      return Math.min(cadenceDelay, due - current);
    }
  } catch {
    // A supplemental slot must never disable the cadence timer.
  }
  return cadenceDelay;
}

export function useOverviewRefresh(
  options: UseOverviewRefreshOptions
): OverviewRefreshController {
  const { cadence, onRefresh, now = Date.now, nextScheduledAt } = options;
  const latestRef = useRef({ onRefresh, now, nextScheduledAt });
  const mountedRef = useRef(true);
  const activeRef = useRef(false);
  const queuedManualRef = useRef<{
    promise: Promise<void>;
    resolve: () => void;
    reject: (error: Error) => void;
  } | null>(null);
  const manualActiveRef = useRef<Promise<void> | null>(null);
  const [isManualRefreshPending, setManualRefreshPending] = useState(false);

  useEffect(() => {
    latestRef.current = { onRefresh, now, nextScheduledAt };
  }, [nextScheduledAt, onRefresh, now]);

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
        activeRef.current = false;
        manualActiveRef.current = null;
        rerender();
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
    const schedule = () => {
      const delay = nextDelay(
        cadence,
        latestRef.current.now,
        latestRef.current.nextScheduledAt
      );
      if (delay === null || cancelled) {
        return;
      }
      timeout = setTimeout(() => {
        timeout = null;
        if (!cancelled) {
          schedule();
        }
        if (cancelled || activeRef.current) {
          return;
        }
        activeRef.current = true;
        runRefresh('scheduled')
          .catch(() => {})
          .finally(() => {
            activeRef.current = false;
            runManualQueue();
          });
      }, delay);
    };
    schedule();
    return () => {
      cancelled = true;
      if (timeout !== null) {
        clearTimeout(timeout);
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
