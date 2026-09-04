import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

const fullscreenFallback =
  'Fullscreen was unavailable. Use the browser fullscreen control instead.';

export interface OverviewFullscreenState {
  isFullscreen: boolean;
  error: string | null;
  enter: () => Promise<void>;
  exit: () => Promise<void>;
}

interface EntryAttempt {
  promise: Promise<void>;
  settle: () => void;
}

export function useOverviewFullscreen(
  rootRef: RefObject<HTMLElement | null>
): OverviewFullscreenState {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const activeEntry = useRef<EntryAttempt | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const owned = useRef(false);

  const settleCaller = useCallback((attempt: EntryAttempt) => {
    if (activeEntry.current === attempt) attempt.settle();
  }, []);

  const consumeEntry = useCallback(
    (attempt: EntryAttempt, failed: boolean) => {
      if (activeEntry.current !== attempt) return;
      activeEntry.current = null;
      if (
        failed &&
        mounted.current &&
        document.fullscreenElement !== rootRef.current
      ) {
        setError(fullscreenFallback);
      }
      attempt.settle();
    },
    [rootRef]
  );

  useEffect(() => {
    mounted.current = true;
    const onChange = () => {
      const nextOwned = document.fullscreenElement === rootRef.current;
      const wasOwned = owned.current;
      owned.current = nextOwned;
      setIsFullscreen(nextOwned);
      if (nextOwned) {
        const attempt = activeEntry.current;
        if (attempt) consumeEntry(attempt, false);
        setError(null);
        rootRef.current?.focus();
      } else if (wasOwned) {
        const target = returnFocus.current;
        if (target?.isConnected) target.focus();
      }
    };
    const onError = () => {
      const attempt = activeEntry.current;
      if (attempt) consumeEntry(attempt, true);
    };
    document.addEventListener('fullscreenchange', onChange);
    document.addEventListener('fullscreenerror', onError);
    return () => {
      mounted.current = false;
      owned.current = false;
      const attempt = activeEntry.current;
      activeEntry.current = null;
      attempt?.settle();
      returnFocus.current = null;
      document.removeEventListener('fullscreenchange', onChange);
      document.removeEventListener('fullscreenerror', onError);
    };
  }, [consumeEntry, rootRef]);

  useEffect(() => {
    document.documentElement.classList.toggle(
      'overview-fullscreen-active',
      isFullscreen
    );
    return () => {
      document.documentElement.classList.remove('overview-fullscreen-active');
    };
  }, [isFullscreen]);

  const enter = useCallback(() => {
    if (activeEntry.current) return activeEntry.current.promise;
    const root = rootRef.current;
    if (!root?.requestFullscreen) {
      setError(fullscreenFallback);
      return Promise.resolve();
    }
    const active = document.activeElement;
    returnFocus.current = active instanceof HTMLElement ? active : null;
    setError(null);
    let settle!: () => void;
    const promise = new Promise<void>((resolve) => {
      settle = resolve;
    });
    const attempt = { promise, settle };
    activeEntry.current = attempt;
    try {
      void root.requestFullscreen().then(
        () => settleCaller(attempt),
        () => consumeEntry(attempt, true)
      );
    } catch {
      consumeEntry(attempt, true);
    }
    return promise;
  }, [consumeEntry, rootRef, settleCaller]);

  const exit = useCallback(async () => {
    if (document.fullscreenElement !== rootRef.current) return;
    try {
      await document.exitFullscreen();
    } catch {
      // fullscreenchange remains authoritative if the browser rejects exit.
    }
  }, [rootRef]);

  return { isFullscreen, error, enter, exit };
}
