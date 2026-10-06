import type { ReadyWeatherManifest } from '@/services/overview-weather';
import type { BrowserWeatherClock } from './weather-state';
import { WeatherWork } from './weather-work';
import {
  detailKey,
  type DetailKey,
  type DetailDemand,
} from './weather-detail-selection';

export type DetailContext = {
  generation: number;
  settingsRevision: number;
  manifest: ReadyWeatherManifest;
};
export type DetailPair = {
  context: DetailContext;
  key: DetailKey;
  radar: ImageBitmap;
  coverage: ImageBitmap;
  dispose(): void;
};
export function manifestResourceIdentity(m: ReadyWeatherManifest): string {
  return JSON.stringify([
    m.product_id,
    m.source,
    m.product,
    m.tile_schema,
    m.coverage_encoding,
    m.zoom,
    m.max_zoom,
    m.tile_size,
    m.frame_time_ms,
    m.coverage_token,
    m.coverage_expires_at_ms,
  ]);
}
export function detailContextIdentity(context: DetailContext): string {
  return JSON.stringify([
    context.generation,
    context.settingsRevision,
    manifestResourceIdentity(context.manifest),
  ]);
}
class TileFailure extends Error {
  readonly delay: number;
  constructor(delay: number) {
    super('Weather detail unavailable');
    this.delay = delay;
  }
}
type Entry = { abort: AbortController; pair?: DetailPair };
export class WeatherDetailOwner {
  private context: DetailContext | null = null;
  private entries = new Map<string, Entry>();
  private failures = new Map<string, number>();
  private listeners = new Set<() => void>();
  private demand: DetailDemand = { keys: [], level: 2, texelPixels: 0 };
  private pairCount = 0;
  private pairWaiters: { signal: AbortSignal; start(): void; abort(): void }[] =
    [];
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private closed = false;
  private fetcher: typeof fetch;
  private clock: BrowserWeatherClock;
  readonly work: WeatherWork;
  constructor(
    fetcher: typeof fetch,
    clock: BrowserWeatherClock,
    work: WeatherWork
  ) {
    this.clock = clock;
    this.work = work;
    this.fetcher = fetcher.bind(globalThis);
    work.setDetailEvictor((bytes) => this.evict(bytes));
  }
  snapshot = (): readonly DetailPair[] =>
    [...this.entries.values()].flatMap((entry) =>
      entry.pair ? [entry.pair] : []
    );
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private emit() {
    this.listeners.forEach((listener) => listener());
  }
  setContext(context: DetailContext | null) {
    if (this.closed || (!context && !this.context)) return;
    const same =
      context &&
      this.context &&
      detailContextIdentity(context) === detailContextIdentity(this.context);
    this.context = context;
    if (same) return;
    clearTimeout(this.retryTimer);
    for (const entry of this.entries.values()) {
      entry.abort.abort();
      entry.pair?.dispose();
    }
    this.entries.clear();
    this.failures.clear();
    this.emit();
    if (context) this.setDemand(this.demand);
  }
  setDemand(demand: DetailDemand) {
    if (this.closed) return;
    this.demand = { ...demand, keys: demand.keys.slice(0, 8) };
    const context = this.context;
    if (!context) return;
    const desired = new Set(this.demand.keys.map(detailKey));
    for (const [id, entry] of this.entries) {
      if (!desired.has(id)) {
        entry.abort.abort();
        entry.pair?.dispose();
        this.entries.delete(id);
      }
    }
    for (const [id, until] of this.failures)
      if (until <= this.clock.nowMono()) this.failures.delete(id);
    for (const key of this.demand.keys) {
      const id = detailKey(key);
      if (
        key.z <= context.manifest.zoom ||
        key.z > context.manifest.max_zoom ||
        !Number.isInteger(key.z) ||
        !Number.isInteger(key.x) ||
        !Number.isInteger(key.y) ||
        key.x < 0 ||
        key.y < 0 ||
        key.x >= 2 ** key.z ||
        key.y >= 2 ** key.z
      )
        continue;
      if (
        this.entries.has(id) ||
        (this.failures.get(id) ?? 0) > this.clock.nowMono()
      )
        continue;
      const entry: Entry = { abort: new AbortController() };
      this.entries.set(id, entry);
      void this.load(context, key, entry).finally(() => {
        if (this.entries.get(id) === entry && !entry.pair)
          this.entries.delete(id);
        this.emit();
        this.scheduleRetry();
      });
    }
    this.emit();
  }
  private pairSlot(signal: AbortSignal): Promise<() => void> {
    signal.throwIfAborted();
    const grant = () => {
      this.pairCount++;
      let held = true;
      return () => {
        if (!held) return;
        held = false;
        this.pairCount--;
        this.pairWaiters.shift()?.start();
      };
    };
    if (this.pairCount < 8) return Promise.resolve(grant());
    return new Promise((resolve, reject) => {
      const waiter = {
        signal,
        start: () => {
          signal.removeEventListener('abort', waiter.abort);
          resolve(grant());
        },
        abort: () => {
          this.pairWaiters = this.pairWaiters.filter((item) => item !== waiter);
          reject(signal.reason);
        },
      };
      this.pairWaiters.push(waiter);
      signal.addEventListener('abort', waiter.abort, { once: true });
    });
  }
  private scheduleRetry() {
    clearTimeout(this.retryTimer);
    if (!this.context || this.closed) return;
    const waits = this.demand.keys
      .map((key) => this.failures.get(detailKey(key)))
      .filter((until): until is number => until !== undefined);
    if (waits.length)
      this.retryTimer = setTimeout(
        () => this.setDemand(this.demand),
        Math.max(1, Math.min(...waits) - this.clock.nowMono())
      );
  }
  private evict(bytes: number) {
    for (const [id, entry] of this.entries) {
      if (!entry.pair) continue;
      entry.pair.dispose();
      this.entries.delete(id);
      bytes -= 2 * this.context!.manifest.tile_size ** 2 * 4;
      if (bytes <= 0) break;
    }
    this.emit();
  }
  private async bitmap(
    template: string,
    key: DetailKey,
    signal: AbortSignal
  ): Promise<ImageBitmap> {
    return this.work.run('detail', signal, async () => {
      const response = await this.fetcher(
        template
          .replace('{z}', String(key.z))
          .replace('{x}', String(key.x))
          .replace('{y}', String(key.y)),
        { signal, credentials: 'same-origin' }
      );
      if (!response.ok) {
        const retry = Number(response.headers.get('retry-after'));
        throw new TileFailure(
          Number.isFinite(retry)
            ? Math.max(30, Math.min(300, retry)) * 1000
            : 30000
        );
      }
      if (response.headers.get('content-type')?.split(';')[0] !== 'image/png')
        throw new TileFailure(30000);
      const blob = await response.blob();
      signal.throwIfAborted();
      if (blob.size > 2097152) throw new TileFailure(30000);
      const bitmap = await createImageBitmap(blob);
      try {
        signal.throwIfAborted();
        if (
          bitmap.width !== this.context?.manifest.tile_size ||
          bitmap.height !== this.context.manifest.tile_size
        )
          throw new TileFailure(30000);
        return bitmap;
      } catch (error) {
        bitmap.close();
        throw error;
      }
    });
  }
  private async load(context: DetailContext, key: DetailKey, entry: Entry) {
    const id = detailKey(key),
      signal = entry.abort.signal;
    const timer = setTimeout(
      () =>
        entry.abort.abort(
          new DOMException('Weather detail timed out', 'TimeoutError')
        ),
      45000
    );
    let release: (() => void) | undefined,
      radar: ImageBitmap | undefined,
      coverage: ImageBitmap | undefined;
    try {
      const freePair = await this.pairSlot(signal);
      try {
        const freeBytes = this.work.reserveDecoded(
          2 * context.manifest.tile_size ** 2 * 4
        );
        release = () => {
          freeBytes();
          freePair();
        };
      } catch (error) {
        freePair();
        throw error;
      }
      radar = await this.bitmap(
        context.manifest.radar_tile_template,
        key,
        signal
      );
      coverage = await this.bitmap(
        context.manifest.coverage_tile_template,
        key,
        signal
      );
      signal.throwIfAborted();
      if (
        !this.context ||
        detailContextIdentity(context) !==
          detailContextIdentity(this.context) ||
        this.entries.get(id) !== entry
      )
        throw new DOMException('Obsolete', 'AbortError');
      const heldRadar = radar,
        heldCoverage = coverage,
        free = release;
      let disposed = false;
      entry.pair = {
        context,
        key,
        radar,
        coverage,
        dispose: () => {
          if (!disposed) {
            disposed = true;
            heldRadar.close();
            heldCoverage.close();
            free();
          }
        },
      };
      radar = coverage = undefined;
      release = undefined;
    } catch (error) {
      if (
        !signal.aborted &&
        this.context &&
        detailContextIdentity(context) === detailContextIdentity(this.context)
      )
        this.failures.set(
          id,
          this.clock.nowMono() +
            (error instanceof TileFailure ? error.delay : 30000)
        );
      while (this.failures.size > 48)
        this.failures.delete(this.failures.keys().next().value!);
    } finally {
      clearTimeout(timer);
      radar?.close();
      coverage?.close();
      release?.();
    }
  }
  dispose() {
    if (this.closed) return;
    this.setContext(null);
    this.closed = true;
    this.listeners.clear();
    this.work.setDetailEvictor(null);
  }
}
