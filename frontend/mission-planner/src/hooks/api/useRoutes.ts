import { overviewRefreshOptions } from './overview-refresh-options';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { routesApi } from '../../services/routes';

export function useRoutes(live = false) {
  return useQuery({
    queryKey: ['routes'],
    queryFn: ({ signal }) => routesApi.list(signal),
    ...overviewRefreshOptions(live),
  });
}

export function useRoute(routeId: string, live = false) {
  return useQuery({
    queryKey: ['routes', routeId],
    queryFn: ({ signal }) => routesApi.get(routeId, signal),
    ...overviewRefreshOptions(live),
    enabled: !!routeId,
  });
}

export function useUploadRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => routesApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routes'] });
    },
  });
}

export function useActivateRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (routeId: string) => routesApi.activate(routeId),
    onSuccess: (_, routeId) => {
      queryClient.invalidateQueries({ queryKey: ['routes'] });
      queryClient.invalidateQueries({ queryKey: ['routes', routeId] });
      // Cross-cache invalidation: route activation changes POI projections
      queryClient.invalidateQueries({ queryKey: ['pois'] });
    },
  });
}

export function useDeactivateRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (routeId: string) => routesApi.deactivate(routeId),
    onSuccess: (_, routeId) => {
      queryClient.invalidateQueries({ queryKey: ['routes'] });
      queryClient.invalidateQueries({ queryKey: ['routes', routeId] });
      // Cross-cache invalidation: route deactivation clears POI projections
      queryClient.invalidateQueries({ queryKey: ['pois'] });
    },
  });
}

export function useDeleteRoute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (routeId: string) => routesApi.delete(routeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routes'] });
    },
  });
}

export function useDownloadRoute() {
  return useMutation({
    mutationFn: (routeId: string) => routesApi.download(routeId),
  });
}
