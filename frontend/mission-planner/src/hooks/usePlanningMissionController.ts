import { useEffect, useMemo } from 'react';
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
