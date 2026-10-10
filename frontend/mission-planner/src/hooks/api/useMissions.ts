import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { missionsApi, type PlanningCAS } from '../../services/missions';
import type { SimulationStart } from '@/services/simulation-run';
import { confirmSimulationRun } from './useSimulationRun';
import type {
  CreateMissionRequest,
  UpdateMissionRequest,
  MissionLeg,
  UpdateLegResponse,
} from '../../types/mission';

export function useMissions() {
  return useQuery({
    queryKey: ['missions'],
    queryFn: missionsApi.list,
  });
}

export function useMissionsPage(limit: number, offset: number) {
  return useQuery({
    queryKey: ['missions', { limit, offset }],
    queryFn: () => missionsApi.listPage(limit, offset),
  });
}

export function useMission(id: string) {
  return useQuery({
    queryKey: ['missions', id],
    queryFn: () => missionsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateMission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (mission: CreateMissionRequest) => missionsApi.create(mission),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useUpdateMission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      updates,
    }: {
      id: string;
      updates: UpdateMissionRequest;
    }) => missionsApi.update(id, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
      queryClient.invalidateQueries({ queryKey: ['missions', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['planning', variables.id] });
    },
  });
}

export function useDeleteMission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => missionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useAddLeg(missionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (leg: Partial<MissionLeg>) =>
      missionsApi.addLeg(missionId, leg),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['planning', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useDeleteLeg(missionId: string, planning?: PlanningCAS) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (value: string | { legId: string; planning: PlanningCAS }) =>
      typeof value === 'string'
        ? missionsApi.deleteLeg(missionId, value, planning)
        : missionsApi.deleteLeg(missionId, value.legId, value.planning),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['planning', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useUpdateLeg(
  missionId: string,
  legId: string,
  planning?: PlanningCAS
) {
  const queryClient = useQueryClient();

  return useMutation<UpdateLegResponse, Error, MissionLeg>({
    mutationFn: (leg: MissionLeg) =>
      missionsApi.updateLeg(missionId, legId, leg, planning),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['planning', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
      queryClient.invalidateQueries({ queryKey: ['timeline', legId] });
    },
  });
}

export function useActivateLeg() {
  const queryClient = useQueryClient();

  return useMutation({
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['simulation-run'] });
    },
    mutationFn: ({
      missionId,
      legId,
      simulation,
    }: {
      missionId: string;
      legId: string;
      simulation?: SimulationStart;
    }) =>
      simulation
        ? missionsApi.activateLeg(missionId, legId, simulation)
        : missionsApi.activateLeg(missionId, legId),
    onSuccess: (result, variables) => {
      if (result?.simulation_run)
        confirmSimulationRun(queryClient, result.simulation_run);
      for (const key of [
        'simulation-run',
        'routes',
        'status',
        'overview-upcoming-pois',
        'flight-status',
        'active-x-link',
      ])
        queryClient.invalidateQueries({ queryKey: [key] });
      queryClient.invalidateQueries({
        queryKey: ['missions', variables.missionId],
      });
      queryClient.invalidateQueries({
        queryKey: ['overview-clock-settings'],
      });
    },
  });
}

export function useDeactivateAllLegs(missionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => missionsApi.deactivateAllLegs(missionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['planning', missionId] });
      queryClient.invalidateQueries({ queryKey: ['simulation-run'] });
      queryClient.invalidateQueries({
        queryKey: ['overview-clock-settings'],
      });
    },
  });
}

export function useUpdateLegRoute(missionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ legId, file }: { legId: string; file: File }) =>
      missionsApi.updateLegRoute(missionId, legId, file),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['planning', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
      queryClient.invalidateQueries({
        queryKey: ['timeline', variables.legId],
      });
    },
  });
}
