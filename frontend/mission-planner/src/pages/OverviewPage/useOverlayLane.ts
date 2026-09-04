import { useCallback, useEffect, useRef, useState } from 'react';
import { CompletionPoller, type Cadence } from './poller';

export interface SourceState {
  loading: boolean;
  stale: boolean;
  error: string | null;
  lastSuccess: Date | null;
  recovering: boolean;
  recoveredAt: Date | null;
}

interface OverlayLane<T> {
  data: T;
  state: SourceState;
  refresh: () => Promise<void>;
}

export function useOverlayLane<T>(
  load: (signal?: AbortSignal) => Promise<T>,
  initial: T,
  cadenceSeconds: Exclude<Cadence, 'paused'>,
  errorMessage: string,
  staleAfterSeconds: number,
  now: Date
): OverlayLane<T> {
  const [data, setData] = useState(initial);
  const [state, setState] = useState<SourceState>({
    loading: true,
    stale: false,
    error: null,
    lastSuccess: null,
    recovering: false,
    recoveredAt: null,
  });
  const controller = useRef<AbortController | null>(null);
  const mounted = useRef(false);

  const request = useCallback(async () => {
    const nextController = new AbortController();
    controller.current = nextController;
    setState((current) => ({
      ...current,
      loading: true,
      recovering: current.error !== null && current.lastSuccess !== null,
    }));
    try {
      const next = await load(nextController.signal);
      if (!mounted.current) return;
      const succeededAt = new Date();
      setData(next);
      setState((current) => ({
        loading: false,
        stale: false,
        error: null,
        lastSuccess: succeededAt,
        recovering: false,
        recoveredAt: current.error ? succeededAt : current.recoveredAt,
      }));
    } catch {
      if (!mounted.current || nextController.signal.aborted) return;
      setState((current) => ({
        ...current,
        loading: false,
        error: errorMessage,
        recovering: false,
      }));
    } finally {
      if (controller.current === nextController) controller.current = null;
    }
  }, [errorMessage, load]);

  const requestRef = useRef(request);
  requestRef.current = request;
  const poller = useRef<CompletionPoller | null>(null);
  if (poller.current === null) {
    poller.current = new CompletionPoller(
      () => requestRef.current(),
      cadenceSeconds
    );
  }

  useEffect(() => {
    mounted.current = true;
    const owner = poller.current;
    owner?.start();
    void owner?.manual();
    return () => {
      mounted.current = false;
      owner?.stop();
      controller.current?.abort();
    };
  }, []);

  const stale =
    state.lastSuccess !== null &&
    now.getTime() - state.lastSuccess.getTime() > staleAfterSeconds * 1000;

  return {
    data,
    state: stale === state.stale ? state : { ...state, stale },
    refresh: () => poller.current?.manual() ?? Promise.resolve(),
  };
}
