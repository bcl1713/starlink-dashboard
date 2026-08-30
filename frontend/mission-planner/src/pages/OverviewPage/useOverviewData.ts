import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import type { OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import * as slots from './overview-data-reducer';
import type {
  OverviewAvailability,
  OverviewRadarReport,
  UseOverviewDataOptions,
} from './overview-data-types';
import { cadenceSeconds } from './overview-requests';
import * as flow from './overview-requests';
import { safeNow } from './overview-freshness';
import * as fresh from './overview-freshness';
type CycleReason = 'scheduled' | 'manual' | 'bootstrap' | 'visibility';
type DataSnapshot = ReturnType<typeof slots.emptyOverviewSnapshot>;
type CycleOutcome = Readonly<{
  slot: slots.OverviewHttpSlot;
  outcome: slots.SlotOutcome;
}>;
type RadarState = { gen: number; token: number; avail: OverviewAvailability };
const DEFAULT_VISIBILITY = flow.defaultVisibility();
export function useOverviewData(options: UseOverviewDataOptions) {
  const {
    cadence,
    poiFilter,
    radarEnabled,
    services: providedServices,
    now = Date.now,
    visibility = DEFAULT_VISIBILITY,
  } = options;
  const [snapshot, setSnapshot] = useState(slots.emptyOverviewSnapshot);
  const [radarRefreshToken, setRadarRefreshToken] = useState(0);
  const registry = useMemo(
    () =>
      flow.createOverviewRequestRegistry(
        providedServices ?? flow.DEFAULT_SERVICES
      ),
    [providedServices]
  );
  const lifecycle = useMemo(() => flow.createOverviewRequestLifecycle(), []);
  const anchors = useRef(new Map<slots.OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const radar = useRef<RadarState>({ gen: 0, token: 0, avail: 'unknown' });
  const seen = useRef({ cadence: false, filter: false, radar: false });
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  const isCurrent = useCallback(
    (gen: number) => lifecycle.mounted && lifecycle.gen === gen,
    [lifecycle]
  );
  const setSnapshotIfCurrent = useCallback(
    (gen: number, update: (snapshot: DataSnapshot) => DataSnapshot) => {
      setSnapshot((state) => (isCurrent(gen) ? update(state) : state));
    },
    [isCurrent]
  );
  const incrementRadarToken = useCallback(() => {
    setRadarRefreshToken((value) => {
      const next = value === Number.MAX_SAFE_INTEGER ? 0 : value + 1;
      radar.current.token = next;
      radar.current.gen = next;
      return next;
    });
  }, []);
  const finishResetIfIdle = useCallback(() => {
    if (!lifecycle.reset || lifecycle.active !== 0 || lifecycle.invalidated)
      return;
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return;
    slots.HTTP_SLOTS.forEach((slot) => anchors.current.set(slot, nowMs));
    lifecycle.reset = false;
  }, [lifecycle]);
  const commitBatch = useCallback(
    (
      outcomes: readonly CycleOutcome[],
      nowMs: number,
      gen: number,
      manualResult?: DataSnapshot['manualResult']
    ) => {
      if (!isCurrent(gen)) return;
      flushSync(() => {
        setSnapshotIfCurrent(gen, (current) => {
          const { commits, pending } = flow.buildSlotCommits(
            outcomes,
            current.history.data,
            pendingTelemetry.current,
            nowMs
          );
          pendingTelemetry.current = pending;
          return slots.commitSlots(
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
    [isCurrent, setSnapshotIfCurrent]
  );
  const runCycle = useCallback(
    async (reason: CycleReason) => {
      const gen = lifecycle.gen;
      lifecycle.active += 1;
      const current = latest.current;
      const anchorMap = anchors.current;
      try {
        if (lifecycle.invalidated || !isCurrent(gen)) return;
        if (
          (reason === 'scheduled' || reason === 'visibility') &&
          (current.cadence === 'paused' || flow.safeHidden(current.visibility))
        )
          return;
        const nowMs = safeNow(current.now);
        if (nowMs === null) return;
        if (lifecycle.reset) {
          if (lifecycle.active === 1) {
            slots.HTTP_SLOTS.forEach((slot) =>
              anchors.current.set(slot, nowMs)
            );
            lifecycle.reset = false;
          }
          if (reason !== 'manual') return;
        }
        const selected = flow.dueSlots(
          reason,
          current.cadence,
          anchorMap,
          nowMs
        );
        if (selected.length === 0) return;
        if (reason === 'manual') incrementRadarToken();
        if (reason === 'manual')
          setSnapshotIfCurrent(gen, (state) =>
            slots.setManualResult(state, 'idle')
          );
        setSnapshotIfCurrent(gen, (state) =>
          slots.startSlots(state, selected, current.cadence === 'paused')
        );
        for (const slot of selected) anchorMap.set(slot, nowMs);
        const outcomes = await Promise.all(
          selected.map(async (slot) => {
            const outcome = await flow.raceLifecycle(
              registry.start(slot, current.poiFilter),
              lifecycle
            );
            return { slot, outcome };
          })
        );
        if (lifecycle.invalidated) return;
        const manualResult =
          reason === 'manual'
            ? flow.manualResultFromOutcomes(outcomes)
            : undefined;
        await commitBatch(outcomes, nowMs, gen, manualResult);
      } finally {
        lifecycle.active -= 1;
        if (isCurrent(gen)) finishResetIfIdle();
      }
    },
    [
      commitBatch,
      finishResetIfIdle,
      incrementRadarToken,
      isCurrent,
      lifecycle,
      registry,
      setSnapshotIfCurrent,
    ]
  );
  const rc = useOverviewRefresh({ cadence, now, onRefresh: runCycle });
  useEffect(() => {
    if (lifecycle.invalidated) lifecycle.renew();
    lifecycle.mounted = true;
    const mountGen = ++lifecycle.gen;
    const radarState = radar.current;
    Promise.resolve().then(
      () => void (isCurrent(mountGen) && runCycle('bootstrap'))
    );
    return () => {
      lifecycle.mounted = false;
      lifecycle.gen += 1;
      lifecycle.invalidate();
      radarState.gen += 1;
      registry.abortAll();
    };
  }, [isCurrent, lifecycle, registry, runCycle]);
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
    const gen = lifecycle.gen;
    if (seen.current.radar) radar.current.gen += 1;
    else seen.current.radar = true;
    if (!radarEnabled) {
      setSnapshotIfCurrent(gen, (state) => {
        radar.current.avail = state.radar.availability;
        return slots.withRadarDisabled(state);
      });
      return;
    }
    const nowMs = safeNow(latest.current.now);
    setSnapshotIfCurrent(gen, (state) => {
      const restored = slots.withRadarEnabled(state, radar.current.avail);
      return nowMs === null
        ? restored
        : slots.projectFreshness(
            restored,
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          );
    });
  }, [lifecycle, radarEnabled, setSnapshotIfCurrent]);
  const retryRadar = useCallback(() => {
    if (!lifecycle.mounted || !latest.current.radarEnabled) return;
    radar.current.gen += 1;
    incrementRadarToken();
    setSnapshot((state) =>
      slots.withRadarRetry(state, latest.current.cadence === 'paused')
    );
  }, [incrementRadarToken, lifecycle]);
  useEffect(() => {
    if (!seen.current.cadence) {
      seen.current.cadence = true;
      return;
    }
    lifecycle.reset = true;
    finishResetIfIdle();
    const nowMs = safeNow(latest.current.now);
    const paused = cadence === 'paused';
    setSnapshot((state) =>
      paused || nowMs === null
        ? slots.projectPaused(state, paused)
        : slots.projectFreshness(state, nowMs, cadenceSeconds(cadence), false)
    );
  }, [cadence, finishResetIfIdle, lifecycle]);
  useEffect(() => {
    if (!seen.current.filter) {
      seen.current.filter = true;
      return;
    }
    const gen = lifecycle.gen;
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return;
    anchors.current.set('pois', nowMs);
    setSnapshotIfCurrent(gen, (state) =>
      slots.startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    flow
      .raceLifecycle(registry.start('pois', poiFilter, true), lifecycle)
      .then((outcome) => commitBatch([{ slot: 'pois', outcome }], nowMs, gen));
  }, [commitBatch, lifecycle, poiFilter, registry, setSnapshotIfCurrent]);
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
        ? fresh.radarOutcome(result.frameTimestamp)
        : { ok: false as const, error: fresh.REQUEST_FAILED_ERROR };
      setSnapshot((state) =>
        slots.commitSlots(
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
