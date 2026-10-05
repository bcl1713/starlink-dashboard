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
  refreshFailed: boolean,
  animate = false
) {
  const [clock, setClock] = useState(() => ({
    status,
    sample: status,
    received: runReceivedAt(status) ?? performance.now(),
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
    const sameObservation =
      sameRun &&
      status?.revision === clock.status?.revision &&
      status?.run?.observed_at === clock.status?.run?.observed_at;
    const sample = sameObservation ? clock.sample : status;
    const received = sameObservation ? clock.received : now;
    setClock({
      status,
      sample,
      received,
      now,
      display: projectMissionTime(
        sample,
        received,
        now,
        realNowMs,
        refreshFailed,
        sameRun ? clock.display : undefined
      ),
    });
  }
  useEffect(() => {
    let frame = 0;
    const tick = () => {
      const now = performance.now();
      setClock((previous) => ({
        ...previous,
        now,
        display: projectMissionTime(
          previous.sample,
          previous.received,
          now,
          Date.now(),
          refreshFailed,
          previous.display
        ),
      }));
      if (animate && status?.state === 'running' && !refreshFailed) {
        frame = window.requestAnimationFrame(tick);
      }
    };
    if (animate && status?.state === 'running') {
      if (!refreshFailed) frame = window.requestAnimationFrame(tick);
      return () => window.cancelAnimationFrame(frame);
    }
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, [refreshFailed, animate, status?.state]);
  return {
    missionNowMs: status?.state === 'running' ? clock.display : realNowMs,
    stale: Boolean(
      isRunStale(clock.sample, clock.received, clock.now, refreshFailed)
    ),
  };
}
