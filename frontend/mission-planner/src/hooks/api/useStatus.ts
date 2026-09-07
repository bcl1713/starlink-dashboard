import { useQuery } from '@tanstack/react-query';
import { statusApi } from '@/services/status';

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: statusApi.get,
  });
}
