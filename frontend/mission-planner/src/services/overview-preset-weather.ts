import { z } from 'zod';

export const presetWeatherSchema = z
  .strictObject({
    radar: z.boolean(),
    metar: z.boolean(),
    taf: z.boolean(),
    sigmet: z.boolean(),
    sigmet_intersecting_only: z.boolean(),
    winds: z.boolean(),
    temperature: z.boolean(),
  })
  .refine(
    (value) => !(value.winds && value.temperature),
    'Only one GFS layer may be enabled'
  );
export type PresetWeatherVisibility = z.infer<typeof presetWeatherSchema>;
