import {
  resolveCityEmission,
  type BloomEmission,
} from '../../pages/overview-bloom-mode';
import type { BloomMode, BloomSettings } from './contracts';
import { SCENARIO } from './scenario';

interface TuningInput {
  sourceSha: string;
  sourceDirty: boolean;
  mode: BloomMode;
  settings: BloomSettings;
  emissions: BloomEmission;
  isolateCities: boolean;
  scene: { full: boolean; path: boolean; paused: boolean; epoch: number };
  frame: Record<string, unknown> | null;
  power: string;
}
export function tuningReport(input: TuningInput) {
  const city = resolveCityEmission(input.mode === 'bloom', input.emissions);
  return structuredClone({
    schema: 'overview-bloom-tuning/v1',
    capturedAt: new Date().toISOString(),
    ...input,
    scenario: SCENARIO,
    texture: 'settlement-mask-current',
    emissionOverridesActive: input.mode === 'bloom',
    cityEmission: {
      intensity: city.intensity,
      colorLinear: city.color.toArray(),
      maxFullMaskNightLuminance:
        city.intensity *
        (city.color.r * 0.299 + city.color.g * 0.587 + city.color.b * 0.114),
      note: 'Upper bound before texture filtering, night fade and bloom downsampling; not an actual pixel measurement.',
    },
  });
}
