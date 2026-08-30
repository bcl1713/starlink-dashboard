import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';

import {
  commitSlots,
  emptyOverviewSnapshot,
  projectFreshness,
  withRadarDisabled,
  withRadarEnabled,
  withRadarRetry,
} from './overview-data-reducer';
import type {
  OverviewAvailability,
  OverviewRadarReport,
  UseOverviewDataOptions,
} from './overview-data-types';
import { REQUEST_FAILED_ERROR } from './overview-request-errors';
import { cadenceSeconds } from './overview-cycle-policy';
import { radarOutcome, safeNow } from './overview-freshness';
import type { OverviewLifecycle } from './overview-lifecycle';

type DataSnapshot = ReturnType<typeof emptyOverviewSnapshot>;
type LatestOptions = Pick<
  UseOverviewDataOptions,
  'cadence' | 'radarEnabled' | 'now'
>;
type RadarState = {
  generation: number;
  token: number;
  availability: OverviewAvailability;
};

export function useOverviewRadar(options: {
  lifecycle: OverviewLifecycle;
  latest: MutableRefObject<LatestOptions>;
  radarEnabled: boolean;
  setSnapshot: Dispatch<SetStateAction<DataSnapshot>>;
  setCurrentSnapshot: (
    generation: number,
    update: (snapshot: DataSnapshot) => DataSnapshot
  ) => void;
}) {
  const { lifecycle, latest, radarEnabled, setSnapshot, setCurrentSnapshot } =
    options;
  const [radarRefreshToken, setRadarRefreshToken] = useState(0);
  const radar = useRef<RadarState>({
    generation: 0,
    token: 0,
    availability: 'unknown',
  });
  const previousRadarEnabled = useRef(radarEnabled);

  const incrementRadarToken = useCallback(() => {
    setRadarRefreshToken((value) => {
      const next = value === Number.MAX_SAFE_INTEGER ? 0 : value + 1;
      radar.current.token = next;
      radar.current.generation = next;
      return next;
    });
  }, []);

  const startManualRadarRefresh = useCallback(() => {
    incrementRadarToken();
  }, [incrementRadarToken]);

  const retryRadar = useCallback(() => {
    if (!lifecycle.mounted || !latest.current.radarEnabled) return;
    radar.current.generation += 1;
    incrementRadarToken();
    setSnapshot((state) =>
      withRadarRetry(state, latest.current.cadence === 'paused')
    );
  }, [incrementRadarToken, latest, lifecycle, setSnapshot]);

  const reportRadarResult = useCallback(
    (token: number, result: OverviewRadarReport) => {
      if (
        !Number.isSafeInteger(token) ||
        token !== radar.current.token ||
        token !== radar.current.generation ||
        !lifecycle.mounted ||
        !latest.current.radarEnabled
      ) {
        return;
      }

      const nowMs = safeNow(latest.current.now ?? Date.now);
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
    [latest, lifecycle, setSnapshot]
  );

  useEffect(() => {
    const generation = lifecycle.generation;
    const changed = previousRadarEnabled.current !== radarEnabled;
    previousRadarEnabled.current = radarEnabled;
    if (changed) radar.current.generation += 1;

    if (!radarEnabled) {
      setCurrentSnapshot(generation, (state) => {
        radar.current.availability = state.radar.availability;
        return withRadarDisabled(state);
      });
      return;
    }

    if (!changed) return;

    const nowMs = safeNow(latest.current.now ?? Date.now);
    setCurrentSnapshot(generation, (state) => {
      const restored = withRadarEnabled(state, radar.current.availability);
      return nowMs === null
        ? restored
        : projectFreshness(
            restored,
            nowMs,
            cadenceSeconds(latest.current.cadence),
            latest.current.cadence === 'paused'
          );
    });
  }, [lifecycle, latest, radarEnabled, setCurrentSnapshot]);

  useEffect(
    () => () => {
      radar.current.generation += 1;
    },
    [lifecycle]
  );

  return useMemo(
    () => ({
      radarRefreshToken,
      retryRadar,
      reportRadarResult,
      startManualRadarRefresh,
    }),
    [radarRefreshToken, retryRadar, reportRadarResult, startManualRadarRefresh]
  );
}
