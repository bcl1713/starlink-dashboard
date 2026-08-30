import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import type { OverviewStatus } from '../../types/monitoring';
import { useOverviewRefresh } from './useOverviewRefresh';
import * as State from './overview-data-reducer';
import type { OverviewHttpSlot, SlotOutcome } from './overview-data-reducer';
import type * as Types from './overview-data-types';
import * as Req from './overview-requests';
import * as Fresh from './overview-freshness';
type CycleReason = 'scheduled' | 'manual' | 'bootstrap' | 'visibility';
type DataSnapshot = ReturnType<typeof State.emptyOverviewSnapshot>;
type CycleOutcome = Readonly<{ slot: OverviewHttpSlot; outcome: SlotOutcome }>;
const DEFAULT_VISIBILITY = Req.defaultVisibility();
export function useOverviewData(options: Types.UseOverviewDataOptions) {
  const {
    cadence,
    poiFilter,
    radarEnabled,
    services = Req.DEFAULT_SERVICES,
    now = Date.now,
    visibility = DEFAULT_VISIBILITY,
  } = options;
  const [snapshot, setSnapshot] = useState(State.emptyOverviewSnapshot);
  const [radarRefreshToken, setRadarRefreshToken] = useState(0);
  const registry = useMemo(() => Req.createRegistry(services), [services]);
  const life = useRef({ mounted: false, gen: 0, active: 0, reset: false });
  const anchors = useRef(new Map<OverviewHttpSlot, number>());
  const pendingTelemetry = useRef<OverviewStatus[]>([]);
  const radar = useRef({
    gen: 0,
    token: 0,
    avail: snapshot.radar.availability,
  });
  const seen = useRef({ cadence: false, filter: false, radar: false });
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  useEffect(() => {
    latest.current = { cadence, poiFilter, radarEnabled, now, visibility };
  }, [cadence, now, poiFilter, radarEnabled, visibility]);
  const resetAnchors = useCallback((nowMs: number) => {
    for (const slot of State.HTTP_SLOTS) anchors.current.set(slot, nowMs);
  }, []);
  const isCurrent = useCallback(
    (gen: number) => life.current.mounted && life.current.gen === gen,
    []
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
    if (!life.current.reset || life.current.active !== 0) return false;
    const nowMs = Fresh.safeNow(latest.current.now);
    if (nowMs === null) return false;
    resetAnchors(nowMs);
    life.current.reset = false;
    return true;
  }, [resetAnchors]);
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
          const { commits, pending } = Req.slotCommits(
            outcomes,
            current.history.data,
            pendingTelemetry.current,
            nowMs
          );
          pendingTelemetry.current = pending;
          return State.commitSlots(
            current,
            commits,
            nowMs,
            Req.seconds(latest.current.cadence),
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
      const gen = life.current.gen;
      life.current.active += 1;
      const current = latest.current;
      try {
        if (!isCurrent(gen)) return;
        if (
          (reason === 'scheduled' || reason === 'visibility') &&
          (current.cadence === 'paused' || Req.safeHidden(current.visibility))
        )
          return;
        const nowMs = Fresh.safeNow(current.now);
        if (nowMs === null) return;
        if (life.current.reset) {
          if (life.current.active === 1) resetAnchors(nowMs);
          if (life.current.active === 1) life.current.reset = false;
          if (reason !== 'manual') return;
        }
        const selected = Req.dueSlots(
          reason,
          current.cadence,
          anchors.current,
          nowMs
        );
        if (selected.length === 0) return;
        if (reason === 'manual') incrementRadarToken();
        if (reason === 'manual')
          setSnapshotIfCurrent(gen, (state) =>
            State.setManualResult(state, 'idle')
          );
        setSnapshotIfCurrent(gen, (state) =>
          State.startSlots(state, selected, current.cadence === 'paused')
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
          gen,
          reason === 'manual' ? Req.resultFromOutcomes(outcomes) : undefined
        );
      } finally {
        life.current.active -= 1;
        if (isCurrent(gen)) finishResetIfIdle();
      }
    },
    [
      commitBatch,
      finishResetIfIdle,
      incrementRadarToken,
      isCurrent,
      registry,
      resetAnchors,
      setSnapshotIfCurrent,
    ]
  );
  const rc = useOverviewRefresh({ cadence, now, onRefresh: runCycle });
  useEffect(() => {
    life.current.mounted = true;
    const mountGen = ++life.current.gen;
    const lifeRef = life.current;
    const radarRef = radar.current;
    Promise.resolve().then(() => {
      if (life.current.mounted && life.current.gen === mountGen)
        void runCycle('bootstrap');
    });
    return () => {
      lifeRef.mounted = false;
      lifeRef.gen += 1;
      radarRef.gen += 1;
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
    const gen = life.current.gen;
    if (seen.current.radar) radar.current.gen += 1;
    else seen.current.radar = true;
    if (!radarEnabled) {
      setSnapshotIfCurrent(gen, (state) => {
        radar.current.avail = state.radar.availability;
        return State.withRadarDisabled(state);
      });
    } else {
      const nowMs = Fresh.safeNow(latest.current.now);
      setSnapshotIfCurrent(gen, (state) => {
        const restored = State.withRadarEnabled(state, radar.current.avail);
        return nowMs === null
          ? restored
          : State.projectFreshness(
              restored,
              nowMs,
              Req.seconds(latest.current.cadence),
              latest.current.cadence === 'paused'
            );
      });
    }
  }, [radarEnabled, setSnapshotIfCurrent]);
  const retryRadar = useCallback(() => {
    if (!life.current.mounted || !latest.current.radarEnabled) return;
    radar.current.gen += 1;
    incrementRadarToken();
    setSnapshot((state) =>
      State.withRadarRetry(state, latest.current.cadence === 'paused')
    );
  }, [incrementRadarToken]);
  useEffect(() => {
    if (!seen.current.cadence) {
      seen.current.cadence = true;
      return;
    }
    life.current.reset = true;
    finishResetIfIdle();
    const nowMs = Fresh.safeNow(latest.current.now);
    setSnapshot((state) =>
      cadence === 'paused' || nowMs === null
        ? State.projectPaused(state, cadence === 'paused')
        : State.projectFreshness(state, nowMs, Req.seconds(cadence), false)
    );
  }, [cadence, finishResetIfIdle]);
  useEffect(() => {
    if (!seen.current.filter) {
      seen.current.filter = true;
      return;
    }
    const gen = life.current.gen;
    const nowMs = Fresh.safeNow(latest.current.now);
    if (nowMs === null) return;
    anchors.current.set('pois', nowMs);
    setSnapshotIfCurrent(gen, (state) =>
      State.startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    registry
      .start('pois', poiFilter, true)
      .then((outcome) => commitBatch([{ slot: 'pois', outcome }], nowMs, gen));
  }, [commitBatch, poiFilter, registry, setSnapshotIfCurrent]);
  const reportRadarResult = useCallback(
    (token: number, result: Types.OverviewRadarReport) => {
      if (
        !Number.isSafeInteger(token) ||
        token !== radar.current.token ||
        token !== radar.current.gen ||
        !life.current.mounted ||
        !latest.current.radarEnabled
      ) {
        return;
      }
      const nowMs = Fresh.safeNow(latest.current.now);
      if (nowMs === null) return;
      const outcome: SlotOutcome = result.ok
        ? Fresh.radarOutcome(result.frameTimestamp)
        : {
            ok: false as const,
            error: {
              code: 'request-failed',
              message: 'Source refresh failed.',
            },
          };
      setSnapshot((state) =>
        State.commitSlots(
          state,
          [['radar', outcome]],
          nowMs,
          Req.seconds(latest.current.cadence),
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
