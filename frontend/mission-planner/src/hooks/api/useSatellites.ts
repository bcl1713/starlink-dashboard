import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { satelliteService } from '../../services/satellites';
import type { Satellite } from '../../types/satellite';

export const useSatellites = () => {
  return useQuery({
    queryKey: ['satellites'],
    queryFn: satelliteService.getAll,
  });
};

export const useCreateSatellite = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: satelliteService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['satellites'] });
    },
  });
};

export const useUpdateSatellite = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Satellite> }) =>
      satelliteService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['satellites'] });
    },
  });
};

export const useDeleteSatellite = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: satelliteService.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['satellites'] });
    },
  });
};
