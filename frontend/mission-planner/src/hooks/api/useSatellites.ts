import { useQuery } from '@tanstack/react-query';
import { satelliteService } from '../../services/satellites';

export const useSatellites = () => {
  return useQuery({
    queryKey: ['satellites'],
    queryFn: satelliteService.getAll,
  });
};
