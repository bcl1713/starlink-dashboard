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
  createOverviewRequestRegistry,
  defaultVisibility,
  manualResultFromOutcomes,
} from './overview-requests';
import {
  beginOverviewCyclePlan,
  cadenceSeconds,
  resetAnchorsAt,
} from './overview-cycle-policy';
import {
  finishOverviewCyclePlan,
  invalidateOverviewLifecycle,
  isOverviewLifecycleCurrent,
  markOverviewResetPending,
  mountOverviewLifecycle,
  OverviewLifecycle,
  raceOverviewLifecycle,
  resetOverviewAnchorsWhenIdle,
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
  const [registry, lifecycle] = useMemo(
    () =>
      [
        createOverviewRequestRegistry(providedServices ?? DEFAULT_SERVICES),
        new OverviewLifecycle(),
      ] as const,
    [providedServices]
  );
  const anchors = useRef(new Map<OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const radar = useRef<RadarState>({ gen: 0, token: 0, avail: 'unknown' });
  const seen = useRef({ cadence: false, filter: false, radar: false });
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  const setCurrentSnapshot = useCallback(
    (gen: number, update: (snapshot: DataSnapshot) => DataSnapshot) =>
      setSnapshot((state) =>
        isOverviewLifecycleCurrent(lifecycle, gen) ? update(state) : state
      ),
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
    async (why: OverviewCycleReason) => {
      const anchorMap = anchors.current;
      const { generation, nowMs, selected } = beginOverviewCyclePlan(
        lifecycle,
        why,
        latest.current,
        anchorMap
      );
      const current = latest.current;
      try {
        if (nowMs === null || selected.length === 0) return;
        if (why === 'manual') incrementRadarToken();
        if (why === 'manual')
          setCurrentSnapshot(generation, (state) =>
            setManualResult(state, 'idle')
          );
        setCurrentSnapshot(generation, (state) =>
          startSlots(state, selected, current.cadence === 'paused')
        );
        for (const slot of selected) anchorMap.set(slot, nowMs);
        const outcomes = await Promise.all(
          selected.map(async (slot) => ({
            slot,
            outcome: await raceOverviewLifecycle(
              registry.start(slot, current.poiFilter),
              lifecycle
            ),
          }))
        );
        if (lifecycle.invalidated) return;
        const manualResult =
          why === 'manual' ? manualResultFromOutcomes(outcomes) : undefined;
        await commitBatch(outcomes, nowMs, generation, manualResult);
      } finally {
        finishOverviewCyclePlan(lifecycle, generation, () =>
          resetAnchorsAt(anchors.current, latest.current.now)
        );
      }
    },
    [commitBatch, incrementRadarToken, lifecycle, registry, setCurrentSnapshot]
  );
  const rc = useOverviewRefresh({ cadence, now, onRefresh: runCycle });
  useEffect(() => {
    const gen = mountOverviewLifecycle(lifecycle);
    const radarState = radar.current;
    Promise.resolve().then(() => {
      if (isOverviewLifecycleCurrent(lifecycle, gen))
        void runCycle('bootstrap');
    });
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
      void unsubscribe;
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
    resetOverviewAnchorsWhenIdle(lifecycle, lifecycle.generation, () =>
      resetAnchorsAt(anchors.current, latest.current.now)
    );
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
