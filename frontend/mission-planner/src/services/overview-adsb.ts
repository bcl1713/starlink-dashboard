import { z } from 'zod';
import apiClient from './api-client';
const finite = z.number().finite();
const timestamp = finite.nonnegative();
const hex = z.string().regex(/^[0-9A-F]{6}$/);
const settingsSchema = z.object({
  enabled: z.boolean(),
  mode: z.enum(['military_and_included', 'included_only']),
  include_hexes: z.array(hex),
  exclude_hexes: z.array(hex),
  callsign_substrings: z.array(z.string()),
  revision: z.number().int().nonnegative(),
});
const altitudeSchema = z.object({
  value: finite,
  unit: z.literal('ft'),
  source: z.enum(['barometric', 'geometric']),
});
const contactSchema = z
  .object({
    hex,
    callsign: z.string().nullable(),
    registration: z.string().nullable(),
    aircraft_type: z.string().nullable(),
    military: z.boolean().nullable(),
    latitude: finite.min(-90).max(90),
    longitude: finite.min(-180).max(180),
    altitude: altitudeSchema.nullable(),
    ground_speed_knots: finite.nonnegative().nullable(),
    track_degrees: finite.min(0).lt(360).nullable(),
    position_observed_at_ms: timestamp,
    acquired_at_ms: timestamp,
  })
  .refine(
    (c) => c.position_observed_at_ms <= c.acquired_at_ms,
    'Position observation cannot be in the future'
  );
const sourceSchema = z.object({
  key: z.string().regex(/^(military|hex:[0-9A-F]{6})$/),
  last_success_at_ms: timestamp.nullable(),
  error: z.string().nullable(),
  retry_at_ms: timestamp.nullable(),
});
const bundleSchema = z.object({
  settings_revision: z.number().int().nonnegative(),
  generated_at_ms: timestamp,
  contacts: z.array(contactSchema),
  sources: z.array(sourceSchema),
});
export type AdsbSettings = z.infer<typeof settingsSchema>;
export type AdsbSettingsUpdate = Partial<Omit<AdsbSettings, 'revision'>>;
export type AdsbAltitude = z.infer<typeof altitudeSchema>;
export type AdsbContact = z.infer<typeof contactSchema>;
export type AdsbSourceStatus = z.infer<typeof sourceSchema>;
export type AdsbTrafficBundle = z.infer<typeof bundleSchema>;
export const overviewAdsbApi = {
  async getSettings(signal?: AbortSignal): Promise<AdsbSettings> {
    const { data } = await apiClient.get<unknown>(
      '/api/overview-adsb/settings',
      { signal }
    );
    return settingsSchema.parse(data);
  },
  async updateSettings(changes: AdsbSettingsUpdate): Promise<AdsbSettings> {
    const { data } = await apiClient.put<unknown>(
      '/api/overview-adsb/settings',
      changes
    );
    return settingsSchema.parse(data);
  },
  async getTraffic(signal?: AbortSignal): Promise<AdsbTrafficBundle> {
    const { data } = await apiClient.get<unknown>(
      '/api/overview-adsb/traffic',
      { signal }
    );
    return bundleSchema.parse(data);
  },
};
