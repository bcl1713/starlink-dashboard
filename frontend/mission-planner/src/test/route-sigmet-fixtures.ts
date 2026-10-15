import catalog from './aviation-catalog.json';
import { advisory, collection, NOW } from '@/pages/aviation-weather/fixtures';
import { weatherDigest } from '@/services/aviation-grid';
export const hash = (c: string) => c.repeat(64);
export function routeSnapshot() {
  const data = { ...collection([]), features: [advisory()] };
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  const product = {
    ...structuredClone(catalog.products[0]),
    layer_id: 'sigmet',
    product_type: 'international-sigmet',
    representation: 'advisory-v1',
    time_kind: 'forecast',
    method_kind: 'reported',
    validity_kind: 'collection',
    observed_at_ms: null,
    issued_at_ms: null,
    valid_at_ms: null,
    valid_from_ms: null,
    valid_to_ms: null,
    generated_at_ms: NOW,
    retrieved_at_ms: NOW,
    fresh_until_ms: NOW + 60000,
    expires_at_ms: NOW + 3600000,
    instance_id: hash('a'),
    coverage: {
      generation: 'sigmet-1',
      expires_at_ms: NOW + 3600000,
      mask_encoding: 'feature-collection-v1',
      missing_meaning: 'unknown-not-clear',
      feed_completeness: 'unknown',
    },
    payload: {
      path: `/api/aviation-weather/v1/products/${hash('a')}/sigmet.json`,
      sha256: weatherDigest(bytes),
      content_type: 'application/geo+json',
      encoded_bytes: bytes.length,
      decoded_bytes: bytes.length * 4,
      gpu_bytes: 1024,
    },
  };
  const snapshot = {
    schema: 'route-sigmets-v1',
    generated_at_ms: NOW,
    settings_revision: 1,
    state_revision: 1,
    generation_id: hash('b'),
    context: {
      context_key: hash('c'),
      source: 'ordinary',
      route_id: 'route-a',
      route_name: 'Route A',
      runtime_id: null,
      run_id: null,
    },
    sigmet_product: product,
    status: 'ready',
    reason: null,
    complete: true,
    truncated: false,
    unresolved: [],
    future_feature_ids: [],
    omitted_features: 0,
    entries: [
      {
        notice_key: hash('d'),
        bulletin_key: hash('e'),
        semantic_digest: hash('f'),
        feature_ids: ['test-advisory'],
        spans: [
          {
            segment_index: 0,
            start_fraction: 0.25,
            end_fraction: 0.75,
            entry: [0, 0],
            exit: [4, 0],
            boundary_error_m: 18.52,
          },
        ],
        attention_order: 1,
        acknowledged: false,
        valid_from_ms: NOW,
        expires_at_ms: NOW + 3600000,
        identity_uncertain: false,
      },
    ],
  };
  return { snapshot, bytes, data };
}
