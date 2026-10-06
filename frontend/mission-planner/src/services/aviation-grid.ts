import { z } from 'zod';
import { sha256 } from '@noble/hashes/sha2.js';
import {
  gridSchema,
  verticalSchema,
  type AviationProduct,
} from './aviation-weather';
import {
  abortable,
  weatherKey,
  type Reservation,
  type WeatherBudget,
} from '@/pages/aviation-weather/weather-budget';
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const time = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const bufferSchema = z.strictObject({
  path: z.string().max(256),
  sha256: hash,
  byte_length: z.number().int().positive(),
  dtype: z.enum(['int16-le', 'uint8']),
});
const schema = z
  .strictObject({
    schema: z.literal('aviation-weather-v1'),
    representation: z.literal('latlon-grid-v1'),
    mask_scope: z.literal('shared-conservative-uvt'),
    product_id: hash,
    instance_id: hash,
    normalization_version: z.literal('gfs-regular-ll-v1'),
    run_at_ms: time,
    lead_seconds: z.number().int(),
    valid_at_ms: time,
    retrieved_at_ms: time,
    generated_at_ms: time,
    vertical: verticalSchema,
    grid: gridSchema,
    buffers: z.strictObject({
      u: bufferSchema,
      v: bufferSchema,
      t: bufferSchema,
      mask: bufferSchema,
    }),
  })
  .superRefine((d, ctx) => {
    const reject = () =>
      ctx.addIssue({ code: 'custom', message: 'Incoherent normalized grid' });
    const quantities = ['wind-east', 'wind-north', 'air-temperature'];
    if (
      d.grid.width !== 720 ||
      d.grid.height !== 361 ||
      d.grid.components.length !== 3 ||
      d.grid.components.some(
        (c, i) =>
          c.quantity !== quantities[i] ||
          c.scale !== 0.01 ||
          c.offset !== (i === 2 ? 273.15 : 0)
      ) ||
      ![0, 3, 6, 9, 12, 18, 24, 36, 48].includes(d.lead_seconds / 3600) ||
      d.valid_at_ms !== d.run_at_ms + d.lead_seconds * 1000 ||
      d.retrieved_at_ms > d.generated_at_ms ||
      d.run_at_ms > d.generated_at_ms + 60000 ||
      d.generated_at_ms >= d.run_at_ms + 18 * 3600000
    )
      reject();
    if (d.vertical.kind === 'pressure') {
      if (![85000, 50000, 30000, 25000, 20000].includes(d.vertical.pressure_pa))
        reject();
    } else if (d.vertical.kind === 'flight-level') {
      const isa: Record<number, number> = {
        50: 84307.2645406,
        100: 69681.6416236,
        180: 50599.82076785,
        240: 39270.97804732,
        300: 30089.56253744,
        340: 24998.99078423,
        390: 19677.29330547,
        450: 14747.66217617,
      };
      const target = isa[d.vertical.flight_level];
      if (
        !target ||
        d.vertical.derivation !== 'isa-log-pressure-v1' ||
        !(
          d.vertical.source_pressures_pa[0] < target &&
          target < d.vertical.source_pressures_pa[1]
        )
      )
        reject();
    } else reject();
    for (const [name, b] of Object.entries(d.buffers)) {
      if (
        b.path !==
          `/api/aviation-weather/v1/products/${d.instance_id}/${name}.bin` ||
        b.byte_length !== 259920 * (name === 'mask' ? 1 : 2) ||
        b.dtype !== (name === 'mask' ? 'uint8' : 'int16-le')
      )
        reject();
    }
  });
export type GridDescriptor = z.infer<typeof schema>;
export type GridLease = {
  descriptor: GridDescriptor;
  u: Int16Array;
  v: Int16Array;
  t: Int16Array;
  mask: Uint8Array;
  release(): void;
};
export const parseGridDescriptor = (data: unknown): GridDescriptor =>
  schema.parse(data);
export const weatherDigest = (bytes: Uint8Array) =>
  Array.from(sha256(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
export type WeatherFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>;
/** Reserve chunks, concatenation and conversion before receiving their bytes. */
export async function boundedWeatherBytes(
  path: string,
  contentType: string,
  limit: number,
  exact: boolean,
  signal: AbortSignal,
  budget: WeatherBudget,
  fetcher: WeatherFetcher = fetch,
  factor = 4
) {
  const reservation = budget.reserve(weatherKey('transfer'), {
    encoded: 0,
    decoded: limit * factor,
    gpu: 0,
  });
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  const parts: Uint8Array[] = [];
  try {
    const response = await abortable(
      fetcher(path, {
        signal,
        credentials: 'same-origin',
        cache: 'no-cache',
        redirect: 'error',
      }),
      signal
    );
    signal.throwIfAborted();
    const length = response.headers.get('Content-Length');
    if (
      !response.ok ||
      !response.body ||
      response.headers.get('Content-Type')?.split(';')[0].trim() !==
        contentType ||
      (length !== null &&
        (!/^\d+$/.test(length) ||
          Number(length) > limit ||
          (exact && Number(length) !== limit)))
    )
      throw Error('Weather response type or size');
    reader = response.body.getReader();
    let size = 0;
    while (true) {
      const { done, value } = await abortable(reader.read(), signal);
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw Error('Weather stream byte budget');
      parts.push(value);
    }
    signal.throwIfAborted();
    if (exact && size !== limit) throw Error('Weather exact bytes');
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of parts) {
      bytes.set(part, offset);
      offset += part.length;
    }
    parts.length = 0;
    return { bytes, release: () => reservation.release() };
  } catch (error) {
    reservation.release();
    throw error;
  } finally {
    parts.length = 0;
    if (reader) {
      void reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }
}
type Component = {
  promise: Promise<Int16Array | Uint8Array>;
  controller: AbortController;
  owners: number;
  ready: boolean;
  allocation: Reservation;
};
const caches = new WeakMap<WeatherBudget, Map<string, Component>>();
async function component(
  descriptor: GridDescriptor,
  name: 'u' | 'v' | 't' | 'mask',
  signal: AbortSignal,
  budget: WeatherBudget
) {
  const buffer = descriptor.buffers[name];
  const quantization =
    name === 'mask'
      ? null
      : descriptor.grid.components[['u', 'v', 't'].indexOf(name)];
  const key = JSON.stringify([
    buffer.sha256,
    buffer.dtype,
    descriptor.grid,
    descriptor.mask_scope,
    quantization && [
      quantization.unit,
      quantization.scale,
      quantization.offset,
    ],
  ]);
  let cache = caches.get(budget);
  if (!cache) {
    cache = new Map();
    caches.set(budget, cache);
  }
  let entry = cache.get(key);
  if (!entry) {
    const allocation = budget.reserve(key, {
      encoded: buffer.byte_length,
      decoded: buffer.byte_length,
      gpu: 0,
    });
    const controller = new AbortController();
    entry = {
      controller,
      owners: 0,
      ready: false,
      allocation,
      promise: Promise.resolve(new Uint8Array()),
    };
    const owned = entry;
    entry.promise = (async () => {
      let transfer: Awaited<ReturnType<typeof boundedWeatherBytes>> | undefined;
      try {
        transfer = await boundedWeatherBytes(
          buffer.path,
          'application/octet-stream',
          buffer.byte_length,
          true,
          controller.signal,
          budget,
          fetch,
          2
        );
        controller.signal.throwIfAborted();
        if (weatherDigest(transfer.bytes) !== buffer.sha256)
          throw Error('Grid component hash');
        const data =
          name === 'mask'
            ? new Uint8Array(transfer.bytes.length)
            : new Int16Array(transfer.bytes.length / 2);
        if (name === 'mask') {
          if (transfer.bytes.some((v) => v > 3))
            throw Error('Grid validity mask');
          data.set(transfer.bytes);
        } else {
          const view = new DataView(
            transfer.bytes.buffer,
            transfer.bytes.byteOffset,
            transfer.bytes.byteLength
          );
          for (let i = 0; i < data.length; i++)
            data[i] = view.getInt16(i * 2, true);
        }
        owned.ready = true;
        return data;
      } catch (error) {
        allocation.release();
        if (cache!.get(key) === owned) cache!.delete(key);
        throw error;
      } finally {
        transfer?.release();
      }
    })();
    cache.set(key, entry);
  }
  entry.owners++;
  let owned = true;
  const release = () => {
    if (!owned) return;
    owned = false;
    if (--entry!.owners === 0) {
      if (cache!.get(key) === entry) cache!.delete(key);
      if (!entry!.ready) entry!.controller.abort();
      entry!.allocation.release();
    }
  };
  try {
    return { data: await abortable(entry.promise, signal), release };
  } catch (error) {
    release();
    throw error;
  }
}
export async function fetchGrid(
  product: AviationProduct,
  signal: AbortSignal,
  budget: WeatherBudget
): Promise<GridLease> {
  const p = product.payload;
  if (
    !p ||
    product.representation !== 'latlon-grid-v1' ||
    p.content_type !== 'application/json' ||
    p.path !==
      `/api/aviation-weather/v1/products/${product.instance_id}/grid.json` ||
    !/^[a-f0-9]{64}$/.test(product.instance_id ?? '') ||
    p.encoded_bytes > 16 * 1024 ** 2
  )
    throw Error('Invalid immutable model envelope');
  const owner = new AbortController(),
    abort = () => owner.abort(signal.reason);
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) abort();
  const timer = setTimeout(
    () => owner.abort(new DOMException('Weather deadline', 'TimeoutError')),
    45000
  );
  const components: Awaited<ReturnType<typeof component>>[] = [];
  let slot: (() => void) | undefined, metadata: Reservation | undefined;
  let transfer: Awaited<ReturnType<typeof boundedWeatherBytes>> | undefined;
  try {
    slot = await budget.acquire(owner.signal);
    transfer = await boundedWeatherBytes(
      p.path,
      p.content_type,
      Math.min(1024 ** 2, p.encoded_bytes),
      false,
      owner.signal,
      budget
    );
    if (weatherDigest(transfer.bytes) !== p.sha256)
      throw Error('Grid descriptor hash');
    metadata = budget.reserve(weatherKey('grid-descriptor'), {
      encoded: transfer.bytes.length,
      decoded: transfer.bytes.length * 4,
      gpu: 0,
    });
    const descriptor = parseGridDescriptor(
      JSON.parse(
        new TextDecoder('utf-8', { fatal: true }).decode(transfer.bytes)
      )
    );
    if (
      descriptor.instance_id !== product.instance_id ||
      descriptor.product_id !== product.product_id ||
      descriptor.run_at_ms !== product.run_at_ms ||
      descriptor.lead_seconds !== product.lead_seconds ||
      descriptor.valid_at_ms !== product.valid_at_ms ||
      JSON.stringify(descriptor.grid) !== JSON.stringify(product.grid) ||
      JSON.stringify(descriptor.vertical) !==
        JSON.stringify(product.vertical) ||
      transfer.bytes.length +
        Object.values(descriptor.buffers).reduce(
          (n, b) => n + b.byte_length,
          0
        ) !==
        p.encoded_bytes
    )
      throw Error('Grid envelope identity');
    transfer.release();
    transfer = undefined;
    for (const name of ['u', 'v', 't', 'mask'] as const)
      components.push(await component(descriptor, name, owner.signal, budget));
    owner.signal.throwIfAborted();
    let owned = true;
    return {
      descriptor,
      u: components[0].data as Int16Array,
      v: components[1].data as Int16Array,
      t: components[2].data as Int16Array,
      mask: components[3].data as Uint8Array,
      release: () => {
        if (!owned) return;
        owned = false;
        components.forEach((c) => c.release());
        metadata!.release();
      },
    };
  } catch (error) {
    components.forEach((c) => c.release());
    metadata?.release();
    throw error;
  } finally {
    transfer?.release();
    slot?.();
    clearTimeout(timer);
    signal.removeEventListener('abort', abort);
  }
}
