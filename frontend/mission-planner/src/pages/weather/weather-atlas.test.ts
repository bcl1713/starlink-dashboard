/** @vitest-environment jsdom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { readyWeather } from '@/test/weather-fixtures';
import { WeatherAtlasLoader } from './weather-atlas';

const loaders: WeatherAtlasLoader[] = [];
const closed = vi.fn();
const draw = vi.fn();
beforeEach(() => {
  closed.mockClear();
  draw.mockClear();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: draw,
  } as unknown as CanvasRenderingContext2D);
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn().mockImplementation(async () => ({
      width: 512,
      height: 512,
      close: closed,
    }))
  );
});
afterEach(() => {
  loaders.splice(0).forEach((l) => l.dispose());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
function makeLoader(fetcher: typeof fetch) {
  const loader = new WeatherAtlasLoader(fetcher, {
    nowMono: () => performance.now(),
  });
  loaders.push(loader);
  return loader;
}
function pngResponse() {
  return new Response('png', {
    headers: { 'Content-Type': 'image/png' },
  });
}

it('publishes only 16 radar plus 16 complete coverage tiles and shares coverage leases', async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockImplementation(async () => pngResponse());
  const loader = makeLoader(fetcher);
  const first = await loader.load(readyWeather(), new AbortController().signal);
  expect(fetcher).toHaveBeenCalledTimes(32);
  expect(closed).toHaveBeenCalledTimes(32);
  expect(first.radar.width).toBe(2048);
  const second = await loader.load(
    {
      ...readyWeather(),
      frame_time_ms: 1791244800000,
      radar_tile_template:
        '/api/overview-weather/radar/1791244800/{z}/{x}/{y}.png',
    },
    new AbortController().signal
  );
  expect(fetcher).toHaveBeenCalledTimes(48);
  expect(second.coverage).toBe(first.coverage);
  first.dispose();
  expect(second.coverage.width).toBe(2048);
  second.dispose();
  loader.dispose();
  expect(second.coverage.width).toBe(0);
});
it('limits image work to four and aborts a whole load at 45 seconds', async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn<typeof fetch>().mockImplementation(
    (_url, options) =>
      new Promise((_resolve, reject) => {
        options?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('aborted', 'AbortError')),
          { once: true }
        );
      })
  );
  const loader = makeLoader(fetcher);
  const outcome = loader
    .load(readyWeather(), new AbortController().signal)
    .catch((error) => error);
  await vi.advanceTimersByTimeAsync(0);
  expect(fetcher).toHaveBeenCalledTimes(4);
  await vi.advanceTimersByTimeAsync(45000);
  expect(await outcome).toMatchObject({ name: 'TimeoutError' });
  expect(fetcher).toHaveBeenCalledTimes(4);
});
it('closes native decodes resolving after abort without publishing or drawing them', async () => {
  const resolutions: Array<(value: ImageBitmap) => void> = [];
  const decode = vi.fn().mockImplementation(
    () =>
      new Promise((done) => {
        resolutions.push(done);
      })
  );
  vi.stubGlobal('createImageBitmap', decode);
  const loader = makeLoader(
    vi.fn<typeof fetch>().mockImplementation(async () => pngResponse())
  );
  const abort = new AbortController();
  const outcome = loader
    .load(readyWeather(), abort.signal)
    .catch((error) => error);
  // Decoder completion is independently controlled, never cancellation-capable.
  await vi.waitFor(() => expect(decode).toHaveBeenCalledTimes(4));
  abort.abort();
  expect(await outcome).toMatchObject({ name: 'AbortError' });
  resolutions.forEach((resolve) =>
    resolve({
      width: 512,
      height: 512,
      close: closed,
    } as unknown as ImageBitmap)
  );
  await Promise.resolve();
  await Promise.resolve();
  expect(closed).toHaveBeenCalledTimes(4);
  expect(draw).not.toHaveBeenCalled();
});

it('rejects a pre-aborted load without starting or leaking image work', async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockImplementation(async () => pngResponse());
  const loader = makeLoader(fetcher);
  const abort = new AbortController();
  abort.abort();
  await expect(loader.load(readyWeather(), abort.signal)).rejects.toMatchObject(
    { name: 'AbortError' }
  );
  await Promise.resolve();
  await Promise.resolve();
  expect(fetcher).not.toHaveBeenCalled();
});

it('invokes the browser fetch capability with its global receiver', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async function (
    this: unknown
  ) {
    if (this !== globalThis) throw new TypeError('Illegal invocation');
    return pngResponse();
  });
  const loader = makeLoader(fetcher);
  const pair = await loader.load(readyWeather(), new AbortController().signal);
  expect(fetcher).toHaveBeenCalledTimes(32);
  pair.dispose();
});
