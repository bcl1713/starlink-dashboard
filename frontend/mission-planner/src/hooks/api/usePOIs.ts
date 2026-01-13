import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { poisService } from '../../services/pois';
import type { POICreate, POIUpdate } from '../../services/pois';

export function usePOIs() {
  return useQuery({
    queryKey: ['pois'],
    queryFn: () => poisService.getAllPOIs(),
  });
}

export function usePOI(poiId: string) {
  return useQuery({
    queryKey: ['pois', poiId],
    queryFn: () => poisService.getPOI(poiId),
    enabled: !!poiId,
  });
}

export function useCreatePOI() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (poi: POICreate) => poisService.createPOI(poi),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pois'] });
    },
  });
}

export function useUpdatePOI() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: POIUpdate }) =>
      poisService.updatePOI(id, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['pois'] });
      queryClient.invalidateQueries({ queryKey: ['pois', variables.id] });
    },
  });
}

export function useDeletePOI() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (poiId: string) => poisService.deletePOI(poiId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pois'] });
    },
  });
}

export function usePOIsWithETA() {
  return useQuery({
    queryKey: ['pois', 'with-eta'],
    queryFn: () => poisService.getPOIsWithETA(),
    refetchInterval: 5000, // Poll every 5 seconds for real-time updates
  });
}
