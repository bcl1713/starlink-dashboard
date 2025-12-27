import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { missionsApi } from '../../services/missions';
import type {
  CreateMissionRequest,
  UpdateMissionRequest,
  MissionLeg,
} from '../../types/mission';

export function useMissions() {
  return useQuery({
    queryKey: ['missions'],
    queryFn: missionsApi.list,
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
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useDeleteLeg(missionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (legId: string) => missionsApi.deleteLeg(missionId, legId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useUpdateLeg(missionId: string, legId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (leg: MissionLeg) =>
      missionsApi.updateLeg(missionId, legId, leg),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}

export function useActivateLeg() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ missionId, legId }: { missionId: string; legId: string }) =>
      missionsApi.activateLeg(missionId, legId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['missions', variables.missionId],
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
    },
  });
}

export function useUpdateLegRoute(missionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ legId, file }: { legId: string; file: File }) =>
      missionsApi.updateLegRoute(missionId, legId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', missionId] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}
