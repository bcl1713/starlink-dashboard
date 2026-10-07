import type * as THREE from 'three';
import {
  parseAviationSettings,
  type AviationSettings,
  type ResolvedAviationSettings,
  type AviationCatalog,
  type AviationProduct,
  type GfsSelection,
} from '@/services/aviation-weather';
import { fetchGrid, type GridLease } from '@/services/aviation-grid';
import {
  abortable,
  optionalWeatherBudget,
  type WeatherBudget,
} from './weather-budget';
export type GfsFlags = { winds: boolean; temperature: boolean };
export type GfsDrawing = {
  object: THREE.Object3D;
  bytes: { decoded: number; gpu: number };
  dispose(): void;
};
export type GfsProducts = {
  winds?: AviationProduct;
  temperature?: AviationProduct;
};
export type GfsView = {
  now: number;
  state: 'off' | 'loading' | 'current' | 'stale' | 'unavailable';
  products: GfsProducts;
  selection?: GfsSelection;
  drawing?: GfsDrawing;
  grid?: GridLease;
};
export const emptyGfsView: GfsView = { now: 0, state: 'off', products: {} };
type Options = {
  budget?: WeatherBudget;
  load?: typeof fetchGrid;
  draw?: (
    lease: GridLease,
    flags: GfsFlags,
    budget: WeatherBudget
  ) => GfsDrawing;
};
type Record = {
  products: GfsProducts;
  leases: GridLease[];
  drawing?: GfsDrawing;
  failed: boolean;
};
const names = ['winds', 'temperature'] as const;
export class GfsController {
  private settings?: ResolvedAviationSettings;
  private live = false;
  private visible = true;
  private online = true;
  private generation = 0;
  private cycle?: AbortController;
  private deadline?: ReturnType<typeof setTimeout>;
  private tick?: ReturnType<typeof setInterval>;
  private poll?: ReturnType<typeof setInterval>;
  private anchor?: { utc: number; mono: number };
  private record?: Record;
  private listeners = new Set<() => void>();
  private view = emptyGfsView;
  private budget: WeatherBudget;
  private load: typeof fetchGrid;
  private api: { getCatalog(signal?: AbortSignal): Promise<AviationCatalog> };
  private options: Options;
  constructor(
    api: { getCatalog(signal?: AbortSignal): Promise<AviationCatalog> },
    options: Options = {}
  ) {
    this.api = api;
    this.options = options;
    this.budget = options.budget ?? optionalWeatherBudget;
    this.load = options.load ?? fetchGrid;
  }
  getSnapshot = () => this.view;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private utc() {
    return this.anchor
      ? this.anchor.utc + Math.max(0, performance.now() - this.anchor.mono)
      : 0;
  }
  private enabled() {
    return (
      !!this.settings && (this.settings.winds || this.settings.temperature)
    );
  }
  private runnable() {
    return this.live && this.visible && this.online && this.enabled();
  }
  start() {
    if (this.live) return;
    this.live = true;
    this.tick = setInterval(() => this.publish(), 5000);
    this.poll = setInterval(() => {
      void this.refresh();
    }, 60000);
    this.publish();
    void this.refresh();
  }
  stop() {
    this.live = false;
    this.abort();
    this.remove();
    if (this.tick) clearInterval(this.tick);
    if (this.poll) clearInterval(this.poll);
    this.tick = this.poll = undefined;
    this.view = { ...emptyGfsView, now: this.utc() };
    this.notify();
    this.listeners.clear();
  }
  setSettings(next: AviationSettings) {
    const settings = parseAviationSettings(next);
    if (this.settings && settings.revision <= this.settings.revision) return;
    const incompatible =
      !this.settings ||
      JSON.stringify(settings.gfs_selection) !==
        JSON.stringify(this.settings.gfs_selection) ||
      settings.winds !== this.settings.winds ||
      settings.temperature !== this.settings.temperature;
    this.settings = settings;
    this.abort();
    if (incompatible) this.remove();
    this.publish();
    void this.refresh();
  }
  setVisible(visible: boolean) {
    if (this.visible === visible) return;
    this.visible = visible;
    this.reconcile();
  }
  setOnline(online: boolean) {
    if (this.online === online) return;
    this.online = online;
    this.reconcile();
  }
  private reconcile() {
    this.abort();
    if (!this.visible || !this.online) this.remove();
    this.publish();
    void this.refresh();
  }
  private abort() {
    this.generation++;
    this.cycle?.abort();
    this.cycle = undefined;
    if (this.deadline) clearTimeout(this.deadline);
    this.deadline = undefined;
  }
  private remove() {
    this.record?.drawing?.dispose();
    this.record?.leases.forEach((l) => l.release());
    this.record = undefined;
  }
  private notify() {
    for (const listener of this.listeners) listener();
  }
  private publish() {
    const now = this.utc();
    if (
      this.record &&
      Object.values(this.record.products).some(
        (p) =>
          now >= p.expires_at_ms! ||
          now + this.settings!.gfs_selection.horizon_hours * 3600000 >
            p.run_at_ms! + 48 * 3600000
      )
    )
      this.remove();
    const record = this.record;
    this.view = {
      now,
      selection: this.settings?.gfs_selection,
      state: !this.enabled()
        ? 'off'
        : record
          ? record.failed ||
            Object.values(record.products).some(
              (p) => p.state === 'stale' || now >= p.fresh_until_ms!
            )
            ? 'stale'
            : 'current'
          : this.cycle
            ? 'loading'
            : 'unavailable',
      products: record?.products ?? {},
      drawing: record?.drawing,
      grid: record?.leases[0],
    };
    this.notify();
  }
  private matches(product: AviationProduct) {
    const selected = this.settings!.gfs_selection.vertical,
      vertical = product.vertical;
    return (
      selected.kind === vertical.kind &&
      (selected.kind === 'pressure'
        ? vertical.kind === 'pressure' &&
          selected.pressure_pa === vertical.pressure_pa
        : vertical.kind === 'flight-level' &&
          selected.flight_level === vertical.flight_level)
    );
  }
  async refresh() {
    if (!this.runnable() || this.cycle) return;
    const generation = this.generation,
      revision = this.settings!.revision,
      owner = new AbortController(),
      started = performance.now();
    let expiry = Infinity;
    this.cycle = owner;
    this.deadline = setTimeout(
      () => owner.abort(new DOMException('Weather deadline', 'TimeoutError')),
      45000
    );
    this.publish();
    const current = () => {
      if (performance.now() >= started + 45000 || this.utc() >= expiry)
        owner.abort(new DOMException('Weather deadline', 'TimeoutError'));
      return (
        this.runnable() &&
        this.generation === generation &&
        this.settings!.revision === revision &&
        !owner.signal.aborted
      );
    };
    let slot: (() => void) | undefined;
    const leases: GridLease[] = [];
    let candidate: GfsDrawing | undefined;
    try {
      slot = await this.budget.acquire(owner.signal);
      if (!current()) throw Error('Expired model generation');
      const catalog = await abortable(
        this.api.getCatalog(owner.signal),
        owner.signal
      );
      slot();
      slot = undefined;
      if (!current() || catalog.settings_revision !== revision)
        throw Error('Obsolete model catalog');
      this.anchor = {
        utc: Math.max(this.utc(), catalog.generated_at_ms),
        mono: performance.now(),
      };
      const products: GfsProducts = {};
      for (const name of names.filter((n) => this.settings![n])) {
        const product = catalog.products.find(
          (p) =>
            p.layer_id === `gfs-${name}` &&
            p.product_type === (name === 'winds' ? 'winds' : 'air-temperature')
        );
        if (
          !product?.payload ||
          !['ready', 'stale'].includes(product.state) ||
          !this.matches(product) ||
          product.expires_at_ms === null ||
          this.utc() >= product.expires_at_ms
        ) {
          this.remove();
          throw Error('Model unavailable');
        }
        products[name] = product;
      }
      clearTimeout(this.deadline);
      expiry = Math.min(
        ...Object.values(products).map((p) =>
          Math.min(
            p.expires_at_ms!,
            p.run_at_ms! +
              48 * 3600000 -
              this.settings!.gfs_selection.horizon_hours * 3600000
          )
        )
      );
      if (!current()) throw Error('Expired model target');
      this.deadline = setTimeout(
        () => owner.abort(new DOMException('Model expired', 'TimeoutError')),
        Math.max(
          0,
          Math.min(45000 - (performance.now() - started), expiry - this.utc())
        )
      );
      if (
        this.record &&
        names.every(
          (n) =>
            this.record!.products[n]?.instance_id === products[n]?.instance_id
        )
      ) {
        this.record.products = products;
        this.record.failed = false;
        return;
      }
      for (const product of Object.values(products)) {
        const pending = this.load(product, owner.signal, this.budget).then(
          (lease) => {
            if (!current()) {
              lease.release();
              throw Error('Superseded model grid');
            }
            return lease;
          }
        );
        leases.push(await abortable(pending, owner.signal));
      }
      if (
        !current() ||
        Object.values(products).some((p) => this.utc() >= p.expires_at_ms!)
      )
        throw Error('Expired model replacement');
      const first = leases[0];
      if (
        leases.some(
          (l) =>
            JSON.stringify(l.descriptor.vertical) !==
              JSON.stringify(first.descriptor.vertical) ||
            l.descriptor.run_at_ms !== first.descriptor.run_at_ms ||
            l.descriptor.valid_at_ms !== first.descriptor.valid_at_ms ||
            ['u', 'v', 't', 'mask'].some(
              (n) =>
                l.descriptor.buffers[n as 'u'].sha256 !==
                first.descriptor.buffers[n as 'u'].sha256
            )
        )
      )
        throw Error('Incoherent model siblings');
      candidate = this.options.draw?.(
        first,
        {
          winds: this.settings!.winds,
          temperature: this.settings!.temperature,
        },
        this.budget
      );
      if (
        !current() ||
        Object.values(products).some((p) => this.utc() >= p.expires_at_ms!)
      )
        throw Error('Expired drawing');
      this.remove();
      this.record = {
        products,
        leases: leases.splice(0),
        drawing: candidate,
        failed: false,
      };
      candidate = undefined;
    } catch {
      if (this.generation === generation && this.record)
        this.record.failed = true;
    } finally {
      candidate?.dispose();
      leases.forEach((l) => l.release());
      slot?.();
      if (this.cycle === owner) {
        this.cycle = undefined;
        if (this.deadline) clearTimeout(this.deadline);
        this.deadline = undefined;
        this.publish();
      }
    }
  }
}
