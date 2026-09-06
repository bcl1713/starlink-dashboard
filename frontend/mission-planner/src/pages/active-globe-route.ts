import type { Route } from '../services/routes';

export function activeRouteId(routes: readonly Route[]): string | null {
  return routes.find((route) => route.is_active)?.id ?? null;
}
