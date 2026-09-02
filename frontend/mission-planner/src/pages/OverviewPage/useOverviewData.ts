import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchApplicablePois,
  fetchGroundEntryPoint,
  fetchHistory,
  fetchStatus,
  type ApplicablePoi,
  type GroundEntryPoint,
  type MonitoringHistory,
  type StatusData,
} from '../../services/monitoring';
import {
  appendSample,
  mergeHistory,
  summarizeWindow,
  type NumericSample,
} from './history';
import { CompletionPoller, type Cadence } from './poller';

type Metric = MonitoringHistory['series'][number]['metric'];
type Store = Record<Metric, NumericSample[]>;

const emptyStore = (): Store => ({
  latitude_degrees: [],
  longitude_degrees: [],
  latency_ms: [],
  throughput_down_mbps: [],
  throughput_up_mbps: [],
  packet_loss_percent: [],
});

export function useOverviewData() {
  const [cadence, setCadence] = useState<Cadence>(1);
  const [status, setStatus] = useState<StatusData | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<Date | null>(null);
  const [history, setHistory] = useState<Store>(emptyStore);
  const [gep, setGep] = useState<GroundEntryPoint | null>(null);
  const [pois, setPois] = useState<ApplicablePoi[]>([]);
  const [now, setNow] = useState(() => new Date());
  const controllers = useRef(new Set<AbortController>());
  const historyPending = useRef(false);
  const hiddenAt = useRef<number | null>(null);

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
    setStatusLoading(true);
    try {
      const sample = await withController(fetchStatus);
      const received = new Date();
      setStatus(sample);
      setLastSuccess(received);
      setStatusError(null);
      setHistory((current) => {
        const timestamp = sample.observed_at;
        const instant = received.getTime();
        return {
          ...current,
          latitude_degrees: appendSample(
            current.latitude_degrees,
            { timestamp, value: sample.position.latitude },
            instant
          ),
          longitude_degrees: appendSample(
            current.longitude_degrees,
            { timestamp, value: sample.position.longitude },
            instant
          ),
          latency_ms: appendSample(
            current.latency_ms,
            { timestamp, value: sample.network.latency_ms },
            instant
          ),
          throughput_down_mbps: appendSample(
            current.throughput_down_mbps,
            { timestamp, value: sample.network.throughput_down_mbps },
            instant
          ),
          throughput_up_mbps: appendSample(
            current.throughput_up_mbps,
            { timestamp, value: sample.network.throughput_up_mbps },
            instant
          ),
          packet_loss_percent: appendSample(
            current.packet_loss_percent,
            { timestamp, value: sample.network.packet_loss_percent },
            instant
          ),
        };
      });
    } catch {
      setStatusError('Live status unavailable');
    } finally {
      setStatusLoading(false);
    }
  }, [withController]);

  const reconcileHistory = useCallback(async () => {
    if (historyPending.current) return;
    historyPending.current = true;
    try {
      const backfill = await withController(fetchHistory);
      const instant = Date.parse(backfill.generated_at);
      setHistory((current) => {
        const next = { ...current };
        for (const series of backfill.series) {
          next[series.metric] = mergeHistory(
            current[series.metric],
            series.samples.flatMap((sample) =>
              sample.value === null ? [] : [{ ...sample, value: sample.value }]
            ),
            instant
          );
        }
        return next;
      });
    } catch {
      // A failed repair leaves accepted browser history untouched.
    } finally {
      historyPending.current = false;
    }
  }, [withController]);

  const requestRef = useRef(refreshStatus);
  requestRef.current = refreshStatus;
  const pollerRef = useRef<CompletionPoller | null>(null);
  if (pollerRef.current === null) {
    pollerRef.current = new CompletionPoller(() => requestRef.current(), 1);
  }

  useEffect(() => pollerRef.current?.setCadence(cadence), [cadence]);

  useEffect(() => {
    const poller = pollerRef.current;
    const ownedControllers = controllers.current;
    if (!poller) return;
    poller.setVisible(document.visibilityState === 'visible');
    poller.start();
    void poller.manual();
    void reconcileHistory();
    void withController(fetchGroundEntryPoint)
      .then(setGep)
      .catch(() => {});
    void withController(fetchApplicablePois)
      .then(setPois)
      .catch(() => {});

    const onVisibility = () => {
      const visible = document.visibilityState === 'visible';
      poller.setVisible(visible);
      if (!visible) {
        hiddenAt.current = performance.now();
      } else if (
        hiddenAt.current !== null &&
        performance.now() - hiddenAt.current > 5000
      ) {
        void reconcileHistory();
        hiddenAt.current = null;
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    let clockTimer: ReturnType<typeof setTimeout>;
    const updateClock = () => {
      setNow(new Date());
      clockTimer = setTimeout(updateClock, 1000);
    };
    clockTimer = setTimeout(updateClock, 1000);
    return () => {
      poller.stop();
      clearTimeout(clockTimer);
      document.removeEventListener('visibilitychange', onVisibility);
      for (const controller of ownedControllers) controller.abort();
      ownedControllers.clear();
    };
  }, [reconcileHistory, withController]);

  const summaries = useMemo(
    () => ({
      latency: summarizeWindow(history.latency_ms, now.getTime(), 300),
      packetLoss: summarizeWindow(
        history.packet_loss_percent,
        now.getTime(),
        1800
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
    gep,
    pois,
    now,
    summaries,
    refreshStatus: () => pollerRef.current?.manual() ?? Promise.resolve(),
    reconcileHistory,
  };
}
