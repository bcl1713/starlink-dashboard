import apiClient from './api-client';

export interface FlightEvent {
  event_id: string;
  revision: number;
  kind: string;
  occurred_at: string;
  detected_at?: string;
  source: string;
  evidence: Record<string, unknown>;
}
export interface FlightEventView {
  status: {
    movement_state: string;
    movement_uncertain: boolean;
    capture_state?: string;
  };
  events: FlightEvent[];
  capture: {
    revision?: string;
    start?: string;
    end?: string;
    complete?: boolean;
    gaps?: { start?: string; end?: string; reason: string }[];
  };
}
export interface TelemetryPreparation {
  id: string;
  state: string;
  download_url?: string | null;
  warning_code?: string | null;
}
export interface FlightRecordingHealth {
  state:
    | 'ready'
    | 'inactive'
    | 'retrying'
    | 'degraded'
    | 'unavailable'
    | 'closed';
  mode: string;
  detection_available: boolean;
  recording_available: boolean;
  history_available: boolean;
  message?: string | null;
  retry_in_seconds?: number | null;
}
const base = (mission: string, leg: string) =>
  `/api/v2/missions/${encodeURIComponent(mission)}/legs/${encodeURIComponent(leg)}`;
export const telemetryArchivesApi = {
  async health(): Promise<FlightRecordingHealth> {
    return (await apiClient.get('/api/flight-recording/status')).data;
  },
  async events(mission: string, leg: string): Promise<FlightEventView> {
    return (await apiClient.get(`${base(mission, leg)}/flight-events`)).data;
  },
  async create(
    mission: string,
    leg: string,
    body: { kind: string; occurred_at: string; reason: string }
  ) {
    return (await apiClient.post(`${base(mission, leg)}/flight-events`, body))
      .data;
  },
  async correct(
    mission: string,
    leg: string,
    event: FlightEvent,
    occurred_at: string,
    reason: string
  ) {
    return (
      await apiClient.patch(
        `${base(mission, leg)}/flight-events/${encodeURIComponent(event.event_id)}`,
        { expected_revision: event.revision, occurred_at, reason }
      )
    ).data;
  },
  async classify(
    mission: string,
    leg: string,
    stop: FlightEvent,
    classification: string,
    reason: string
  ) {
    return (
      await apiClient.post(
        `${base(mission, leg)}/stops/${encodeURIComponent(stop.event_id)}/classification`,
        { classification, reason }
      )
    ).data;
  },
  async prepare(
    mission: string,
    partial: boolean
  ): Promise<TelemetryPreparation> {
    return (
      await apiClient.post(
        `/api/v2/missions/${encodeURIComponent(mission)}/export-preparations`,
        null,
        { params: { artifact_kind: 'telemetry', allow_partial: partial } }
      )
    ).data;
  },
  async preparation(
    mission: string,
    job: string
  ): Promise<TelemetryPreparation> {
    return (
      await apiClient.get(
        `/api/v2/missions/${encodeURIComponent(mission)}/export-preparations/${encodeURIComponent(job)}`
      )
    ).data;
  },
};
