import { useCallback, useEffect, useRef, useState } from 'react';
import type { OverviewRefreshCadence } from './preferences';

export type OverviewRefreshReason = 'scheduled' | 'manual';
export interface UseOverviewRefreshOptions {
  cadence: OverviewRefreshCadence;
  onRefresh(reason: OverviewRefreshReason): Promise<void>;
  now?: () => number;
}
export interface OverviewRefreshController {
  readonly isManualRefreshPending: boolean;
  manualRefresh(): Promise<void>;
}

const UNMOUNTED_ERROR = 'Overview refresh unmounted';

function nextDelay(
  cadence: OverviewRefreshCadence,
  now: () => number
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
  return remainder === 0 ? interval : interval - remainder;
}

export function useOverviewRefresh(
  options: UseOverviewRefreshOptions
): OverviewRefreshController {
  const { cadence, onRefresh, now = Date.now } = options;
  const latestRef = useRef({ onRefresh, now });
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
    latestRef.current = { onRefresh, now };
  }, [onRefresh, now]);

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
      const delay = nextDelay(cadence, latestRef.current.now);
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
  }, [cadence, now, runManualQueue, runRefresh]);

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
