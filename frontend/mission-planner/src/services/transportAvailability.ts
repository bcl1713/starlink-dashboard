import { apiClient } from './api-client';
export type RFTransport = 'X' | 'Ka' | 'Ku';
export type TransportEligibility = Record<RFTransport, boolean>;
export type AvailabilityOverrides = Partial<TransportEligibility>;
export const rfTransports = [
  { key: 'X', label: 'X-band' },
  { key: 'Ka', label: 'Ka' },
  { key: 'Ku', label: 'Starshield' },
] as const;
export interface AvailabilityChange {
  id: string;
  transport: RFTransport;
  unavailable: boolean;
  effective_at: string;
  reason?: string | null;
  simulation_run_id: string | null;
}
export interface AvailabilityView {
  mission_id: string;
  revision: number;
  defaults: AvailabilityOverrides;
  leg_overrides: Record<string, AvailabilityOverrides>;
  history: AvailabilityChange[];
  simulation_run_id: string | null;
  as_of: string | null;
  active_leg_id: string | null;
  effective: TransportEligibility | null;
  operator_actions_allowed: boolean;
  operator_actions_unavailable_reason: string | null;
  legs: Array<{
    leg_id: string;
    installed_leg_id?: string | null;
    x_configuration_required?: boolean;
    planning_effective?: TransportEligibility | null;
    planned: TransportEligibility;
    effective: TransportEligibility | null;
    overrides: AvailabilityOverrides;
  }>;
}
export interface PlannedAvailabilityUpdate {
  defaults?: AvailabilityOverrides;
  leg_overrides?: Record<string, AvailabilityOverrides>;
}
export interface AvailabilityAction {
  transport: RFTransport;
  action: 'unavailable' | 'restore';
  reason?: string;
}
export interface AvailabilityCommand {
  expected_revision: number;
  command_id: string;
}
const path = (missionId: string) =>
  `/api/v2/missions/${encodeURIComponent(missionId)}/availability`;
export const transportAvailabilityApi = {
  read: async (missionId: string, signal?: AbortSignal) =>
    (await apiClient.get<AvailabilityView>(path(missionId), { signal })).data,
  update: async (
    missionId: string,
    command: AvailabilityCommand & PlannedAvailabilityUpdate
  ) => (await apiClient.put<AvailabilityView>(path(missionId), command)).data,
  action: async (
    missionId: string,
    command: AvailabilityCommand &
      AvailabilityAction & { expected_simulation_run_id?: string | null }
  ) =>
    (
      await apiClient.post<AvailabilityView>(
        `${path(missionId)}/actions`,
        command
      )
    ).data,
};
/** Catalog identity is stable even after a rename; custom names are not RF keys. */
export function catalogTransportKey(id: string): RFTransport | null {
  return id === 'Starshield' ? 'Ku' : id === 'X' || id === 'Ka' ? id : null;
}
export function activeTransportFailures(view: AvailabilityView) {
  const failures: Partial<Record<RFTransport, AvailabilityChange>> = {};
  for (const item of view.history) {
    if (
      item.simulation_run_id !== view.simulation_run_id ||
      !view.as_of ||
      Date.parse(item.effective_at) > Date.parse(view.as_of)
    )
      continue;
    if (item.unavailable) failures[item.transport] = item;
    else delete failures[item.transport];
  }
  return failures;
}
export function legAvailability(
  view: AvailabilityView | undefined,
  legId: string
) {
  return view?.legs.find(
    (row) => row.leg_id === legId || row.installed_leg_id === legId
  );
}
