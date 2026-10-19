import { overviewWeatherApi } from '@/services/overview-weather';
import { aviationWeatherApi } from '@/services/aviation-weather';

export interface TrainingProviderState {
  name: string;
  state: string;
  detail: string;
}
/** Ordinary parsed provider reads; no toggling, data download or outage inference. */
export async function readTrainingProviderEvidence() {
  const [radar, aviation] = await Promise.allSettled([
    overviewWeatherApi.getFrame(),
    aviationWeatherApi.getCatalog(),
  ]);
  const providerStates: TrainingProviderState[] = [];
  const failed = (name: string) => ({
    name,
    state: 'read failed',
    detail: 'No confirmed provider response; retry the evidence check.',
  });
  if (radar.status === 'fulfilled')
    providerStates.push({
      name: 'Radar',
      state: radar.value.state,
      detail: radar.value.provenance,
    });
  else providerStates.push(failed('Radar'));
  if (aviation.status === 'fulfilled')
    providerStates.push(
      ...aviation.value.products.map((product) => ({
        name: product.layer_id,
        state: product.state,
        detail: product.provenance,
      }))
    );
  else providerStates.push(failed('Aviation weather'));
  return {
    providerStates,
    outcomes:
      radar.status === 'fulfilled' &&
      aviation.status === 'fulfilled' &&
      aviation.value.products.length > 0
        ? ['optional-provider-branches']
        : [],
  };
}
