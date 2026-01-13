import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { routesApi } from '../../services/routes';

export function useRoutes() {
  return useQuery({
    queryKey: ['routes'],
    queryFn: routesApi.list,
  });
}

export function useRoute(routeId: string) {
  return useQuery({
    queryKey: ['routes', routeId],
    queryFn: () => routesApi.get(routeId),
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
