import { useSimulationRun } from '@/hooks/api/useSimulationRun';
import { useSimulationClock } from '@/hooks/useSimulationClock';
import { SimulationRunPanel } from '@/pages/SimulationRunPanel';
import type { MissionLeg } from '@/types/mission';

export function MissionSimulationStatus({
  missionId,
  legs,
}: {
  missionId: string;
  legs: Pick<MissionLeg, 'id' | 'name'>[];
}) {
  const query = useSimulationRun();
  const { stale } = useSimulationClock(query.data, 0, query.isError);
  const run = query.data?.run;
  if (!run || run.mission_id !== missionId) return null;
  const legName = legs.find((leg) => leg.id === run.leg_id)?.name ?? run.leg_id;
  return (
    <div aria-label="Mission simulation" className="mb-6">
      <p>Leg: {legName}</p>
      <SimulationRunPanel
        status={query.data}
        stale={stale}
        compact={query.data?.state !== 'running'}
      />
    </div>
  );
}
