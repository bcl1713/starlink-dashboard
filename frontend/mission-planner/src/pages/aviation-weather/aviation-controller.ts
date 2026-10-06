import { boundedWeatherBytes, weatherDigest } from '@/services/aviation-grid';
import {
  optionalWeatherBudget,
  weatherKey,
  type Reservation,
  type WeatherBudget,
} from './weather-budget';
import type {
  AviationCatalog,
  AviationLayer,
  AviationProduct,
  AviationSettings,
} from '@/services/aviation-weather';
import {
  activeFeatures,
  currentForecastGroups,
  parseAviationFeatures,
  type AviationCollection,
  type AviationStation,
} from '@/services/aviation-features';
import {
  createBudgetedAviationDrawing,
  type AviationDrawing,
} from './aviation-renderer';
const layers: AviationLayer[] = ['metar', 'taf', 'sigmet'];
const limits = [16, 32, 16].map((v) => v * 1024 ** 2);
export type AviationLayerView = {
  state: 'off' | 'loading' | 'current' | 'stale' | 'unavailable';
  product?: AviationProduct;
  data?: AviationCollection;
  drawing?: AviationDrawing;
};
export type AviationView = {
  now: number;
  layers: Record<AviationLayer, AviationLayerView>;
};
export const emptyAviationView: AviationView = {
  now: 0,
  layers: {
    metar: { state: 'off' },
    taf: { state: 'off' },
    sigmet: { state: 'off' },
  },
};
type Entry = {
  product: AviationProduct;
  data: AviationCollection;
  drawing: AviationDrawing;
  signature: string;
  failed: boolean;
  allocation: Reservation;
};
type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>;
const usage = (p: AviationProduct) =>
  p.payload
    ? [p.payload.encoded_bytes, p.payload.decoded_bytes, p.payload.gpu_bytes]
    : [0, 0, 0];
export async function fetchAviationPayload(
  product: AviationProduct,
  layer: AviationLayer,
  signal: AbortSignal,
  fetcher: Fetcher = fetch,
  budget: WeatherBudget = optionalWeatherBudget
): Promise<AviationCollection> {
  const p = product.payload;
  if (
    !p ||
    !/^\/api\/aviation-weather\/v1\/products\/[a-f0-9]{64}\/(metar|taf|sigmet)\.json$/.test(
      p.path
    ) ||
    !p.path.endsWith(`/${layer}.json`) ||
    p.content_type !== 'application/geo+json'
  )
    throw Error('Invalid immutable weather payload');
  const slot = await budget.acquire(signal);
  let transfer: Awaited<ReturnType<typeof boundedWeatherBytes>> | undefined;
  try {
    transfer = await boundedWeatherBytes(
      p.path,
      p.content_type,
      p.encoded_bytes,
      true,
      signal,
      budget,
      fetcher
    );
    if (weatherDigest(transfer.bytes) !== p.sha256)
      throw Error('Weather payload digest');
    signal.throwIfAborted();
    return parseAviationFeatures(
      JSON.parse(
        new TextDecoder('utf-8', { fatal: true }).decode(transfer.bytes)
      ),
      layer
    );
  } finally {
    transfer?.release();
    slot();
  }
}
async function withAbort<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  signal.throwIfAborted();
  let abort: () => void = () => {};
  const cancelled = new Promise<T>((_, reject) => {
    abort = () => reject(new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
  });
  try {
    return await Promise.race([work, cancelled]);
  } finally {
    signal.removeEventListener('abort', abort);
  }
}
export class AviationController {
  private settings: AviationSettings | undefined;
  private anchor: { utc: number; mono: number } | null = null;
  private utc() {
    return this.anchor
      ? this.anchor.utc + Math.max(0, performance.now() - this.anchor.mono)
      : 0;
  }
  private visible = true;
  private online = true;
  private live = false;
  private generation = 0;
  private cycle: AbortController | null = null;
  private deadline: ReturnType<typeof setTimeout> | undefined;
  private tickTimer: ReturnType<typeof setInterval> | undefined;
  private pollTimer: ReturnType<typeof setInterval> | undefined;
  private records = new Map<AviationLayer, Entry>();
  private reservations = new Map<AviationLayer, Reservation>();
  private failed = new Set<AviationLayer>();
  private listeners = new Set<() => void>();
  private view = emptyAviationView;
  private api: {
    getCatalog: (signal?: AbortSignal) => Promise<AviationCatalog>;
  };
  private fetcher: Fetcher;
  private budget: WeatherBudget;
  constructor(
    api: { getCatalog: (signal?: AbortSignal) => Promise<AviationCatalog> },
    fetcher: Fetcher = fetch,
    budget: WeatherBudget = optionalWeatherBudget
  ) {
    this.api = api;
    this.fetcher = fetcher;
    this.budget = budget;
  }
  snapshot = () => this.view;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  start() {
    if (this.live) return;
    this.live = true;
    this.tickTimer = setInterval(() => this.publish(), 5000);
    this.pollTimer = setInterval(() => {
      void this.refresh();
    }, 60000);
    this.publish();
    void this.refresh();
  }
  setSettings(next: AviationSettings | undefined) {
    if (!next || (this.settings && next.revision < this.settings.revision))
      return;
    if (this.settings && next.revision === this.settings.revision) return;
    this.settings = next;
    this.abort();
    for (const l of layers) if (!next[l]) this.remove(l);
    this.failed.clear();
    this.publish();
    void this.refresh();
  }
  setVisible(value: boolean) {
    if (this.visible === value) return;
    this.visible = value;
    this.reconcile();
  }
  setOnline(value: boolean) {
    if (this.online === value) return;
    this.online = value;
    this.reconcile();
  }
  private reconcile() {
    this.abort();
    if (!this.visible || !this.online) {
      for (const l of layers) this.remove(l);
    }
    this.publish();
    void this.refresh();
  }
  private runnable() {
    return (
      this.live &&
      this.visible &&
      this.online &&
      !!this.settings &&
      layers.some((l) => this.settings![l])
    );
  }
  private abort() {
    this.generation++;
    this.cycle?.abort();
    this.cycle = null;
    if (this.deadline) clearTimeout(this.deadline);
    this.deadline = undefined;
    for (const reservation of this.reservations.values()) reservation.release();
    this.reservations.clear();
  }
  private remove(layer: AviationLayer) {
    this.records.get(layer)?.drawing.dispose();
    this.records.get(layer)?.allocation.release();
    this.records.delete(layer);
    this.failed.delete(layer);
  }
  private signature(c: AviationCollection, layer: AviationLayer, now: number) {
    return activeFeatures(c, layer, now)
      .map(
        (f) =>
          f.id +
          ('station_id' in f.properties
            ? currentForecastGroups(f as AviationStation, now)
                .map((g) =>
                  (f as AviationStation).properties.forecast_groups.indexOf(g)
                )
                .join(',')
            : '')
      )
      .join('|');
  }
  private publish() {
    const now = this.utc();
    const next = {} as Record<AviationLayer, AviationLayerView>;
    for (const l of layers) {
      if (!this.settings?.[l]) {
        next[l] = { state: 'off' };
        continue;
      }
      let record = this.records.get(l);
      if (record && now >= record.product.expires_at_ms!) {
        this.remove(l);
        record = undefined;
      }
      if (record) {
        const data = {
          ...record.data,
          features: record.data.features.filter(
            (f) => now < f.properties.expires_at_ms
          ),
        };
        const signature = this.signature(data, l, now);
        if (signature !== record.signature) {
          try {
            const candidate = createBudgetedAviationDrawing(
              data,
              l,
              now,
              this.budget
            );
            if (
              candidate.bytes > record.product.payload!.gpu_bytes ||
              candidate.bytes +
                [...this.records.values()].reduce(
                  (sum, r) => sum + r.product.payload!.gpu_bytes,
                  0
                ) >
                limits[2]
            ) {
              candidate.dispose();
              throw Error('Replacement geometry budget');
            }
            record.drawing.dispose();
            record.drawing = candidate;
            record.signature = signature;
          } catch {
            this.remove(l);
            record = undefined;
            this.failed.add(l);
          }
        }
        if (record) {
          record.data = data;
          const featureStale = data.features.some(
            (f) =>
              'fresh_until_ms' in f.properties &&
              now >= f.properties.fresh_until_ms
          );
          next[l] = {
            state:
              record.failed ||
              record.product.state === 'stale' ||
              now >= record.product.fresh_until_ms! ||
              featureStale
                ? 'stale'
                : 'current',
            product: record.product,
            data,
            drawing: record.drawing,
          };
          continue;
        }
      }
      next[l] = {
        state: this.cycle && !this.failed.has(l) ? 'loading' : 'unavailable',
      };
    }
    this.view = { now, layers: next };
    for (const listener of this.listeners) listener();
  }
  private reserve(layer: AviationLayer, product: AviationProduct) {
    const amounts = usage(product);
    if (amounts[1] < amounts[0] * 4)
      throw Error('Underdeclared decoded reserve');
    const allocation = this.budget.reserve(weatherKey(`bulletin:${layer}`), {
      encoded: amounts[0],
      decoded: amounts[1],
      gpu: amounts[2],
    });
    this.reservations.set(layer, allocation);
    return allocation;
  }
  private async catalog(signal: AbortSignal) {
    const slot =
      this.budget.tryAcquire(signal) ?? (await this.budget.acquire(signal));
    try {
      return await withAbort(this.api.getCatalog(signal), signal);
    } finally {
      slot();
    }
  }
  async refresh() {
    if (!this.runnable() || this.cycle) return;
    const generation = this.generation,
      revision = this.settings!.revision,
      owner = new AbortController();
    this.cycle = owner;
    this.deadline = setTimeout(() => {
      owner.abort();
      if (this.cycle === owner) {
        this.generation++;
        for (const reservation of this.reservations.values())
          reservation.release();
        this.reservations.clear();
        this.cycle = null;
        for (const l of layers)
          if (this.settings?.[l]) {
            this.failed.add(l);
            const r = this.records.get(l);
            if (r) r.failed = true;
          }
        this.publish();
      }
    }, 45000);
    this.publish();
    const current = () =>
      this.runnable() &&
      this.generation === generation &&
      this.settings!.revision === revision &&
      !owner.signal.aborted;
    try {
      const catalog = await withAbort(this.catalog(owner.signal), owner.signal);
      if (!current() || catalog.settings_revision !== revision)
        throw Error('Obsolete weather catalog');
      this.anchor = {
        utc: Math.max(this.utc(), catalog.generated_at_ms),
        mono: performance.now(),
      };
      // At most the three independently enabled Phase 1 layers; radar has its own owner.
      await Promise.all(
        layers
          .filter((l) => this.settings![l])
          .map(async (l) => {
            const p = catalog.products.find(
              (p) =>
                p.layer_id === l &&
                p.product_type ===
                  (
                    {
                      metar: 'metar-speci',
                      taf: 'taf',
                      sigmet: 'international-sigmet',
                    } as const
                  )[l]
            );
            let allocation: Reservation | undefined,
              transferred = false;
            try {
              if (
                !p?.payload ||
                !['ready', 'stale'].includes(p.state) ||
                p.expires_at_ms === null ||
                this.utc() >= p.expires_at_ms
              )
                throw Error('Weather product unavailable');
              const previous = this.records.get(l);
              if (previous && previous.product.instance_id === p.instance_id) {
                previous.failed = false;
                return;
              }
              allocation = this.reserve(l, p);
              const data = await withAbort(
                fetchAviationPayload(
                  p,
                  l,
                  owner.signal,
                  this.fetcher,
                  this.budget
                ),
                owner.signal
              );
              if (!current()) return;
              if (
                data.retrieved_at_ms > this.utc() + 60000 ||
                (l === 'metar' &&
                  data.features.some(
                    (f) =>
                      'observed_at_ms' in f.properties &&
                      f.properties.observed_at_ms !== null &&
                      f.properties.observed_at_ms > this.utc() + 60000
                  ))
              )
                throw Error('Future weather observation');
              const drawing = createBudgetedAviationDrawing(
                data,
                l,
                this.utc(),
                this.budget
              );
              if (drawing.bytes > p.payload.gpu_bytes) {
                drawing.dispose();
                throw Error('Underdeclared native GPU reserve');
              }
              this.remove(l);
              this.records.set(l, {
                product: p,
                data,
                drawing,
                signature: this.signature(data, l, this.utc()),
                failed: false,
                allocation,
              });
              transferred = true;
              this.failed.delete(l);
            } catch {
              if (current()) {
                this.failed.add(l);
                const r = this.records.get(l);
                if (r) r.failed = true;
              }
            } finally {
              if (!transferred) allocation?.release();
              if (this.generation === generation) this.reservations.delete(l);
            }
          })
      );
    } catch {
      if (this.generation === generation) {
        for (const l of layers)
          if (this.settings?.[l]) {
            this.failed.add(l);
            const r = this.records.get(l);
            if (r) r.failed = true;
          }
      }
    } finally {
      if (this.cycle === owner) {
        this.cycle = null;
        if (this.deadline) clearTimeout(this.deadline);
        this.deadline = undefined;
        this.publish();
      }
    }
  }
  dispose() {
    this.live = false;
    this.abort();
    if (this.tickTimer) clearInterval(this.tickTimer);
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.tickTimer = undefined;
    this.pollTimer = undefined;
    for (const l of layers) this.remove(l);
    this.listeners.clear();
    this.view = emptyAviationView;
  }
}
