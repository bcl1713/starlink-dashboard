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
        `/api/overview-weather/radar/${frame}/{z}/{x}/{y}.png` &&
      value.coverage_tile_template ===
        `/api/overview-weather/coverage/${value.coverage_token}/{z}/{x}/{y}.png`
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
const manifestSchema = z.union([readySchema, unavailableSchema]);
export type WeatherSettings = z.infer<typeof settingsSchema>;
export type WeatherManifest = z.infer<typeof manifestSchema>;
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
    return manifestSchema.parse(data);
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
