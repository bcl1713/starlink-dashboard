import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchApplicablePois,
  fetchGroundEntryPoint,
  fetchHistory,
  fetchStatus,
  type StatusData,
} from '../../services/monitoring';
import { mergeHistory, summarizeWindow } from './history';
import {
  appendLiveStatus,
  createOverviewHistoryStore,
  type OverviewHistoryStore,
} from './overviewHistoryStore';
import { CompletionPoller, type Cadence } from './poller';
import { useOverlayLane } from './useOverlayLane';

export function useOverviewData() {
  const [cadence, setCadence] = useState<Cadence>(1);
  const [status, setStatus] = useState<StatusData | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<Date | null>(null);
  const [history, setHistory] = useState<OverviewHistoryStore>(
    createOverviewHistoryStore
  );
  const [now, setNow] = useState(() => new Date());
  const controllers = useRef(new Set<AbortController>());
  const historyPending = useRef(false);
  const historyRepairQueued = useRef(false);
  const hidden = useRef(false);
  const offline = useRef(false);
  const gap = useRef<{ startedAt: number; handled: boolean } | null>(null);
  const lastStatusAt = useRef(performance.now());
  const mounted = useRef(false);

  const gepLane = useOverlayLane(
    fetchGroundEntryPoint,
    null,
    30,
    'Ground entry point unavailable',
    90,
    now
  );
  const poiLane = useOverlayLane(
    fetchApplicablePois,
    [],
    10,
    'Points of interest unavailable',
    30,
    now
  );

  const withController = useCallback(
    async <T>(work: (signal: AbortSignal) => Promise<T>) => {
      const controller = new AbortController();
      controllers.current.add(controller);
      try {
        return await work(controller.signal);
      } finally {
        controllers.current.delete(controller);
      }
    },
    []
  );

  const refreshStatus = useCallback(async () => {
    if (mounted.current) setStatusLoading(true);
    try {
      const sample = await withController(fetchStatus);
      if (!mounted.current) return;
      const received = new Date();
      lastStatusAt.current = performance.now();
      setStatus(sample);
      setLastSuccess(received);
      setStatusError(null);
      setHistory((current) =>
        appendLiveStatus(current, sample, received.getTime())
      );
    } catch {
      if (mounted.current) setStatusError('Live status unavailable');
    } finally {
      if (mounted.current) setStatusLoading(false);
    }
  }, [withController]);

  const reconcileHistory = useCallback(
    async (queueIfPending = false) => {
      if (historyPending.current) {
        if (queueIfPending) historyRepairQueued.current = true;
        return;
      }
      historyPending.current = true;
      try {
        do {
          historyRepairQueued.current = false;
          try {
            const backfill = await withController(fetchHistory);
            if (!mounted.current) return;
            const instant = Date.parse(backfill.generated_at);
            setHistory((current) => {
              const next = { ...current };
              for (const series of backfill.series) {
                next[series.metric] = mergeHistory(
                  current[series.metric],
                  series.samples.flatMap((sample) =>
                    sample.value === null
                      ? []
                      : [{ ...sample, value: sample.value }]
                  ),
                  instant
                );
              }
              return next;
            });
          } catch {
            // A failed repair leaves accepted browser history untouched.
          }
        } while (mounted.current && historyRepairQueued.current);
      } finally {
        historyPending.current = false;
      }
    },
    [withController]
  );

  const requestRef = useRef(refreshStatus);
  requestRef.current = refreshStatus;
  const pollerRef = useRef<CompletionPoller | null>(null);
  if (pollerRef.current === null) {
    pollerRef.current = new CompletionPoller(() => requestRef.current(), 1);
  }

  useEffect(() => pollerRef.current?.setCadence(cadence), [cadence]);

  useEffect(() => {
    mounted.current = true;
    const poller = pollerRef.current;
    const ownedControllers = controllers.current;
    if (!poller) return;
    const initiallyHidden = document.visibilityState !== 'visible';
    hidden.current = initiallyHidden;
    offline.current = navigator.onLine === false;
    if (initiallyHidden || offline.current) {
      gap.current = { startedAt: performance.now(), handled: false };
    }
    poller.setVisible(!initiallyHidden);
    poller.start();
    void poller.manual();
    void reconcileHistory();

    const beginGap = (startedAt = performance.now()) => {
      if (gap.current === null || (!hidden.current && !offline.current)) {
        gap.current = { startedAt, handled: false };
      }
    };
    const recoverGap = () => {
      const current = gap.current;
      if (
        current !== null &&
        !current.handled &&
        performance.now() - current.startedAt > 5000
      ) {
        current.handled = true;
        void reconcileHistory(true);
      } else if (!hidden.current && !offline.current && current !== null) {
        current.handled = true;
      }
    };
    const onVisibility = () => {
      const visible = document.visibilityState === 'visible';
      poller.setVisible(visible);
      if (!visible) {
        if (!hidden.current) beginGap();
        hidden.current = true;
      } else {
        hidden.current = false;
        recoverGap();
      }
    };
    const onOffline = () => {
      if (!offline.current) beginGap();
      offline.current = true;
    };
    const onOnline = () => {
      offline.current = false;
      if (gap.current === null) beginGap(lastStatusAt.current);
      recoverGap();
    };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('offline', onOffline);
    window.addEventListener('online', onOnline);
    let clockTimer: ReturnType<typeof setTimeout>;
    const updateClock = () => {
      setNow(new Date());
      clockTimer = setTimeout(updateClock, 1000);
    };
    clockTimer = setTimeout(updateClock, 1000);
    return () => {
      mounted.current = false;
      poller.stop();
      clearTimeout(clockTimer);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('offline', onOffline);
      window.removeEventListener('online', onOnline);
      for (const controller of ownedControllers) controller.abort();
      ownedControllers.clear();
    };
  }, [reconcileHistory]);

  const summaries = useMemo(
    () => ({
      latency: summarizeWindow(history.latency_ms, now.getTime(), 300),
      packetLoss: summarizeWindow(
        history.packet_loss_percent,
        now.getTime(),
        300
      ),
    }),
    [history, now]
  );

  const stale =
    status !== null &&
    now.getTime() - Date.parse(status.observed_at) >
      (cadence === 'paused' ? 30_000 : Math.max(10_000, cadence * 3000));
  const statusMessage = statusError
    ? `${statusError}; showing last good values`
    : statusLoading && !lastSuccess
      ? 'Loading live status'
      : stale
        ? 'Live status is stale'
        : lastSuccess
          ? `Updated ${lastSuccess.toLocaleTimeString()}`
          : 'No successful update';

  return {
    cadence,
    setCadence,
    status,
    statusMessage,
    history,
    gep: gepLane.data,
    gepState: gepLane.state,
    pois: poiLane.data,
    poiState: poiLane.state,
    now,
    summaries,
    refreshStatus: () => pollerRef.current?.manual() ?? Promise.resolve(),
    reconcileHistory,
    refreshGep: gepLane.refresh,
    refreshPois: poiLane.refresh,
  };
}
