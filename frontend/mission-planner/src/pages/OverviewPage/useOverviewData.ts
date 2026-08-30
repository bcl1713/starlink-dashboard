import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import type { OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import * as R from './overview-data-reducer';
import type {
  OverviewManualResult,
  OverviewRadarReport,
  OverviewSourceKey,
  UseOverviewDataOptions,
  UseOverviewDataResult as Result,
} from './overview-data-types';
import * as Q from './overview-requests';
import * as F from './overview-freshness';

type CycleReason = 'scheduled' | 'manual' | 'bootstrap' | 'visibility';
export function useOverviewData(options: UseOverviewDataOptions): Result {
  const {
    cadence,
    poiFilter,
    radarEnabled,
    services = Q.DEFAULT_SERVICES,
    now = Date.now,
    visibility = Q.defaultVisibility(),
  } = options;
  const [snapshot, setSnapshot] = useState(R.emptyOverviewSnapshot);
  const [radarRefreshToken, setRadarRefreshToken] = useState(0);
  const registry = useMemo(
    () => Q.createOverviewRequestRegistry(services),
    [services]
  );
  const mounted = useRef(false),
    generation = useRef(0);
  const anchors = useRef(new Map<R.OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const activeCycles = useRef(0),
    pendingReset = useRef(false);
  const radarGeneration = useRef(0);
  const radarToken = useRef(0);
  const radarAvailability = useRef(snapshot.radar.availability);
  const sawCadence = useRef(false),
    sawFilter = useRef(false),
    sawRadar = useRef(false);
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  useEffect(() => {
    latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  }, [cadence, now, poiFilter, radarEnabled, visibility]);

  const resetAnchors = useCallback((nowMs: number) => {
    for (const slot of R.HTTP_SLOTS) anchors.current.set(slot, nowMs);
  }, []);

  const incrementRadarToken = useCallback(() => {
    setRadarRefreshToken((value) => {
      const next = value === Number.MAX_SAFE_INTEGER ? 0 : value + 1;
      radarToken.current = next;
      radarGeneration.current = next;
      return next;
    });
  }, []);

  const finishResetIfIdle = useCallback(() => {
    if (!pendingReset.current || activeCycles.current !== 0) return false;
    const nowMs = F.safeNow(latest.current.now);
    if (nowMs === null) return false;
    resetAnchors(nowMs);
    pendingReset.current = false;
    return true;
  }, [resetAnchors]);

  const commitBatch = useCallback(
    (
      outcomes: readonly {
        slot: OverviewSourceKey;
        outcome: R.SlotOutcome;
      }[],
      nowMs: number,
      manualResult?: OverviewManualResult
    ) => {
      if (!mounted.current) return;
      flushSync(() => {
        setSnapshot((current) => {
          const { commits, pending } = Q.buildSlotCommits(
            outcomes,
            current.history.data,
            pendingTelemetry.current,
            nowMs
          );
          pendingTelemetry.current = pending;
          return R.commitSlots(
            current,
            commits,
            nowMs,
            Q.cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused',
            manualResult
          );
        });
      });
    },
    []
  );

  const runCycle = useCallback(
    async (reason: CycleReason) => {
      activeCycles.current += 1;
      const current = latest.current;
      try {
        if (
          (reason === 'scheduled' || reason === 'visibility') &&
          (current.cadence === 'paused' || Q.safeHidden(current.visibility))
        )
          return;
        const nowMs = F.safeNow(current.now);
        if (nowMs === null) return;
        if (pendingReset.current) {
          if (activeCycles.current === 1) resetAnchors(nowMs);
          if (activeCycles.current === 1) pendingReset.current = false;
          if (reason !== 'manual') return;
        }
        const selected = Q.dueSlots(
          reason,
          current.cadence,
          anchors.current,
          nowMs
        );
        if (selected.length === 0) return;
        if (reason === 'manual') incrementRadarToken();
        if (reason === 'manual')
          setSnapshot((state) => R.setManualResult(state, 'idle'));
        setSnapshot((state) =>
          R.startSlots(state, selected, current.cadence === 'paused')
        );
        for (const slot of selected) anchors.current.set(slot, nowMs);
        const outcomes = await Promise.all(
          selected.map(async (slot) => {
            const outcome = await registry.start(slot, current.poiFilter);
            return { slot, outcome };
          })
        );
        await commitBatch(
          outcomes,
          nowMs,
          reason === 'manual' ? Q.manualResultFromOutcomes(outcomes) : undefined
        );
      } finally {
        activeCycles.current -= 1;
        finishResetIfIdle();
      }
    },
    [
      commitBatch,
      finishResetIfIdle,
      incrementRadarToken,
      registry,
      resetAnchors,
    ]
  );

  const rc = useOverviewRefresh({ cadence, now, onRefresh: runCycle });

  useEffect(() => {
    mounted.current = true;
    const mountGeneration = ++generation.current;
    Promise.resolve().then(() => {
      if (mounted.current && generation.current === mountGeneration)
        void runCycle('bootstrap');
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
        void unsubscribe;
      }
    };
  }, [runCycle, visibility]);

  useEffect(() => {
    if (sawRadar.current) radarGeneration.current += 1;
    else sawRadar.current = true;
    if (!radarEnabled) {
      setSnapshot((state) => {
        radarAvailability.current = state.radar.availability;
        return R.withRadarDisabled(state);
      });
    } else {
      const nowMs = F.safeNow(latest.current.now);
      setSnapshot((state) => {
        const restored = R.withRadarEnabled(state, radarAvailability.current);
        return nowMs === null
          ? restored
          : R.projectFreshness(
              restored,
              nowMs,
              Q.cadenceSeconds(latest.current.cadence),
              latest.current.cadence === 'paused'
            );
      });
    }
  }, [radarEnabled]);

  const retryRadar = useCallback(() => {
    if (!latest.current.radarEnabled) return;
    radarGeneration.current += 1;
    incrementRadarToken();
    setSnapshot((state) =>
      R.withRadarRetry(state, latest.current.cadence === 'paused')
    );
  }, [incrementRadarToken]);

  useEffect(() => {
    if (!sawCadence.current) {
      sawCadence.current = true;
      return;
    }
    pendingReset.current = true;
    finishResetIfIdle();
    const nowMs = F.safeNow(latest.current.now);
    setSnapshot((state) =>
      cadence === 'paused' || nowMs === null
        ? R.projectPaused(state, cadence === 'paused')
        : R.projectFreshness(state, nowMs, Q.cadenceSeconds(cadence), false)
    );
  }, [cadence, finishResetIfIdle]);

  useEffect(() => {
    if (!sawFilter.current) {
      sawFilter.current = true;
      return;
    }
    const nowMs = F.safeNow(latest.current.now);
    if (nowMs === null) return;
    anchors.current.set('pois', nowMs);
    setSnapshot((state) =>
      R.startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    registry
      .start('pois', poiFilter, true)
      .then((outcome) => commitBatch([{ slot: 'pois', outcome }], nowMs));
  }, [commitBatch, poiFilter, registry]);

  const reportRadarResult = useCallback(
    (token: number, result: OverviewRadarReport) => {
      if (
        !Number.isSafeInteger(token) ||
        token !== radarToken.current ||
        token !== radarGeneration.current ||
        !latest.current.radarEnabled
      ) {
        return;
      }
      const nowMs = F.safeNow(latest.current.now);
      if (nowMs === null) return;
      const outcome: R.SlotOutcome = result.ok
        ? F.radarOutcome(result.frameTimestamp)
        : {
            ok: false as const,
            error: {
              code: 'request-failed',
              message: 'Source refresh failed.',
            },
          };
      setSnapshot((state) =>
        R.commitSlots(
          state,
          [['radar', outcome]],
          nowMs,
          Q.cadenceSeconds(latest.current.cadence),
          latest.current.cadence === 'paused'
        )
      );
    },
    []
  );

  return {
    snapshot,
    controller: {
      isManualRefreshPending: rc.isManualRefreshPending,
      manualRefresh: rc.manualRefresh,
      radarRefreshToken,
      retryRadar,
      reportRadarResult,
    },
  };
}
