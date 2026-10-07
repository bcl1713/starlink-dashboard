import { afterEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import {
  AviationController,
  fetchAviationPayload,
} from './aviation-controller';
import type {
  AviationProduct,
  AviationCatalog,
  AviationSettings,
} from '@/services/aviation-weather';
import { NOW, station, collection } from './fixtures';
import { WeatherBudget } from './weather-budget';
const settings: AviationSettings = {
  metar: true,
  taf: false,
  sigmet: false,
  revision: 1,
};
async function payload(taf = false) {
  const bytes = new TextEncoder().encode(
    JSON.stringify(collection([station(taf)]))
  );
  const hash = Array.from(
    new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)),
    (v) => v.toString(16).padStart(2, '0')
  ).join('');
  const product = {
    layer_id: taf ? 'taf' : 'metar',
    state: 'ready',
    product_type: taf ? 'taf' : 'metar-speci',
    expires_at_ms: NOW + 3600000,
    fresh_until_ms: NOW + 60000,
    payload: {
      path: `/api/aviation-weather/v1/products/${hash}/${taf ? 'taf' : 'metar'}.json`,
      sha256: hash,
      content_type: 'application/geo+json',
      encoded_bytes: bytes.length,
      decoded_bytes: bytes.length * 4,
      gpu_bytes: bytes.length * 4,
    },
  } as AviationProduct;
  return { bytes, product };
}
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
describe('bounded aviation ownership', () => {
  it('checks exact bytes, content type and digest before JSON decoding', async () => {
    vi.stubGlobal('crypto', webcrypto);
    const { bytes, product } = await payload();
    const response = () =>
      new Response(bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      });
    expect(
      (
        await fetchAviationPayload(
          product,
          'metar',
          new AbortController().signal,
          async () => response()
        )
      ).features
    ).toHaveLength(1);
    for (const broken of [
      new Response(bytes, { headers: { 'Content-Type': 'application/json' } }),
      new Response(bytes.slice(1), {
        headers: { 'Content-Type': 'application/geo+json' },
      }),
      new Response(new Uint8Array(bytes.length), {
        headers: { 'Content-Type': 'application/geo+json' },
      }),
    ])
      await expect(
        fetchAviationPayload(
          product,
          'metar',
          new AbortController().signal,
          async () => broken
        )
      ).rejects.toThrow();
  });
  it('never fetches a third-party or nonimmutable payload path', async () => {
    const { product } = await payload();
    product.payload!.path = 'https://evil.example/metar.json';
    await expect(
      fetchAviationPayload(
        product,
        'metar',
        new AbortController().signal,
        vi.fn()
      )
    ).rejects.toThrow();
  });
  it('aborts pending work on hide/offline/disable and ignores obsolete generations', async () => {
    vi.useFakeTimers({
      toFake: [
        'setTimeout',
        'clearTimeout',
        'setInterval',
        'clearInterval',
        'Date',
        'performance',
      ],
    });
    vi.setSystemTime(NOW);
    let signal: AbortSignal | undefined;
    let resolve: (v: AviationCatalog) => void = () => {};
    const api = {
      getCatalog: (s?: AbortSignal) => {
        signal = s;
        return new Promise<AviationCatalog>((r) => {
          resolve = r;
        });
      },
    };
    const c = new AviationController(api, vi.fn());
    c.start();
    c.setSettings(settings);
    expect(signal?.aborted).toBe(false);
    c.setVisible(false);
    expect(signal?.aborted).toBe(true);
    resolve({
      schema: 'aviation-weather-v1',
      generated_at_ms: NOW,
      settings_revision: 1,
      products: [],
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(c.snapshot().layers.metar?.data).toBeUndefined();
    c.setVisible(true);
    expect(signal?.aborted).toBe(false);
    c.setOnline(false);
    expect(signal?.aborted).toBe(true);
    c.setOnline(true);
    c.setSettings({ ...settings, metar: false, revision: 2 });
    expect(signal?.aborted).toBe(true);
    expect(c.snapshot().layers.metar?.state).toBe('off');
    c.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });
  it('expires features using UTC without extending freshness after failure', async () => {
    vi.stubGlobal('crypto', webcrypto);
    vi.useFakeTimers({
      toFake: [
        'setTimeout',
        'clearTimeout',
        'setInterval',
        'clearInterval',
        'Date',
        'performance',
      ],
    });
    vi.setSystemTime(NOW);
    const { bytes, product } = await payload();
    const api = {
      getCatalog: vi.fn().mockResolvedValue({
        schema: 'aviation-weather-v1',
        generated_at_ms: NOW,
        settings_revision: 1,
        products: [product],
      }),
    };
    const c = new AviationController(
      api,
      async () =>
        new Response(bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
    );
    c.start();
    c.setSettings(settings);
    await vi.waitFor(() =>
      expect(c.snapshot().layers.metar?.state).toBe('current')
    );
    api.getCatalog.mockRejectedValue(new Error('unavailable'));
    await vi.advanceTimersByTimeAsync(60000);
    expect(c.snapshot().layers.metar?.state).toBe('stale');
    await vi.advanceTimersByTimeAsync(3600000);
    expect(c.snapshot().layers.metar?.data).toBeUndefined();
    c.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });
  it('fences settings revisions and catalog responses', async () => {
    vi.useFakeTimers({
      toFake: [
        'setTimeout',
        'clearTimeout',
        'setInterval',
        'clearInterval',
        'Date',
        'performance',
      ],
    });
    vi.setSystemTime(NOW);
    const { product } = await payload();
    const fetcher = vi.fn();
    const c = new AviationController(
      {
        getCatalog: async () => ({
          schema: 'aviation-weather-v1',
          generated_at_ms: NOW,
          settings_revision: 0,
          products: [product],
        }),
      },
      fetcher
    );
    c.start();
    c.setSettings(settings);
    await vi.advanceTimersByTimeAsync(10);
    expect(fetcher).not.toHaveBeenCalled();
    c.setSettings({ ...settings, metar: false, revision: 2 });
    c.setSettings(settings);
    expect(c.snapshot().layers.metar?.state).toBe('off');
    c.dispose();
  });
  it('rejects declarations that cannot reserve decoded/current/candidate budgets', async () => {
    vi.stubGlobal('crypto', webcrypto);
    vi.useFakeTimers({
      toFake: [
        'setTimeout',
        'clearTimeout',
        'setInterval',
        'clearInterval',
        'Date',
        'performance',
      ],
    });
    vi.setSystemTime(NOW);
    const { product } = await payload();
    product.payload!.decoded_bytes = 33 * 1024 ** 2;
    const fetcher = vi.fn();
    const c = new AviationController(
      {
        getCatalog: async () => ({
          schema: 'aviation-weather-v1',
          generated_at_ms: NOW,
          settings_revision: 1,
          products: [product],
        }),
      },
      fetcher
    );
    c.start();
    c.setSettings(settings);
    await vi.advanceTimersByTimeAsync(10);
    expect(fetcher).not.toHaveBeenCalled();
    expect(c.snapshot().layers.metar?.state).toBe('unavailable');
    c.dispose();
  });
});

it('terminates its catalog deadline even when transport ignores the abort signal', async () => {
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(NOW);
  let signal: AbortSignal | undefined;
  const c = new AviationController(
    {
      getCatalog: (s) => {
        signal = s;
        return new Promise(() => {});
      },
    },
    vi.fn()
  );
  c.start();
  c.setSettings(settings);
  await vi.advanceTimersByTimeAsync(45000);
  expect(signal?.aborted).toBe(true);
  expect(c.snapshot().layers.metar?.state).toBe('unavailable');
  c.dispose();
  expect(vi.getTimerCount()).toBe(0);
});

it('replaces the forecast marker at BECMG completion even while group intervals stay active', async () => {
  vi.stubGlobal('crypto', webcrypto);
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(NOW);
  const f = station(true),
    g = f.properties.forecast_groups[0];
  f.properties.forecast_groups.push({
    ...g,
    change_type: 'BECMG' as never,
    time_becoming_ms: (NOW + 30000) as never,
    valid_from_ms: NOW,
    visibility_m: 100,
    visibility_lower_bound: false,
  });
  const bytes = new TextEncoder().encode(JSON.stringify(collection([f]))),
    { product } = await payload(true);
  product.payload!.encoded_bytes = bytes.length;
  product.payload!.decoded_bytes = bytes.length * 4;
  product.payload!.gpu_bytes = bytes.length * 4;
  product.payload!.sha256 = Array.from(
    new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)),
    (v) => v.toString(16).padStart(2, '0')
  ).join('');
  const c = new AviationController(
    {
      getCatalog: async () => ({
        schema: 'aviation-weather-v1',
        generated_at_ms: NOW,
        settings_revision: 1,
        products: [product],
      }),
    },
    async () =>
      new Response(bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      })
  );
  c.start();
  c.setSettings({ ...settings, metar: false, taf: true });
  await vi.waitFor(() =>
    expect(c.snapshot().layers.taf?.state).toBe('current')
  );
  const original = c.snapshot().layers.taf.drawing!.object.uuid;
  await vi.advanceTimersByTimeAsync(35000);
  expect(c.snapshot().layers.taf.drawing!.object.uuid).not.toBe(original);
  c.dispose();
});

it('uses verified server UTC plus monotonic elapsed time despite a behind or rolled-back client clock', async () => {
  vi.stubGlobal('crypto', webcrypto);
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(NOW - 86400000);
  const { bytes, product } = await payload();
  const c = new AviationController(
    {
      getCatalog: async () => ({
        schema: 'aviation-weather-v1',
        generated_at_ms: NOW,
        settings_revision: 1,
        products: [product],
      }),
    },
    async () =>
      new Response(bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      })
  );
  c.start();
  c.setSettings(settings);
  await vi.waitFor(() =>
    expect(c.snapshot().layers.metar?.state).toBe('current')
  );
  expect(c.snapshot().now).toBeGreaterThanOrEqual(NOW);
  vi.setSystemTime(NOW - 7 * 86400000);
  await vi.advanceTimersByTimeAsync(65000);
  expect(c.snapshot().layers.metar?.state).toBe('stale');
  await vi.advanceTimersByTimeAsync(3600000);
  expect(c.snapshot().layers.metar?.data).toBeUndefined();
  c.dispose();
});

it('rejects future METAR observations against verified UTC independent of the client clock', async () => {
  vi.stubGlobal('crypto', webcrypto);
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(NOW + 90000);
  const f = station();
  f.properties.observed_at_ms = NOW + 120000;
  f.properties.fresh_until_ms = NOW + 300000;
  const bytes = new TextEncoder().encode(JSON.stringify(collection([f]))),
    { product } = await payload();
  product.payload!.encoded_bytes = bytes.length;
  product.payload!.decoded_bytes = bytes.length * 4;
  product.payload!.gpu_bytes = bytes.length * 4;
  product.payload!.sha256 = Array.from(
    new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)),
    (v) => v.toString(16).padStart(2, '0')
  ).join('');
  const c = new AviationController(
    {
      getCatalog: async () => ({
        schema: 'aviation-weather-v1',
        generated_at_ms: NOW,
        settings_revision: 1,
        products: [product],
      }),
    },
    async () =>
      new Response(bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      })
  );
  c.start();
  c.setSettings(settings);
  await vi.waitFor(() =>
    expect(c.snapshot().layers.metar?.state).not.toBe('loading')
  );
  expect(c.snapshot().layers.metar?.state).toBe('unavailable');
  c.dispose();
});

it('still verifies SHA256 on HTTP when browser SubtleCrypto is absent', async () => {
  vi.stubGlobal('crypto', {});
  const { bytes, product } = await payload();
  expect(
    (
      await fetchAviationPayload(
        product,
        'metar',
        new AbortController().signal,
        async () =>
          new Response(bytes, {
            headers: { 'Content-Type': 'application/geo+json' },
          })
      )
    ).features
  ).toHaveLength(1);
  await expect(
    fetchAviationPayload(
      product,
      'metar',
      new AbortController().signal,
      async () =>
        new Response(new Uint8Array(bytes.length), {
          headers: { 'Content-Type': 'application/geo+json' },
        })
    )
  ).rejects.toThrow(/digest/);
});

it('shares the optional decoded allowance with GFS and highlights before fetching', async () => {
  const budget = new WeatherBudget();
  const occupied = budget.reserve('GFS-and-highlight', {
    encoded: 0,
    decoded: 32 * 1024 ** 2,
    gpu: 0,
  });
  const { product, bytes } = await payload();
  const fetcher = vi.fn(
    async () =>
      new Response(bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      })
  );
  const controller = new AviationController(
    {
      getCatalog: async () => ({
        schema: 'aviation-weather-v1',
        generated_at_ms: NOW,
        settings_revision: 1,
        products: [product],
      }),
    },
    fetcher,
    budget
  );
  try {
    controller.start();
    controller.setSettings(settings);
    await vi.waitFor(() =>
      expect(controller.snapshot().layers.metar.state).not.toBe('loading')
    );
    expect(fetcher).not.toHaveBeenCalled();
    expect(controller.snapshot().layers.metar.state).toBe('unavailable');
  } finally {
    controller.dispose();
    occupied.release();
  }
  await Promise.resolve();
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    gpu: 0,
    slots: 0,
  });
});
