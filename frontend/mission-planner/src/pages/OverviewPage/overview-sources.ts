import type { OverviewSourceKey } from './overview-data-types';

export const SOURCE_LABELS = {
  telemetry: 'Telemetry',
  history: 'History',
  activeLink: 'Active link',
  pois: 'POIs',
  satellites: 'Satellite ETAs',
  missionEvents: 'Mission events',
  route: 'Route',
  groundEntryPoint: 'Ground entry point',
  radar: 'Weather radar',
} as const satisfies Record<OverviewSourceKey, string>;

export const SOURCE_ORDER = [
  'telemetry',
  'history',
  'activeLink',
  'pois',
  'satellites',
  'missionEvents',
  'route',
  'groundEntryPoint',
  'radar',
] as const satisfies readonly OverviewSourceKey[];

export const HTTP_SLOTS = [
  'telemetry',
  'pois',
  'satellites',
  'missionEvents',
  'activeLink',
  'route',
  'groundEntryPoint',
  'history',
] as const;

export type OverviewHttpSlot = (typeof HTTP_SLOTS)[number];
