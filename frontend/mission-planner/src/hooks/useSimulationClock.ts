import { useEffect, useState } from 'react';
import type { SimulationRunStatus } from '@/services/simulation-run';
import { runReceivedAt } from '@/services/simulation-run';
import {
  isRunStale,
  projectMissionTime,
} from '@/pages/simulation-run-projection';

export function useSimulationClock(
  status: SimulationRunStatus | undefined,
  realNowMs: number,
  refreshFailed: boolean
) {
  const [clock, setClock] = useState(() => ({
    status,
    received: performance.now(),
    now: performance.now(),
    display:
      status?.state === 'running'
        ? Date.parse(status.run!.simulation_time)
        : realNowMs,
  }));
  if (clock.status !== status) {
    const now = runReceivedAt(status) ?? clock.now;
    const sameRun =
      status?.runtime_id === clock.status?.runtime_id &&
      status?.run?.run_id === clock.status?.run?.run_id;
    setClock({
      status,
      received: now,
      now,
      display: projectMissionTime(
        status,
        now,
        now,
        realNowMs,
        refreshFailed,
        sameRun ? clock.display : undefined
      ),
    });
  }
  useEffect(() => {
    const timer = window.setInterval(() => {
      const now = performance.now();
      setClock((previous) => ({
        ...previous,
        now,
        display: projectMissionTime(
          previous.status,
          previous.received,
          now,
          Date.now(),
          refreshFailed,
          previous.display
        ),
      }));
    }, 250);
    return () => window.clearInterval(timer);
  }, [refreshFailed]);
  return {
    missionNowMs: status?.state === 'running' ? clock.display : realNowMs,
    stale: Boolean(
      isRunStale(status, clock.received, clock.now, refreshFailed)
    ),
  };
}
