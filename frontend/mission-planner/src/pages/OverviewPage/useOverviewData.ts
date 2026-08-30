import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MonitoringHistory, OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import {
  commitSlot,
  emptyOverviewSnapshot,
  mergeTelemetryIntoHistory,
  setManualResult,
  startSlots,
  withManualIdle,
  withRadarDisabled,
  type OverviewHttpSlot,
  type SlotOutcome,
} from './overview-data-reducer';
import type {
  OverviewManualResult,
  UseOverviewDataOptions,
  UseOverviewDataResult,
} from './overview-data-types';
import {
  classifyOverviewError,
  radarOutcome,
  safeNow,
} from './overview-freshness';
import {
  DEFAULT_SERVICES,
  cadenceSeconds,
  createOverviewRequestRegistry,
  defaultVisibility,
  dueSlots,
  refreshSnapshotFreshness,
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
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });

  useEffect(() => {
    latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  }, [cadence, now, poiFilter, radarEnabled, visibility]);

  const commit = useCallback(
    (slot: OverviewHttpSlot, outcome: SlotOutcome, nowMs: number) => {
      if (!mounted.current) return;
      setSnapshot((current) => {
        let next = current;
        if (slot === 'telemetry' && outcome.ok) {
          const status = outcome.data as OverviewStatus;
          next = commitSlot(
            next,
            slot,
            outcome,
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          );
          if (!next.history.data) pendingTelemetry.current.push(status);
          const history = mergeTelemetryIntoHistory(
            next.history.data,
            status,
            nowMs
          );
          return history
            ? commitSlot(
                next,
                'history',
                { ok: true, data: history },
                nowMs,
                cadenceSeconds(latest.current.cadence),
                latest.current.cadence === 'paused'
              )
            : next;
        }
        if (slot === 'history' && outcome.ok) {
          const statuses = [
            ...pendingTelemetry.current,
            ...(next.telemetry.data ? [next.telemetry.data] : []),
          ];
          pendingTelemetry.current = [];
          const history = statuses.reduce(
            (acc, status) =>
              mergeTelemetryIntoHistory(acc, status, nowMs) ?? acc,
            outcome.data as MonitoringHistory
          );
          return commitSlot(
            next,
            slot,
            { ok: true, data: history },
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          );
        }
        return commitSlot(
          next,
          slot,
          outcome,
          nowMs,
          cadenceSeconds(latest.current.cadence),
          latest.current.cadence === 'paused'
        );
      });
    },
    []
  );

  const runCycle = useCallback(
    async (reason: 'scheduled' | 'manual' | 'bootstrap' | 'visibility') => {
      const current = latest.current;
      const nowMs = safeNow(current.now);
      if (nowMs === null) return;
      if (
        (reason === 'scheduled' || reason === 'visibility') &&
        (current.cadence === 'paused' || safeHidden(current.visibility))
      ) {
        return;
      }
      const selected = dueSlots(
        reason,
        current.cadence,
        anchors.current,
        nowMs
      );
      if (selected.length === 0) return;
      if (reason === 'manual') setSnapshot(withManualIdle);
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
      let successes = 0;
      let failures = 0;
      for (const { slot, outcome } of outcomes) {
        if (outcome.ok) successes += 1;
        else if (outcome.error) failures += 1;
        if (slot === 'telemetry' && outcome.ok) {
          pendingTelemetry.current.push(outcome.data as OverviewStatus);
        }
        commit(slot, outcome, nowMs);
      }
      if (reason === 'manual') {
        const manual: OverviewManualResult =
          failures === 0 ? 'success' : successes === 0 ? 'failure' : 'partial';
        setSnapshot((state) => setManualResult(state, manual));
      }
    },
    [commit, registry]
  );

  const refreshController = useOverviewRefresh({
    cadence,
    now,
    onRefresh: runCycle,
  });

  useEffect(() => {
    mounted.current = true;
    const mountGeneration = ++generation.current;
    queueMicrotask(() => {
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
    let active = true;
    if (!radarEnabled) {
      queueMicrotask(() => {
        if (active) setSnapshot(withRadarDisabled);
      });
    }
    return () => {
      active = false;
    };
  }, [radarEnabled]);

  useEffect(() => {
    let active = true;
    if (cadence === 'paused') return;
    const nowMs = safeNow(now);
    if (nowMs === null) return;
    queueMicrotask(() => {
      if (active) {
        setSnapshot((state) => refreshSnapshotFreshness(state, nowMs, cadence));
      }
    });
    return () => {
      active = false;
    };
  }, [cadence, now]);

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
        commitSlot(
          state,
          'radar',
          outcome,
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
