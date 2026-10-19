import { overviewLinkSettingsApi } from '@/services/overview-link-settings';
import { overviewWeatherApi } from '@/services/overview-weather';
import { aviationWeatherApi } from '@/services/aviation-weather';

/** Current confirmed settings reads, never evidence of visual or cue delivery. */
export async function readTrainingDisplayEvidence(): Promise<string[]> {
  const reads = await Promise.allSettled([
    overviewLinkSettingsApi.get(),
    overviewWeatherApi.getSettings(),
    aviationWeatherApi.getSettings(),
  ]);
  return reads.every((read) => read.status === 'fulfilled')
    ? ['display-settings-read']
    : [];
}
