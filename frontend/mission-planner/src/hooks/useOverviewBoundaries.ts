import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  MAX_BOUNDARY_BYTES,
  parseBoundaries,
  projectBoundaries,
  type BoundaryKind,
} from '@/pages/overview-boundaries';

export function useOverviewBoundaries(kind: BoundaryKind, enabled: boolean) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['overview-boundaries', kind],
    enabled,
    retry: false,
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(`/boundaries/${kind}.json`, { signal });
      if (
        !response.ok ||
        Number(response.headers.get('content-length')) > MAX_BOUNDARY_BYTES
      )
        throw new Error('Boundary data unavailable');
      if (!response.body) throw new Error('Boundary data unavailable');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let bytes = 0;
      let text = '';
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          bytes += value.byteLength;
          if (bytes > MAX_BOUNDARY_BYTES)
            throw new Error('Boundary data too large');
          text += decoder.decode(value, { stream: true });
        }
        text += decoder.decode();
      } finally {
        await reader.cancel().catch(() => {});
        reader.releaseLock();
      }
      const data = parseBoundaries(JSON.parse(text));
      // Projection failure belongs to this optional data load, never Canvas.
      return { ...data, segments: projectBoundaries(data) };
    },
  });
  useEffect(() => {
    if (!enabled)
      void client.cancelQueries({
        queryKey: ['overview-boundaries', kind],
        exact: true,
      });
  }, [client, enabled, kind]);
  return {
    data: enabled ? query.data : undefined,
    loading: enabled && query.isPending,
    unavailable: enabled && query.isError,
  };
}
