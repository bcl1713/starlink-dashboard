import { sha256 } from '@noble/hashes/sha2.js';
import type { AviationProduct } from '@/services/aviation-weather';
export const GRID_RUN = Date.parse('2026-10-06T00:00:00Z');
export const digest = (bytes: Uint8Array) =>
  Array.from(sha256(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
export function gridFixture(
  instance = 'a'.repeat(64),
  kind: 'winds' | 'air-temperature' = 'winds'
) {
  const buffers = {
    u: new Uint8Array(519840),
    v: new Uint8Array(519840),
    t: new Uint8Array(519840),
    mask: new Uint8Array(259920),
  };
  for (const [name, value] of [
    ['u', -1234],
    ['v', 300],
    ['t', -1000],
  ] as const) {
    const view = new DataView(buffers[name].buffer);
    for (let i = 0; i < 259920; i++) view.setInt16(i * 2, value, true);
  }
  const descriptor = {
    schema: 'aviation-weather-v1',
    representation: 'latlon-grid-v1',
    mask_scope: 'shared-conservative-uvt',
    product_id: 'c'.repeat(64),
    instance_id: instance,
    normalization_version: 'gfs-regular-ll-v1',
    run_at_ms: GRID_RUN,
    lead_seconds: 21600,
    valid_at_ms: GRID_RUN + 21600000,
    retrieved_at_ms: GRID_RUN,
    generated_at_ms: GRID_RUN,
    vertical: { kind: 'pressure', pressure_pa: 50000 },
    grid: {
      width: 720,
      height: 361,
      longitude_start: -180,
      latitude_start: 90,
      longitude_step: 0.5,
      latitude_step: -0.5,
      mask_encoding: 'uint8-validity-v1',
      components: [
        { quantity: 'wind-east', unit: 'm/s', scale: 0.01, offset: 0 },
        { quantity: 'wind-north', unit: 'm/s', scale: 0.01, offset: 0 },
        { quantity: 'air-temperature', unit: 'K', scale: 0.01, offset: 273.15 },
      ],
    },
    buffers: Object.fromEntries(
      Object.entries(buffers).map(([name, bytes]) => [
        name,
        {
          path: `/api/aviation-weather/v1/products/${instance}/${name}.bin`,
          sha256: digest(bytes),
          byte_length: bytes.length,
          dtype: name === 'mask' ? 'uint8' : 'int16-le',
        },
      ])
    ),
  };
  const json = new TextEncoder().encode(JSON.stringify(descriptor));
  const product = {
    state: 'ready',
    layer_id: kind === 'winds' ? 'gfs-winds' : 'gfs-temperature',
    product_type: kind,
    representation: 'latlon-grid-v1',
    product_id: descriptor.product_id,
    instance_id: instance,
    run_at_ms: GRID_RUN,
    lead_seconds: 21600,
    valid_at_ms: GRID_RUN + 21600000,
    retrieved_at_ms: GRID_RUN,
    generated_at_ms: GRID_RUN,
    fresh_until_ms: GRID_RUN + 9 * 3600000,
    expires_at_ms: GRID_RUN + 18 * 3600000,
    grid: descriptor.grid,
    vertical: descriptor.vertical,
    payload: {
      path: `/api/aviation-weather/v1/products/${instance}/grid.json`,
      sha256: digest(json),
      content_type: 'application/json',
      encoded_bytes: json.length + 1819440,
      decoded_bytes: 5 * 1024 ** 2,
      gpu_bytes: 2 * 1024 ** 2,
    },
  } as AviationProduct;
  const response = (path: string) =>
    path.endsWith('grid.json')
      ? new Response(json, {
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': String(json.length),
          },
        })
      : new Response(
          buffers[
            path.split('/').pop()!.replace('.bin', '') as keyof typeof buffers
          ],
          { headers: { 'Content-Type': 'application/octet-stream' } }
        );
  return { descriptor, buffers, json, product, response };
}
