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

export function useOverviewFullscreen(
  rootRef: RefObject<HTMLElement | null>
): OverviewFullscreenState {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const pendingEntry = useRef<Promise<void> | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const owned = useRef(false);

  useEffect(() => {
    mounted.current = true;
    const onChange = () => {
      const nextOwned = document.fullscreenElement === rootRef.current;
      const wasOwned = owned.current;
      owned.current = nextOwned;
      setIsFullscreen(nextOwned);
      if (nextOwned) {
        setError(null);
        rootRef.current?.focus();
      } else if (wasOwned) {
        const target = returnFocus.current;
        if (target?.isConnected) target.focus();
      }
    };
    const onError = () => {
      // The event cannot be correlated to a particular pending request. The
      // request promise is the only authority for entry failure.
    };
    document.addEventListener('fullscreenchange', onChange);
    document.addEventListener('fullscreenerror', onError);
    return () => {
      mounted.current = false;
      owned.current = false;
      pendingEntry.current = null;
      returnFocus.current = null;
      document.removeEventListener('fullscreenchange', onChange);
      document.removeEventListener('fullscreenerror', onError);
    };
  }, [rootRef]);

  const enter = useCallback(() => {
    if (pendingEntry.current) return pendingEntry.current;
    const root = rootRef.current;
    if (!root?.requestFullscreen) {
      setError(fullscreenFallback);
      return Promise.resolve();
    }
    const active = document.activeElement;
    returnFocus.current = active instanceof HTMLElement ? active : null;
    setError(null);
    const attempt = root
      .requestFullscreen()
      .catch(() => {
        if (mounted.current && document.fullscreenElement !== root) {
          setError(fullscreenFallback);
        }
      })
      .finally(() => {
        if (pendingEntry.current === attempt) pendingEntry.current = null;
      });
    pendingEntry.current = attempt;
    return attempt;
  }, [rootRef]);

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
