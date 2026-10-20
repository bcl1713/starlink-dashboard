import { aviationWeatherApi } from '@/services/aviation-weather';

export interface TrainingProviderState {
  name: string;
  state: string;
  detail: string;
}
/** Read the admitted catalog only, never fetch an external product to check a lesson. */
export async function readTrainingProviderEvidence() {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 3000);
  try {
    const catalog = await aviationWeatherApi.getCatalog(controller.signal);
    return {
      providerStates: catalog.products.map((product) => ({
        name:
          product.product_type === 'observed-precipitation'
            ? 'Radar'
            : product.layer_id,
        state: product.state,
        detail: product.provenance,
      })),
      outcomes: catalog.products.length ? ['optional-provider-branches'] : [],
    };
  } catch {
    return {
      providerStates: [
        {
          name: 'Weather catalog',
          state: 'read failed',
          detail: 'No confirmed provider response; retry the evidence check.',
        },
      ],
      outcomes: [],
    };
  } finally {
    clearTimeout(deadline);
  }
}
