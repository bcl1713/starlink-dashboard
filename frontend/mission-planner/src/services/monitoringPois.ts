import { z } from 'zod';
import {
  coordinate,
  finite,
  instant,
  text,
} from './monitoringSchemaPrimitives';

const MAX_POIS = 100;
const etaSeconds = finite.refine((value) => value === -1 || value >= 0, {
  message: 'ETA must be -1 or nonnegative',
});
const poiResponseItemSchema = coordinate.extend({
  poi_id: text.min(1),
  name: text.min(1),
  category: text.nullable(),
  icon: text.min(1),
  active: z.boolean(),
  eta_seconds: etaSeconds,
  eta_type: z.enum(['anticipated', 'estimated']),
  is_pre_departure: z.boolean(),
  flight_phase: z
    .enum(['pre_departure', 'in_flight', 'post_arrival'])
    .nullable(),
  distance_meters: finite.nonnegative(),
  bearing_degrees: finite.min(0).max(360).nullable(),
  course_status: z
    .enum(['on_course', 'slightly_off', 'off_track', 'behind'])
    .nullable(),
  is_on_active_route: z.boolean(),
  projected_latitude: finite.min(-90).max(90).nullable(),
  projected_longitude: finite.min(-180).max(180).nullable(),
  projected_waypoint_index: z.number().int().nonnegative().nullable(),
  projected_route_progress: finite.min(0).max(100).nullable(),
  route_aware_status: z
    .enum(['ahead_on_route', 'already_passed', 'not_on_route', 'pre_departure'])
    .nullable(),
});
const poiSchema = coordinate.extend({
  poi_id: text.min(1),
  name: text.min(1),
  category: text.nullable(),
  eta_seconds: etaSeconds,
  distance_meters: finite.nonnegative(),
  active: z.boolean(),
});
const poiResponseSchema = z
  .strictObject({
    pois: z.array(poiResponseItemSchema).max(MAX_POIS),
    total: z.number().int().nonnegative().max(MAX_POIS),
    timestamp: instant,
  })
  .refine((value) => value.total === value.pois.length, {
    message: 'POI total does not match collection length',
    path: ['total'],
  });

export type ApplicablePoi = z.infer<typeof poiSchema>;

export const parseApplicablePois = (value: unknown): ApplicablePoi[] => {
  assertBoundedPois(value);
  return poiResponseSchema.parse(value).pois.map((poi) =>
    poiSchema.parse({
      poi_id: poi.poi_id,
      name: poi.name,
      category: poi.category,
      eta_seconds: poi.eta_seconds,
      distance_meters: poi.distance_meters,
      active: poi.active,
      latitude: poi.latitude,
      longitude: poi.longitude,
    })
  );
};

function assertBoundedPois(value: unknown): void {
  if (
    isRecord(value) &&
    Array.isArray(value.pois) &&
    value.pois.length > MAX_POIS
  ) {
    throw new Error('POI response exceeds item budget');
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
