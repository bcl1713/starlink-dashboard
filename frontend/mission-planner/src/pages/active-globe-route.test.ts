import { describe, expect, it } from 'vitest';
import { activeRouteId } from './active-globe-route';
import type { Route } from '../services/routes';

describe('activeRouteId', () => {
  it('selects the route explicitly marked active', () => {
    const routes: Route[] = [
      {
        id: 'leg-1',
        name: 'Inactive route',
        is_active: false,
      },
      {
        id: 'leg-2',
        name: 'Active route',
        is_active: true,
      },
    ];

    expect(activeRouteId(routes)).toBe('leg-2');
  });

  it('returns null when no route is active', () => {
    const routes: Route[] = [
      {
        id: 'leg-1',
        name: 'First inactive route',
        is_active: false,
      },
      {
        id: 'leg-2',
        name: 'Second inactive route',
        is_active: false,
      },
    ];

    expect(activeRouteId(routes)).toBeNull();
  });
});
