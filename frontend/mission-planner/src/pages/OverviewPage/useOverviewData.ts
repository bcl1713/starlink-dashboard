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
} from './overview-data-reducer';
import type {
  OverviewSlotOutcome,
  UseOverviewDataOptions,
} from './overview-data-types';
import { buildSlotCommits } from './overview-history-continuity';
import {
  DEFAULT_SERVICES,
  createOverviewRequestRegistry,
  manualResultFromOutcomes,
} from './overview-requests';
import {
  beginOverviewCyclePlan,
  cadenceSeconds,
  finishOverviewCyclePlan,
  markOverviewResetPending,
  resetAnchorsAt,
  resetOverviewAnchorsWhenIdle,
  type OverviewCycleReason,
} from './overview-cycle-policy';
import {
  invalidateOverviewLifecycle,
  isOverviewLifecycleCurrent,
  mountOverviewLifecycle,
  OverviewLifecycle,
  raceOverviewLifecycle,
} from './overview-lifecycle';
import { safeNow } from './overview-freshness';
import type { OverviewHttpSlot } from './overview-sources';
import { defaultVisibility } from './overview-visibility';
import { useOverviewRadar } from './useOverviewRadar';
import { useOverviewRefresh } from './useOverviewRefresh';

type DataSnapshot = ReturnType<typeof emptyOverviewSnapshot>;
type CycleOutcome = Readonly<{
  slot: OverviewHttpSlot;
  outcome: OverviewSlotOutcome;
}>;

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
  const seen = useRef({ cadence: false, filter: false });
  const latest = useRef({ cadence, poiFilter, radarEnabled, now, visibility });
  latest.current = { cadence, poiFilter, radarEnabled, now, visibility };

  const setCurrentSnapshot = useCallback(
    (generation: number, update: (snapshot: DataSnapshot) => DataSnapshot) =>
      setSnapshot((state) =>
        isOverviewLifecycleCurrent(lifecycle, generation)
          ? update(state)
          : state
      ),
    [lifecycle]
  );

  const {
    radarRefreshToken,
    retryRadar,
    reportRadarResult,
    startManualRadarRefresh,
  } = useOverviewRadar({
    lifecycle,
    latest,
    radarEnabled,
    setSnapshot,
    setCurrentSnapshot,
  });

  const commitBatch = useCallback(
    (
      outcomes: readonly CycleOutcome[],
      nowMs: number,
      generation: number,
      manualResult?: DataSnapshot['manualResult']
    ) => {
      flushSync(() => {
        setCurrentSnapshot(generation, (current) => {
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
      const anchorMap = anchors.current;
      const { generation, nowMs, selected } = beginOverviewCyclePlan(
        lifecycle,
        reason,
        latest.current,
        anchorMap
      );
      const current = latest.current;

      try {
        if (nowMs === null || selected.length === 0) return;
        if (reason === 'manual') {
          startManualRadarRefresh();
          setCurrentSnapshot(generation, (state) =>
            setManualResult(state, 'idle')
          );
        }
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
          reason === 'manual' ? manualResultFromOutcomes(outcomes) : undefined;
        await commitBatch(outcomes, nowMs, generation, manualResult);
      } finally {
        finishOverviewCyclePlan(lifecycle, generation, () =>
          resetAnchorsAt(anchors.current, latest.current.now)
        );
      }
    },
    [
      commitBatch,
      lifecycle,
      registry,
      setCurrentSnapshot,
      startManualRadarRefresh,
    ]
  );

  const refreshController = useOverviewRefresh({
    cadence,
    now,
    onRefresh: runCycle,
  });

  useEffect(() => {
    const generation = mountOverviewLifecycle(lifecycle);
    Promise.resolve().then(() => {
      if (isOverviewLifecycleCurrent(lifecycle, generation)) {
        void runCycle('bootstrap');
      }
    });
    return () => {
      invalidateOverviewLifecycle(lifecycle);
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
    const generation = lifecycle.generation;
    const nowMs = safeNow(latest.current.now);
    if (nowMs === null) return;

    anchors.current.set('pois', nowMs);
    setCurrentSnapshot(generation, (state) =>
      startSlots(state, ['pois'], latest.current.cadence === 'paused')
    );
    raceOverviewLifecycle(
      registry.start('pois', poiFilter, true),
      lifecycle
    ).then((outcome) =>
      commitBatch([{ slot: 'pois', outcome }], nowMs, generation)
    );
  }, [commitBatch, lifecycle, poiFilter, registry, setCurrentSnapshot]);

  return {
    snapshot,
    controller: {
      isManualRefreshPending: refreshController.isManualRefreshPending,
      manualRefresh: refreshController.manualRefresh,
      radarRefreshToken,
      retryRadar,
      reportRadarResult,
    },
  };
}
