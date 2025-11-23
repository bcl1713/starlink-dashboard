import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { missionsApi } from '../../services/missions';
import type { CreateMissionRequest } from '../../types/mission';

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

export function useDeleteMission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => missionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions'] });
    },
  });
}
