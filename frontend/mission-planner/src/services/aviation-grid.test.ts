import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchGrid, parseGridDescriptor } from './aviation-grid';
import { WeatherBudget } from '@/pages/aviation-weather/weather-budget';
import { digest, gridFixture } from '@/test/gfs-grid';
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe('immutable normalized grid admission', () => {
  it.each([
    'path',
    'identity',
    'length',
    'dtype',
    'unit',
    'geometry',
    'mask-scope',
  ])('rejects descriptor %s before GPU allocation', (failure) => {
    const fixture = gridFixture(),
      data = structuredClone(fixture.descriptor);
    if (failure === 'path') data.buffers.u.path = 'https://evil.test/u.bin';
    if (failure === 'identity') data.instance_id = 'b'.repeat(64);
    if (failure === 'length') data.buffers.u.byte_length--;
    if (failure === 'dtype') data.buffers.u.dtype = 'float32';
    if (failure === 'unit') data.grid.components[0].unit = 'K';
    if (failure === 'geometry') data.grid.longitude_step = 1;
    if (failure === 'mask-scope') data.mask_scope = 'none';
    expect(() => parseGridDescriptor(data)).toThrow();
  });
  it('deduplicates immutable components while sibling descriptors retain their identities', async () => {
    const wind = gridFixture(),
      temperature = gridFixture('b'.repeat(64), 'air-temperature'),
      budget = new WeatherBudget();
    const fetcher = vi.fn(async (path: string) =>
      (path.includes('b'.repeat(64)) ? temperature : wind).response(path)
    );
    vi.stubGlobal('fetch', fetcher);
    const a = await fetchGrid(
      wind.product,
      new AbortController().signal,
      budget
    );
    const b = await fetchGrid(
      temperature.product,
      new AbortController().signal,
      budget
    );
    expect(a.u).toBe(b.u);
    expect(a.mask).toBe(b.mask);
    expect(a.u[0]).toBe(-1234);
    expect(a.t[0]).toBe(-1000);
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(b.descriptor.instance_id).toBe('b'.repeat(64));
    a.release();
    a.release();
    expect(b.u[0]).toBe(-1234);
    expect(budget.snapshot().decoded).toBeGreaterThan(1819440);
    b.release();
    expect(budget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    });
  });
  it('shares equal U/V bytes only under equal physical quantization', async () => {
    const fixture = gridFixture(),
      budget = new WeatherBudget();
    fixture.buffers.v.set(fixture.buffers.u);
    fixture.descriptor.buffers.v.sha256 = digest(fixture.buffers.v);
    const json = new TextEncoder().encode(JSON.stringify(fixture.descriptor));
    fixture.product.payload!.sha256 = digest(json);
    fixture.product.payload!.encoded_bytes = json.length + 1819440;
    const fetcher = vi.fn(async (path: string) =>
      path.endsWith('grid.json')
        ? new Response(json, {
            headers: { 'Content-Type': 'application/json' },
          })
        : fixture.response(path)
    );
    vi.stubGlobal('fetch', fetcher);
    const lease = await fetchGrid(
      fixture.product,
      new AbortController().signal,
      budget
    );
    expect(lease.u).toBe(lease.v);
    expect(fetcher).toHaveBeenCalledTimes(4);
    lease.release();
    expect(budget.snapshot().decoded).toBe(0);
  });
  it('keeps a shared in-flight buffer alive when only one sibling cancels', async () => {
    const wind = gridFixture(),
      temperature = gridFixture('b'.repeat(64), 'air-temperature'),
      budget = new WeatherBudget();
    let complete!: (response: Response) => void, sharedSignal!: AbortSignal;
    const fetcher = vi.fn((path: string, options: RequestInit) => {
      if (path.endsWith('u.bin')) {
        sharedSignal = options.signal!;
        return new Promise<Response>((resolve) => {
          complete = resolve;
        });
      }
      return Promise.resolve(
        (path.includes('b'.repeat(64)) ? temperature : wind).response(path)
      );
    });
    vi.stubGlobal('fetch', fetcher);
    const owner = new AbortController();
    const a = fetchGrid(wind.product, owner.signal, budget);
    const denied = expect(a).rejects.toThrow();
    const b = fetchGrid(
      temperature.product,
      new AbortController().signal,
      budget
    );
    await vi.waitFor(() => expect(complete).toBeDefined());
    for (let i = 0; i < 20; i++) await Promise.resolve();
    owner.abort();
    await denied;
    expect(sharedSignal.aborted).toBe(false);
    complete(wind.response(wind.descriptor.buffers.u.path));
    const lease = await b;
    expect(lease.u[0]).toBe(-1234);
    expect(
      fetcher.mock.calls.filter(([path]) => path.endsWith('u.bin'))
    ).toHaveLength(1);
    lease.release();
    expect(budget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    });
  });
  it.each(['hash', 'type', 'short', 'mask'])(
    'rejects corrupt %s bytes and releases every allocation',
    async (failure) => {
      const fixture = gridFixture(),
        budget = new WeatherBudget();
      if (failure === 'mask') {
        fixture.buffers.mask[0] = 4;
        fixture.descriptor.buffers.mask.sha256 = digest(fixture.buffers.mask);
        const json = new TextEncoder().encode(
          JSON.stringify(fixture.descriptor)
        );
        fixture.product.payload!.sha256 = digest(json);
        fixture.product.payload!.encoded_bytes = json.length + 1819440;
        vi.stubGlobal('fetch', async (path: string) =>
          path.endsWith('grid.json')
            ? new Response(json, {
                headers: { 'Content-Type': 'application/json' },
              })
            : fixture.response(path)
        );
      } else {
        vi.stubGlobal('fetch', async (path: string) =>
          path.endsWith('u.bin')
            ? new Response(
                failure === 'short'
                  ? fixture.buffers.u.slice(1)
                  : failure === 'hash'
                    ? new Uint8Array(519840)
                    : fixture.buffers.u,
                {
                  headers: {
                    'Content-Type':
                      failure === 'type'
                        ? 'text/html'
                        : 'application/octet-stream',
                  },
                }
              )
            : fixture.response(path)
        );
      }
      await expect(
        fetchGrid(fixture.product, new AbortController().signal, budget)
      ).rejects.toThrow();
      expect(budget.snapshot()).toMatchObject({
        encoded: 0,
        decoded: 0,
        gpu: 0,
        slots: 0,
      });
    }
  );
  it('bounds a stalled generation to 45 seconds and ignores a late descriptor', async () => {
    vi.useFakeTimers();
    const fixture = gridFixture(),
      budget = new WeatherBudget();
    let resolve!: (response: Response) => void;
    vi.stubGlobal(
      'fetch',
      () =>
        new Promise<Response>((r) => {
          resolve = r;
        })
    );
    const result = fetchGrid(
      fixture.product,
      new AbortController().signal,
      budget
    );
    const denied = expect(result).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(45000);
    await denied;
    resolve(fixture.response(fixture.product.payload!.path));
    await Promise.resolve();
    expect(budget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });
});
