import { useQueries } from '@tanstack/react-query';
import { routesApi } from '@/services/routes';
import { inferCallAssociation, type CallAssociation } from './callAssociation';
export interface AssociationMission {
  id: string;
  name: string;
  legs: {
    id: string;
    name: string;
    route_id?: string;
    adjusted_departure_time?: string | null;
    is_active?: boolean;
  }[];
}
/** Reuses the mission's existing route timing queries; no new source or clock. */
export function useMissionAssociation(
  mission: AssociationMission | undefined,
  enabled = true
) {
  const queries = useQueries({
    queries: (mission?.legs ?? []).map((leg) => ({
      queryKey: ['routes', leg.route_id],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        routesApi.get(leg.route_id!, signal),
      enabled: enabled && !!leg.route_id,
      staleTime: 30_000,
      retry: false,
    })),
  });
  const timed = (mission?.legs ?? []).map((leg, index) => {
    const profile = queries[index]?.data?.timing_profile;
    const departure =
      typeof profile?.departure_time === 'string'
        ? profile.departure_time
        : null;
    const arrival =
      typeof profile?.arrival_time === 'string' ? profile.arrival_time : null;
    const start = leg.adjusted_departure_time ?? departure;
    const duration = Date.parse(arrival ?? '') - Date.parse(departure ?? '');
    const end =
      start &&
      Number.isFinite(Date.parse(start)) &&
      Number.isFinite(duration) &&
      duration > 0
        ? new Date(Date.parse(start) + duration).toISOString()
        : null;
    return { id: leg.id, name: leg.name, start, end };
  });
  const at = (time: string | null) => inferCallAssociation(timed, time);
  return {
    at,
    current(time: string | null): CallAssociation | null {
      const active = mission?.legs.filter((leg) => leg.is_active) ?? [];
      if (active.length > 1) return null;
      return active.length === 1
        ? {
            scope: 'leg',
            leg_id: active[0].id,
            previous_leg_id: null,
            next_leg_id: null,
            label: active[0].name,
          }
        : at(time);
    },
  };
}
