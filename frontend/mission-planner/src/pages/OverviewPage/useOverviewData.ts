import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MonitoringHistory, OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import {
  commitSlots,
  emptyOverviewSnapshot,
  HTTP_SLOTS,
  mergeTelemetryIntoHistory,
  setManualResult,
  startSlots,
  withRadarDisabled,
  type OverviewHttpSlot,
  type SlotCommit,
  type SlotOutcome,
} from './overview-data-reducer';
import type {
  OverviewManualResult,
  OverviewSourceKey,
  UseOverviewDataOptions,
  UseOverviewDataResult,
} from './overview-data-types';
import {
  acceptTelemetry,
  appendPending,
  classifyOverviewError,
  historyContains,
  radarOutcome,
  safeNow,
} from './overview-freshness';
import {
  DEFAULT_SERVICES,
  cadenceSeconds,
  createOverviewRequestRegistry,
  defaultVisibility,
  dueSlots,
  manualResultFromOutcomes,
  projectPaused,
  safeHidden,
} from './overview-requests';

export function useOverviewData(
  options: UseOverviewDataOptions
): UseOverviewDataResult {
  const {
    cadence,
    poiFilter,
    radarEnabled,
    services = DEFAULT_SERVICES,
    now = Date.now,
    visibility = defaultVisibility(),
  } = options;
  const [snapshot, setSnapshot] = useState(emptyOverviewSnapshot);
  const registry = useMemo(
    () => createOverviewRequestRegistry(services),
    [services]
  );
  const mounted = useRef(false);
  const generation = useRef(0);
  const anchors = useRef(new Map<OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const activeCycles = useRef(0);
  const pendingReset = useRef(false);
  const sawCadence = useRef(false);
  const sawFilter = useRef(false);
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });

  useEffect(() => {
    latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  }, [cadence, now, poiFilter, radarEnabled, visibility]);

  const resetAnchors = useCallback((nowMs: number) => {
    for (const slot of HTTP_SLOTS) anchors.current.set(slot, nowMs);
  }, []);

  const finishResetIfIdle = useCallback(() => {
    if (!pendingReset.current || activeCycles.current !== 0) return false;
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return false;
    resetAnchors(nowMs);
    pendingReset.current = false;
    return true;
  }, [resetAnchors]);

  const commitBatch = useCallback(
    (
      outcomes: readonly { slot: OverviewSourceKey; outcome: SlotOutcome }[],
      nowMs: number,
      manualResult?: OverviewManualResult
    ) => {
      if (!mounted.current) return;
      setSnapshot((current) => {
        const commits: SlotCommit[] = [];
        for (const { slot, outcome } of outcomes) {
          if (slot === 'telemetry' && outcome.ok) {
            const status = outcome.data as OverviewStatus;
            if (acceptTelemetry(status, nowMs)) {
              if (current.history.data) {
                const history = mergeTelemetryIntoHistory(
                  current.history.data,
                  status,
                  nowMs
                );
                if (history)
                  commits.push(['history', { ok: true, data: history }]);
              } else {
                pendingTelemetry.current = appendPending(
                  pendingTelemetry.current,
                  status
                );
              }
            }
          }
          if (slot === 'history' && outcome.ok) {
            const history = mergeTelemetryIntoHistory(
              outcome.data as MonitoringHistory,
              pendingTelemetry.current,
              nowMs
            );
            if (history) {
              pendingTelemetry.current = pendingTelemetry.current.filter(
                (status) => !historyContains(history, status.timestamp)
              );
              commits.push(['history', { ok: true, data: history }]);
              continue;
            }
          }
          commits.push([slot, outcome]);
        }
        return commitSlots(
          current,
          commits,
          nowMs,
          cadenceSeconds(latest.current.cadence),
          latest.current.cadence === 'paused',
          manualResult
        );
      });
    },
    []
  );

  const runCycle = useCallback(
    async (reason: 'scheduled' | 'manual' | 'bootstrap' | 'visibility') => {
      activeCycles.current += 1;
      const current = latest.current;
      try {
        if (
          (reason === 'scheduled' || reason === 'visibility') &&
          (current.cadence === 'paused' || safeHidden(current.visibility))
        ) {
          return;
        }
        const nowMs = safeNow(current.now);
        if (nowMs === null) return;
        if (pendingReset.current) {
          resetAnchors(nowMs);
          pendingReset.current = false;
          if (reason !== 'manual') return;
        }
        const selected = dueSlots(
          reason,
          current.cadence,
          anchors.current,
          nowMs
        );
        if (selected.length === 0) return;
        if (reason === 'manual') {
          setSnapshot((state) => setManualResult(state, 'idle'));
        }
        setSnapshot((state) =>
          startSlots(state, selected, current.cadence === 'paused')
        );
        for (const slot of selected) anchors.current.set(slot, nowMs);
        const outcomes = await Promise.all(
          selected.map(async (slot) => {
            const outcome = await registry.start(slot, current.poiFilter);
            return { slot, outcome };
          })
        );
        if (reason === 'manual') {
          commitBatch(outcomes, nowMs, manualResultFromOutcomes(outcomes));
        } else {
          commitBatch(outcomes, nowMs);
        }
      } finally {
        activeCycles.current -= 1;
        finishResetIfIdle();
      }
    },
    [commitBatch, finishResetIfIdle, registry, resetAnchors]
  );

  const refreshController = useOverviewRefresh({
    cadence,
    now,
    onRefresh: runCycle,
  });

  useEffect(() => {
    mounted.current = true;
    const mountGeneration = ++generation.current;
    Promise.resolve().then(() => {
      if (mounted.current && generation.current === mountGeneration) {
        void runCycle('bootstrap');
      }
    });
    return () => {
      mounted.current = false;
      generation.current += 1;
      registry.abortAll();
    };
  }, [registry, runCycle]);

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = visibility.subscribe(() => void runCycle('visibility'));
    } catch {
      unsubscribe = undefined;
    }
    return () => {
      try {
        unsubscribe?.();
      } catch {
        return;
      }
    };
  }, [runCycle, visibility]);

  useEffect(() => {
    if (!radarEnabled) setSnapshot(withRadarDisabled);
  }, [radarEnabled]);

  useEffect(() => {
    if (!sawCadence.current) {
      sawCadence.current = true;
      return;
    }
    pendingReset.current = true;
    finishResetIfIdle();
    setSnapshot((state) => projectPaused(state, cadence === 'paused'));
  }, [cadence, finishResetIfIdle]);

  useEffect(() => {
    if (!sawFilter.current) {
      sawFilter.current = true;
      return;
    }
    registry.start('pois', poiFilter, true).then((outcome) => {
      const nowMs = safeNow(latest.current.now);
      if (nowMs !== null) commitBatch([{ slot: 'pois', outcome }], nowMs);
    });
    setSnapshot((state) =>
      startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
  }, [commitBatch, poiFilter, registry]);

  const reportRadarResult = useCallback(
    (
      result:
        | { readonly ok: true; readonly frameTimestamp: string }
        | { readonly ok: false; readonly error: unknown }
    ) => {
      const nowMs = safeNow(latest.current.now);
      if (nowMs === null || !latest.current.radarEnabled) return;
      const outcome = result.ok
        ? radarOutcome(result.frameTimestamp)
        : {
            ok: false as const,
            error: classifyOverviewError(result.error, false),
          };
      setSnapshot((state) =>
        commitSlots(
          state,
          [['radar', outcome]],
          nowMs,
          cadenceSeconds(latest.current.cadence),
          latest.current.cadence === 'paused'
        )
      );
    },
    []
  );

  return {
    snapshot,
    controller: {
      isManualRefreshPending: refreshController.isManualRefreshPending,
      manualRefresh: refreshController.manualRefresh,
      reportRadarResult,
    },
  };
}
