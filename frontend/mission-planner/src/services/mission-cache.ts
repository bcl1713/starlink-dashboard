import type { QueryClient } from '@tanstack/react-query';
import type { Mission } from '../types/mission';
import type { MissionPage } from './missions';

export function newestMission(received: Mission, cached?: Mission): Mission {
  const before = Date.parse(cached?.updated_at ?? '');
  const after = Date.parse(received.updated_at ?? '');
  return cached &&
    Number.isFinite(before) &&
    Number.isFinite(after) &&
    before > after
    ? cached
    : received;
}
export function rememberMission(client: QueryClient, mission: Mission) {
  client.setQueryData<Mission>(['missions', mission.id], (current) =>
    newestMission(mission, current)
  );
  client.setQueriesData<Mission[] | MissionPage>(
    { queryKey: ['missions'] },
    (current) => {
      if (Array.isArray(current))
        return current.map((row) =>
          row.id === mission.id ? newestMission(mission, row) : row
        );
      if (current && 'missions' in current)
        return {
          ...current,
          missions: current.missions.map((row) =>
            row.id === mission.id ? newestMission(mission, row) : row
          ),
        };
      return current;
    }
  );
}
