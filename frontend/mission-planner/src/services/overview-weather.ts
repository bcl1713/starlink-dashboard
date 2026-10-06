import { z } from 'zod';
import apiClient from './api-client';

const integer = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const settingsSchema = z.strictObject({
  enabled: z.boolean(),
  revision: integer,
});
const common = {
  settings_revision: integer,
  generated_at_ms: integer,
  source: z.string().regex(/^[a-z0-9_-]{1,64}$/),
  provenance: z.string().min(1).max(256),
  product: z.literal('observed-precipitation'),
  product_id: z.string().regex(/^[a-f0-9]{64}$/),
  tile_schema: z.literal('xyz-rgba-pair-v1'),
  coverage_encoding: z.literal('absence-rgba-v1'),
  max_zoom: z.number().int().min(2).max(7),
  attribution: z.strictObject({
    label: z.string().min(1).max(256),
    url: z
      .string()
      .url()
      .max(2048)
      .refine((value) => value.startsWith('https://')),
  }),
  zoom: z.literal(2),
  tile_size: z.literal(512),
};
const readySchema = z
  .strictObject({
    ...common,
    state: z.literal('ready'),
    frame_time_ms: integer,
    coverage_token: integer,
    coverage_expires_at_ms: integer,
    radar_tile_template: z.string(),
    coverage_tile_template: z.string(),
  })
  .refine((value) => {
    const frame = value.frame_time_ms / 1000;
    const age = value.generated_at_ms - value.frame_time_ms;
    return (
      Number.isInteger(frame) &&
      age >= -60000 &&
      age < 3600000 &&
      value.coverage_token === Math.floor(value.generated_at_ms / 86400000) &&
      value.coverage_expires_at_ms === (value.coverage_token + 1) * 86400000 &&
      value.radar_tile_template ===
        `/api/overview-weather/radar/${frame}/{z}/{x}/{y}.png?product_id=${value.product_id}` &&
      value.coverage_tile_template ===
        `/api/overview-weather/coverage/${value.coverage_token}/{z}/{x}/{y}.png?product_id=${value.product_id}`
    );
  }, 'Invalid admitted weather frame');
const unavailableSchema = z.strictObject({
  ...common,
  state: z.enum(['off', 'unavailable']),
  frame_time_ms: z.null(),
  coverage_token: z.null(),
  coverage_expires_at_ms: z.null(),
  radar_tile_template: z.null(),
  coverage_tile_template: z.null(),
});
export const weatherManifestSchema = z.union([readySchema, unavailableSchema]);
export type WeatherCapabilities = Pick<
  ReadyWeatherManifest,
  'zoom' | 'max_zoom' | 'tile_size' | 'tile_schema' | 'coverage_encoding'
>;
export type WeatherSettings = z.infer<typeof settingsSchema>;
export type WeatherManifest = z.infer<typeof weatherManifestSchema>;
export type ReadyWeatherManifest = z.infer<typeof readySchema>;
export type WeatherSettingsObservation = {
  settings: WeatherSettings;
  receivedAtMono: number;
};
export const overviewWeatherApi = {
  async getSettings(signal?: AbortSignal): Promise<WeatherSettings> {
    const { data } = await apiClient.get<unknown>(
      '/api/overview-weather/settings',
      { signal }
    );
    return settingsSchema.parse(data);
  },
  async updateSettings(update: { enabled: boolean }): Promise<WeatherSettings> {
    const { data } = await apiClient.put<unknown>(
      '/api/overview-weather/settings',
      update
    );
    return settingsSchema.parse(data);
  },
  async getFrame(signal?: AbortSignal): Promise<WeatherManifest> {
    const { data } = await apiClient.get<unknown>(
      '/api/overview-weather/frame',
      { signal }
    );
    return weatherManifestSchema.parse(data);
  },
};

export function acceptWeatherObservation(
  old: WeatherSettingsObservation | undefined,
  next: WeatherSettingsObservation
) {
  if (
    old &&
    (old.settings.revision > next.settings.revision ||
      (old.settings.revision === next.settings.revision &&
        old.settings.enabled !== next.settings.enabled))
  ) {
    return old;
  }
  return next;
}
