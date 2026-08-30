import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import type { OverviewStatus } from '../../types/monitoring';
import {
  commitSlots,
  emptyOverviewSnapshot,
  projectFreshness,
  projectPaused,
  setManualResult,
  startSlots,
  type OverviewHttpSlot,
  type SlotOutcome,
  withRadarDisabled,
  withRadarEnabled,
  withRadarRetry,
} from './overview-data-reducer';
import type {
  OverviewAvailability,
  OverviewRadarReport,
  UseOverviewDataOptions,
} from './overview-data-types';
import {
  DEFAULT_SERVICES,
  buildSlotCommits,
  cadenceSeconds,
  createOverviewRequestRegistry,
  defaultVisibility,
  manualResultFromOutcomes,
} from './overview-requests';
import {
  beginOverviewCyclePlan,
  finishOverviewCycle,
  invalidateOverviewLifecycle,
  isOverviewLifecycleCurrent as isLifecycleCurrent,
  markOverviewResetPending,
  mountOverviewLifecycle,
  OverviewLifecycle,
  raceOverviewLifecycle,
  resetOverviewAnchorsWhenIdle as resetIdleAnchors,
  type OverviewCycleReason,
} from './overview-lifecycle';
import {
  REQUEST_FAILED_ERROR,
  radarOutcome,
  safeNow,
} from './overview-freshness';
import { useOverviewRefresh } from './useOverviewRefresh';

type DataSnapshot = ReturnType<typeof emptyOverviewSnapshot>;
type CycleOutcome = Readonly<{ slot: OverviewHttpSlot; outcome: SlotOutcome }>;
type RadarState = { gen: number; token: number; avail: OverviewAvailability };
const DEFAULT_VISIBILITY = defaultVisibility();
export function useOverviewData(options: UseOverviewDataOptions) {
  const {
    cadence,
    poiFilter,
    radarEnabled,
    services: providedServices,
    now = Date.now,
    visibility = DEFAULT_VISIBILITY,
  } = options;
  const [snapshot, setSnapshot] = useState(emptyOverviewSnapshot);
  const [radarRefreshToken, setRadarRefreshToken] = useState(0);
  const { registry, lifecycle } = useMemo(
    () => ({
      registry: createOverviewRequestRegistry(
        providedServices ?? DEFAULT_SERVICES
      ),
      lifecycle: new OverviewLifecycle(),
    }),
    [providedServices]
  );
  const anchors = useRef(new Map<OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const radar = useRef<RadarState>({ gen: 0, token: 0, avail: 'unknown' });
  const seen = useRef({ cadence: false, filter: false, radar: false });
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  const setCurrentSnapshot = useCallback(
    (generation: number, update: (snapshot: DataSnapshot) => DataSnapshot) => {
      setSnapshot((state) =>
        isLifecycleCurrent(lifecycle, generation) ? update(state) : state
      );
    },
    [lifecycle]
  );
  const incrementRadarToken = useCallback(() => {
    setRadarRefreshToken((value) => {
      const next = value === Number.MAX_SAFE_INTEGER ? 0 : value + 1;
      radar.current.token = next;
      radar.current.gen = next;
      return next;
    });
  }, []);
  const commitBatch = useCallback(
    (
      outcomes: readonly CycleOutcome[],
      nowMs: number,
      gen: number,
      manualResult?: DataSnapshot['manualResult']
    ) => {
      flushSync(() => {
        setCurrentSnapshot(gen, (current) => {
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
      });
    },
    [setCurrentSnapshot]
  );
  const runCycle = useCallback(
    async (reason: OverviewCycleReason) => {
      const current = latest.current;
      const anchorMap = anchors.current;
      const { generation, nowMs, selected } = beginOverviewCyclePlan(
        lifecycle,
        reason,
        current,
        anchorMap
      );
      try {
        if (nowMs === null || selected.length === 0) return;
        if (reason === 'manual') incrementRadarToken();
        if (reason === 'manual')
          setCurrentSnapshot(generation, (state) =>
            setManualResult(state, 'idle')
          );
        setCurrentSnapshot(generation, (state) =>
          startSlots(state, selected, current.cadence === 'paused')
        );
        for (const slot of selected) anchorMap.set(slot, nowMs);
        const outcomes = await Promise.all(
          selected.map(async (slot) => {
            const outcome = await raceOverviewLifecycle(
              registry.start(slot, current.poiFilter),
              lifecycle
            );
            return { slot, outcome };
          })
        );
        if (lifecycle.invalidated) return;
        const manualResult =
          reason === 'manual' ? manualResultFromOutcomes(outcomes) : undefined;
        await commitBatch(outcomes, nowMs, generation, manualResult);
      } finally {
        finishOverviewCycle(
          lifecycle,
          generation,
          anchors.current,
          latest.current.now
        );
      }
    },
    [commitBatch, incrementRadarToken, lifecycle, registry, setCurrentSnapshot]
  );
  const rc = useOverviewRefresh({ cadence, now, onRefresh: runCycle });
  useEffect(() => {
    mountOverviewLifecycle(lifecycle);
    const radarState = radar.current;
    Promise.resolve().then(() => void runCycle('bootstrap'));
    return () => {
      invalidateOverviewLifecycle(lifecycle);
      radarState.gen += 1;
      registry.abortAll();
    };
  }, [lifecycle, registry, runCycle]);
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
    const gen = lifecycle.generation;
    if (seen.current.radar) radar.current.gen += 1;
    else seen.current.radar = true;
    if (!radarEnabled) {
      setCurrentSnapshot(gen, (state) => {
        radar.current.avail = state.radar.availability;
        return withRadarDisabled(state);
      });
      return;
    }
    const nowMs = safeNow(latest.current.now);
    setCurrentSnapshot(gen, (state) => {
      const restored = withRadarEnabled(state, radar.current.avail);
      return nowMs === null
        ? restored
        : projectFreshness(
            restored,
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          );
    });
  }, [lifecycle, radarEnabled, setCurrentSnapshot]);
  const retryRadar = useCallback(() => {
    if (!lifecycle.mounted || !latest.current.radarEnabled) return;
    radar.current.gen += 1;
    incrementRadarToken();
    setSnapshot((state) =>
      withRadarRetry(state, latest.current.cadence === 'paused')
    );
  }, [incrementRadarToken, lifecycle]);
  useEffect(() => {
    if (!seen.current.cadence) {
      seen.current.cadence = true;
      return;
    }
    markOverviewResetPending(lifecycle);
    const getNow = latest.current.now;
    resetIdleAnchors(lifecycle, lifecycle.generation, anchors.current, getNow);
    const nowMs = safeNow(latest.current.now);
    const paused = cadence === 'paused';
    setSnapshot((state) =>
      paused || nowMs === null
        ? projectPaused(state, paused)
        : projectFreshness(state, nowMs, cadenceSeconds(cadence), false)
    );
  }, [cadence, lifecycle]);
  useEffect(() => {
    if (!seen.current.filter) {
      seen.current.filter = true;
      return;
    }
    const gen = lifecycle.generation;
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return;
    anchors.current.set('pois', nowMs);
    setCurrentSnapshot(gen, (state) =>
      startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    raceOverviewLifecycle(
      registry.start('pois', poiFilter, true),
      lifecycle
    ).then((outcome) => commitBatch([{ slot: 'pois', outcome }], nowMs, gen));
  }, [commitBatch, lifecycle, poiFilter, registry, setCurrentSnapshot]);
  const reportRadarResult = useCallback(
    (token: number, result: OverviewRadarReport) => {
      if (
        !Number.isSafeInteger(token) ||
        token !== radar.current.token ||
        token !== radar.current.gen ||
        !lifecycle.mounted ||
        !latest.current.radarEnabled
      ) {
        return;
      }
      const nowMs = safeNow(latest.current.now);
      if (nowMs === null) return;
      const outcome = result.ok
        ? radarOutcome(result.frameTimestamp)
        : { ok: false as const, error: REQUEST_FAILED_ERROR };
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
    [lifecycle]
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
