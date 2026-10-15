import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { planningMissionController } from '../services/planning-mutations';

export function usePlanningMissionController(missionId: string) {
  const client = useQueryClient();
  const controller = useMemo(
    () => planningMissionController(client, missionId),
    [client, missionId]
  );
  useEffect(() => {
    controller.retain();
    return () => controller.release();
  }, [controller]);
  return controller;
}

export function usePlanningEditEpoch(
  controller: ReturnType<typeof planningMissionController>
) {
  return useSyncExternalStore(
    controller.subscribeEdits,
    controller.editSnapshot,
    controller.editSnapshot
  );
}
