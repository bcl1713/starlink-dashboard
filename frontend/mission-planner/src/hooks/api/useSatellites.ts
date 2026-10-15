import { overviewRefreshOptions } from './overview-refresh-options';
import { useQuery } from '@tanstack/react-query';
import { satelliteService } from '../../services/satellites';

export const useSatellites = (live = false) => {
  return useQuery({
    queryKey: ['satellites'],
    queryFn: ({ signal }) => satelliteService.getAll(signal),
    retry: false,
    ...overviewRefreshOptions(live),
  });
};
