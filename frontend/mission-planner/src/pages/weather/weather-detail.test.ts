import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { readyWeather } from '@/test/weather-fixtures';
import { WeatherWork } from './weather-work';
import {
  WeatherDetailOwner,
  detailContextIdentity,
  type DetailContext,
} from './weather-detail';
const owners: WeatherDetailOwner[] = [];
const close = vi.fn();
const context = (): DetailContext => ({
  generation: 1,
  settingsRevision: 1,
  manifest: readyWeather(),
});
const demand = { keys: [{ z: 5, x: 16, y: 16 }], level: 5, texelPixels: 1 };
const flush = async () => {
  for (let n = 0; n < 30; n++) await Promise.resolve();
};
beforeEach(() => {
  close.mockClear();
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width: 512, height: 512, close }))
  );
});
afterEach(() => {
  owners.splice(0).forEach((owner) => owner.dispose());
  vi.unstubAllGlobals();
});
function harness(
  fetcher = vi.fn<typeof fetch>(
    async () =>
      new Response('png', { headers: { 'Content-Type': 'image/png' } })
  )
) {
  const work = new WeatherWork(),
    owner = new WeatherDetailOwner(fetcher, { nowMono: () => 0 }, work);
  owners.push(owner);
  owner.setContext(context());
  return { owner, work, fetcher };
}
it('publishes only a complete pair; identical demand reuses same resources', async () => {
  const h = harness();
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(h.owner.snapshot()).toHaveLength(1));
  expect(h.fetcher).toHaveBeenCalledTimes(2);
  expect(h.work.snapshot().decodedBytes).toBe(2 * 512 * 512 * 4);
  h.owner.setDemand(demand);
  await flush();
  expect(h.fetcher).toHaveBeenCalledTimes(2);
  h.owner.setContext(null);
  expect(close).toHaveBeenCalledTimes(2);
  expect(h.work.snapshot().decodedBytes).toBe(0);
});
it('closes uncancellable decodes after a source/context replacement', async () => {
  const resolutions: ((bitmap: ImageBitmap) => void)[] = [];
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(
      () => new Promise<ImageBitmap>((resolve) => resolutions.push(resolve))
    )
  );
  const h = harness();
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(resolutions.length).toBeGreaterThan(0));
  h.owner.setContext({
    ...context(),
    manifest: {
      ...readyWeather(),
      source: 'fixture-radar',
      product_id: 'b'.repeat(64),
    },
  });
  h.owner.setDemand({ ...demand, keys: [] });
  resolutions
    .splice(0)
    .forEach((resolve) =>
      resolve({ width: 512, height: 512, close } as unknown as ImageBitmap)
    );
  await flush();
  expect(h.owner.snapshot()).toHaveLength(0);
  expect(close).toHaveBeenCalled();
  expect(h.work.snapshot().decodedBytes).toBe(0);
});
it('does not reacquire on provenance-only changes but fences machine identity changes', async () => {
  const first = context();
  const wording = {
    ...first,
    manifest: { ...first.manifest, provenance: 'RainViewer' },
  };
  expect(detailContextIdentity(first)).toBe(detailContextIdentity(wording));
  expect(
    detailContextIdentity({
      ...first,
      manifest: { ...first.manifest, product_id: 'b'.repeat(64) },
    })
  ).not.toBe(detailContextIdentity(first));
  const h = harness();
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(h.owner.snapshot()).toHaveLength(1));
  h.owner.setContext(wording);
  h.owner.setDemand(demand);
  await flush();
  expect(h.fetcher).toHaveBeenCalledTimes(2);
});
it('uses failure cooldown rather than camera polling retries and releases bad dimensions', async () => {
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width: 256, height: 512, close }))
  );
  const h = harness();
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(close).toHaveBeenCalled());
  await flush();
  h.owner.setDemand(demand);
  await flush();
  expect(h.owner.snapshot()).toHaveLength(0);
  expect(h.work.snapshot().decodedBytes).toBe(0);
  expect(h.fetcher).toHaveBeenCalledTimes(1);
});
it('never owns more than eight pairs including pending staging and closes evictions', async () => {
  const h = harness();
  h.owner.setDemand({
    keys: Array.from({ length: 8 }, (_, x) => ({ z: 5, x, y: 16 })),
    level: 5,
    texelPixels: 1,
  });
  await vi.waitFor(() => expect(h.owner.snapshot()).toHaveLength(8));
  h.owner.setDemand({
    keys: [{ z: 5, x: 20, y: 16 }],
    level: 5,
    texelPixels: 1,
  });
  await vi.waitFor(() =>
    expect(h.owner.snapshot().some((pair) => pair.key.x === 20)).toBe(true)
  );
  expect(close).toHaveBeenCalledTimes(16);
  expect(h.work.snapshot().decodedBytes).toBe(2 * 512 * 512 * 4);
});
it('counts cancelled native staging until it really closes before starting replacement pairs', async () => {
  const completions: ((bitmap: ImageBitmap) => void)[] = [];
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(
      () => new Promise<ImageBitmap>((resolve) => completions.push(resolve))
    )
  );
  const h = harness(),
    selection = (offset: number) => ({
      keys: Array.from({ length: 8 }, (_, x) => ({
        z: 5,
        x: x + offset,
        y: 16,
      })),
      level: 5,
      texelPixels: 1,
    });
  h.owner.setDemand(selection(0));
  await vi.waitFor(() => expect(completions).toHaveLength(2));
  h.owner.setDemand(selection(8));
  await flush();
  expect(h.work.snapshot().decodedBytes).toBeLessThanOrEqual(16 * 1024 * 1024);
  h.owner.setContext(null);
  completions
    .splice(0)
    .forEach((resolve) =>
      resolve({ width: 512, height: 512, close } as unknown as ImageBitmap)
    );
  await flush();
  expect(h.work.snapshot().decodedBytes).toBe(0);
});
it('camera movement away and back cannot bypass the failure cooldown', async () => {
  const fetcher = vi.fn<typeof fetch>(
    async () =>
      new Response('', { status: 503, headers: { 'Retry-After': '300' } })
  );
  const h = harness(fetcher);
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  await flush();
  h.owner.setDemand({ ...demand, keys: [] });
  h.owner.setDemand(demand);
  await flush();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('evicts and closes detail bitmap pairs when coarse staging needs its decoded reservation', async () => {
  const h = harness();
  h.owner.setDemand({
    keys: Array.from({ length: 8 }, (_, x) => ({ z: 5, x, y: 16 })),
    level: 5,
    texelPixels: 1,
  });
  await vi.waitFor(() => expect(h.owner.snapshot()).toHaveLength(8));
  const coarseAndCanvases = h.work.reserveDecoded(80 * 1024 * 1024);
  const decode = h.work.reserveDecoded(512 * 512 * 4);
  expect(close).toHaveBeenCalledTimes(2);
  expect(h.owner.snapshot()).toHaveLength(7);
  expect(h.work.snapshot().peakDecodedBytes).toBeLessThanOrEqual(
    96 * 1024 * 1024
  );
  coarseAndCanvases();
  decode();
  h.owner.dispose();
  expect(h.work.snapshot().decodedBytes).toBe(0);
});
it('rejects oversized compressed images before native decode starts', async () => {
  const fetcher = vi.fn<typeof fetch>(
    async () =>
      new Response(new Uint8Array(2097153), {
        headers: { 'Content-Type': 'image/png' },
      })
  );
  const h = harness(fetcher);
  h.owner.setDemand(demand);
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
  await flush();
  expect(createImageBitmap).not.toHaveBeenCalled();
  expect(h.owner.snapshot()).toHaveLength(0);
  expect(h.work.snapshot().decodedBytes).toBe(0);
});
