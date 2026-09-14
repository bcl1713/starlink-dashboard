import { activeXLinkApi } from '@/services/active-x-link';
import { useQuery } from '@tanstack/react-query';

export function useActiveXLink() {
  return useQuery({
    queryKey: ['active-x-link'],
    queryFn: activeXLinkApi.get,
    retry: false,
    refetchInterval: 1_000,
    refetchIntervalInBackground: true,
  });
}
