import type { FlowPoint } from '../overview-animated-flow-line-rendering';

export const MAX_OBJECTS = 16_384;
export const EARTH_RADIUS_KM = 6378.137;
export const ELEMENT_FIELDS = [
  'MEAN_MOTION',
  'ECCENTRICITY',
  'INCLINATION',
  'RA_OF_ASC_NODE',
  'ARG_OF_PERICENTER',
  'MEAN_ANOMALY',
  'BSTAR',
  'MEAN_MOTION_DOT',
  'MEAN_MOTION_DDOT',
] as const;
export type CatalogObject = { NORAD_CAT_ID: string; EPOCH: string } & Record<
  (typeof ELEMENT_FIELDS)[number],
  number
>;
export type OrbitalStatusKind =
  | 'off'
  | 'loading'
  | 'ready'
  | 'disconnected'
  | 'expired'
  | 'provider-suspended'
  | 'worker-failed';
export interface CatalogEnvelope {
  generation: string;
  acquired_at: string | null;
  last_attempt_at: string | null;
  retry_after_at: string | null;
  suspended: boolean;
  objects: CatalogObject[];
  rejected_count: number;
  truncated_count: number;
  eligible_count: number;
  status: OrbitalStatusKind;
  accepted_count?: number;
  fallback_reason?: string | null;
  provider_error?: string | null;
}
export type OrbitalDiagnostics = Omit<CatalogEnvelope, 'objects'> & {
  active_viewers?: number;
};
export interface OrbitalEndpoints {
  aircraft: FlowPoint | null;
  pop: FlowPoint | null;
}
export interface PropagationResult {
  utcMs: number;
  ids: string[];
  positionsKm: Float64Array<ArrayBuffer>;
  valid: Uint8Array<ArrayBuffer>;
}
export interface OrbitalRoute {
  ids: string[];
  lengthKm: number;
  identity: string;
}
export interface OrbitalSnapshot extends PropagationResult {
  generation: number;
  catalogGeneration: string;
  bankId: number;
  route: OrbitalRoute | null;
  fallbackReason?: string | null;
  updateMs: number;
}
