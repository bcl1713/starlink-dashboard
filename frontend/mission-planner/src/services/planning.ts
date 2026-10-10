import { apiClient } from './api-client';
import type {
  AcceptRouteBinding,
  ApplyProposal,
  ApplyRevision,
  ConfirmItinerary,
  GenerateProposal,
  ItineraryPreview,
  PlanningEvaluation,
  PlanningProposal,
  PlanningSatelliteOptions,
  PlanningView,
  PreviewDraft,
  RevisionPreview,
  RouteAnchor,
  RouteBindingPreview,
  SaveDraft,
  SaveReviewed,
  SatelliteSelection,
} from '../types/planning';

const base = '/api/v2/missions/planning';
const missionPath = (id: string) =>
  `${base}/missions/${encodeURIComponent(id)}`;
const legPath = (mission: string, leg: string) =>
  `${missionPath(mission)}/legs/${encodeURIComponent(leg)}`;
const upload = (file: File, revision?: number) => {
  const body = new FormData();
  body.append('file', file);
  if (revision !== undefined)
    body.append('expected_revision', String(revision));
  return body;
};
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } };
export const planningApi = {
  previewItinerary: async (file: File): Promise<ItineraryPreview> => {
    if (file.size > 10 * 1024 * 1024)
      throw new Error('PDF upload exceeds 10 MiB. Choose a smaller file.');
    return (
      await apiClient.post(
        `${base}/itinerary-previews`,
        upload(file),
        multipart
      )
    ).data;
  },
  satelliteOptions: async (): Promise<PlanningSatelliteOptions> =>
    (await apiClient.get(`${base}/satellite-options`)).data,
  create: async (request: ConfirmItinerary): Promise<PlanningView> =>
    (await apiClient.post(`${base}/missions`, request)).data,
  read: async (mission: string): Promise<PlanningView> =>
    (await apiClient.get(missionPath(mission))).data,
  previewRoute: async (
    mission: string,
    leg: string,
    file: File,
    revision: number
  ): Promise<RouteBindingPreview> =>
    (
      await apiClient.post(
        `${legPath(mission, leg)}/route-previews`,
        upload(file, revision),
        multipart
      )
    ).data,
  acceptRoute: async (
    mission: string,
    leg: string,
    request: AcceptRouteBinding
  ): Promise<PlanningView> =>
    (await apiClient.post(`${legPath(mission, leg)}/route`, request)).data,
  saveDraft: async (
    mission: string,
    leg: string,
    request: SaveDraft
  ): Promise<PlanningView> =>
    (await apiClient.put(`${legPath(mission, leg)}/draft`, request)).data,
  previewDraft: async (
    mission: string,
    leg: string,
    request: PreviewDraft
  ): Promise<PlanningEvaluation> =>
    (await apiClient.post(`${legPath(mission, leg)}/preview`, request)).data,
  generateProposal: async (
    mission: string,
    leg: string,
    request: GenerateProposal
  ): Promise<PlanningProposal> =>
    (
      await apiClient.post(`${legPath(mission, leg)}/proposals`, request, {
        timeout: 40_000,
      })
    ).data,
  readProposal: async (
    mission: string,
    leg: string,
    proposal: string
  ): Promise<PlanningProposal> =>
    (
      await apiClient.get(
        `${legPath(mission, leg)}/proposals/${encodeURIComponent(proposal)}`
      )
    ).data,
  applyProposal: async (
    mission: string,
    leg: string,
    request: ApplyProposal
  ): Promise<PlanningView> =>
    (await apiClient.post(`${legPath(mission, leg)}/apply`, request)).data,
  saveReviewed: async (
    mission: string,
    leg: string,
    request: SaveReviewed
  ): Promise<PlanningView> =>
    (await apiClient.post(`${legPath(mission, leg)}/reviewed`, request)).data,
  previewRevision: async (
    mission: string,
    file: File,
    revision: number
  ): Promise<RevisionPreview> =>
    (
      await apiClient.post(
        `${missionPath(mission)}/itinerary-previews`,
        upload(file, revision),
        multipart
      )
    ).data,
  applyRevision: async (
    mission: string,
    request: ApplyRevision
  ): Promise<PlanningView> =>
    (await apiClient.post(`${missionPath(mission)}/revision`, request)).data,
};
export function planningErrorMessage(error: unknown): string {
  const response = error as {
    response?: { status?: number };
    cause?: { response?: { status?: number } };
  } | null;
  if (
    response?.response?.status === 409 ||
    response?.cause?.response?.status === 409
  )
    return 'Planning state changed or this preview expired. Reload the mission before retrying; an expired upload needs to be uploaded again. Your entered corrections are preserved here.';
  return error instanceof Error
    ? error.message
    : 'Planning request failed. Try again.';
}
export function defaultSatelliteSelection(
  options: PlanningSatelliteOptions
): SatelliteSelection {
  return {
    permitted_satellite_ids: options.satellites
      .filter((s) => s.transport === 'X' && s.eligible)
      .map((s) => s.id),
    access_confirmation: null,
    starshield_enabled: true,
  };
}
/** Expected ordinals are authoritative; executable omissions never shrink the count. */
export function planningDisplayCount(view: PlanningView): number {
  const live = view.expected_legs.filter((card) => !card.leg.retired);
  const linked = new Set(
    view.expected_legs.map((card) => card.leg.installed_leg_id).filter(Boolean)
  );
  return (
    live.length + view.mission.legs.filter((leg) => !linked.has(leg.id)).length
  );
}

export function arRouteSpan(
  coordinates: [number, number][],
  start?: RouteAnchor | null,
  end?: RouteAnchor | null,
  binding?: { route_id: string; content_hash: string }
): [number, number][] {
  if (!start || !end || !binding) return [];
  const valid = (a: RouteAnchor) =>
    a.route_id === binding.route_id &&
    a.content_hash === binding.content_hash &&
    Number.isInteger(a.segment_index) &&
    a.segment_index >= 0 &&
    a.segment_index < coordinates.length &&
    a.fraction >= 0 &&
    a.fraction <= 1 &&
    (a.fraction === 0 || a.segment_index < coordinates.length - 1);
  if (
    !valid(start) ||
    !valid(end) ||
    start.segment_index + start.fraction >= end.segment_index + end.fraction
  )
    return [];
  return [
    [start.latitude, start.longitude],
    ...coordinates.slice(
      Math.floor(start.segment_index + start.fraction) + 1,
      Math.ceil(end.segment_index + end.fraction)
    ),
    [end.latitude, end.longitude],
  ];
}
