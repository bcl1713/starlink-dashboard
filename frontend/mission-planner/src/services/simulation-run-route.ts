import { z } from 'zod';
const finite = z.number().finite();
const timestamp = z.iso.datetime({ offset: true });
const coordinate = {
  latitude: finite.min(-90).max(90),
  longitude: finite.min(-180).max(180),
  altitude: finite.nullable().optional(),
};
export const replayRouteSchema = z
  .object({
    runtime_id: z.string().min(1),
    run_id: z.string().min(1),
    route: z
      .object({
        id: z.string(),
        name: z.string(),
        description: z.string().nullable(),
        point_count: z.number().int().nonnegative(),
        is_active: z.boolean(),
        imported_at: timestamp,
        file_path: z.string(),
        points: z
          .array(
            z
              .object({
                ...coordinate,
                sequence: z.number().int(),
                expected_arrival_time: timestamp.nullable(),
                expected_segment_speed_knots: finite.nonnegative().nullable(),
              })
              .strict()
          )
          .min(2),
        waypoints: z.array(
          z
            .object({
              ...coordinate,
              name: z.string().nullable(),
              description: z.string().nullable(),
              style_url: z.string().nullable(),
              order: z.number().int(),
              role: z.string().nullable(),
              expected_arrival_time: timestamp.nullable(),
            })
            .strict()
        ),
        timing_profile: z
          .object({
            departure_time: timestamp.nullable(),
            arrival_time: timestamp.nullable(),
            total_expected_duration_seconds: finite.nullable(),
            actual_departure_time: timestamp.nullable(),
            actual_arrival_time: timestamp.nullable(),
            flight_status: z.string(),
            has_timing_data: z.boolean(),
            segment_count_with_timing: z.number().int(),
          })
          .strict(),
        has_timing_data: z.boolean(),
        flight_phase: z.string(),
        eta_mode: z.string(),
        poi_count: z.number().int(),
        statistics: z
          .object({
            distance_meters: finite.nonnegative(),
            distance_km: finite.nonnegative(),
            bounds: z
              .object({
                min_lat: finite,
                max_lat: finite,
                min_lon: finite,
                max_lon: finite,
              })
              .strict(),
          })
          .strict(),
      })
      .strict(),
  })
  .strict();
