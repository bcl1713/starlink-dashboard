import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import {
  commitSlots,
  emptyOverviewSnapshot,
  HTTP_SLOTS,
  projectFreshness,
  projectPaused,
  setManualResult,
  startSlots,
  withRadarDisabled,
  type OverviewHttpSlot,
  type SlotOutcome,
} from './overview-data-reducer';
import type {
  OverviewManualResult,
  OverviewSourceKey,
  UseOverviewDataOptions,
  UseOverviewDataResult,
} from './overview-data-types';
import {
  buildSlotCommits,
  DEFAULT_SERVICES,
  cadenceSeconds,
  createOverviewRequestRegistry,
  defaultVisibility,
  dueSlots,
  manualResultFromOutcomes,
  safeHidden,
} from './overview-requests';
import {
  classifyOverviewError,
  radarOutcome,
  safeNow,
} from './overview-freshness';

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
  const radarGeneration = useRef(0);
  const radarAvailability = useRef(snapshot.radar.availability);
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
        const { commits, pending } = buildSlotCommits(
          outcomes,
          current.history.data,
          pendingTelemetry.current,
          nowMs
        );
        pendingTelemetry.current = pending;
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
          if (activeCycles.current === 1) {
            resetAnchors(nowMs);
            pendingReset.current = false;
          }
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
    radarGeneration.current += 1;
    if (!radarEnabled) {
      setSnapshot((state) => {
        radarAvailability.current = state.radar.availability;
        return withRadarDisabled(state);
      });
    } else {
      const nowMs = safeNow(latest.current.now);
      if (nowMs !== null) {
        setSnapshot((state) =>
          projectFreshness(
            {
              ...state,
              radar: {
                ...state.radar,
                availability: radarAvailability.current,
              },
            },
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          )
        );
      }
    }
  }, [radarEnabled]);

  useEffect(() => {
    if (!sawCadence.current) {
      sawCadence.current = true;
      return;
    }
    pendingReset.current = true;
    finishResetIfIdle();
    const nowMs = safeNow(latest.current.now);
    setSnapshot((state) =>
      cadence === 'paused' || nowMs === null
        ? projectPaused(state, cadence === 'paused')
        : projectFreshness(state, nowMs, cadenceSeconds(cadence), false)
    );
  }, [cadence, finishResetIfIdle]);

  useEffect(() => {
    if (!sawFilter.current) {
      sawFilter.current = true;
      return;
    }
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return;
    anchors.current.set('pois', nowMs);
    setSnapshot((state) =>
      startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    registry
      .start('pois', poiFilter, true)
      .then((outcome) => commitBatch([{ slot: 'pois', outcome }], nowMs));
  }, [commitBatch, poiFilter, registry]);

  const reportRadarResult = useCallback(
    (
      result:
        | { readonly ok: true; readonly frameTimestamp: string }
        | { readonly ok: false; readonly error: unknown }
    ) => {
      const nowMs = safeNow(latest.current.now);
      const reportGeneration = radarGeneration.current;
      if (nowMs === null || !latest.current.radarEnabled) return;
      const outcome = result.ok
        ? radarOutcome(result.frameTimestamp)
        : {
            ok: false as const,
            error: classifyOverviewError(result.error, false),
          };
      setSnapshot((state) =>
        reportGeneration === radarGeneration.current
          ? commitSlots(
              state,
              [['radar', outcome]],
              nowMs,
              cadenceSeconds(latest.current.cadence),
              latest.current.cadence === 'paused'
            )
          : state
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
