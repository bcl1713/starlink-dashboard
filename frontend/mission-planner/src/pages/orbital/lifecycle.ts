import { orbitalCatalogApi } from '@/services/orbital-catalog';
import type { OverviewLinkSettings } from '@/services/overview-link-settings';
import { OrbitalWorkerClient } from './worker-client';
import type {
  CatalogEnvelope,
  OrbitalDiagnostics,
  OrbitalEndpoints,
  OrbitalSnapshot,
  OrbitalRoute,
  OrbitalStatusKind,
} from './types';

type WorkerOwner = Pick<
  OrbitalWorkerClient,
  'start' | 'setEndpoints' | 'recycle' | 'dispose'
>;
interface Session {
  generation: number;
  id: string;
  abort: AbortController;
  expiry: number;
  renewing: boolean;
  polling: boolean;
}
export interface OrbitalTrafficState {
  previous: OrbitalSnapshot | null;
  current: OrbitalSnapshot | null;
  route: OrbitalRoute | null;
  spritesReady: boolean;
  status: {
    kind: OrbitalStatusKind;
    diagnostics: OrbitalDiagnostics | null;
    reason?: string | null;
  };
}
interface Options {
  api?: Pick<typeof orbitalCatalogApi, 'acquire' | 'release' | 'catalog'>;
  workerFactory?: (
    generation: number,
    snapshot: (s: OrbitalSnapshot) => void,
    error: (e: Error) => void
  ) => WorkerOwner;
  refreshSettings: () => Promise<OverviewLinkSettings | undefined>;
  clock?: () => number;
}
const inactive = (): OrbitalTrafficState => ({
  previous: null,
  current: null,
  route: null,
  spritesReady: false,
  status: { kind: 'off', diagnostics: null },
});

/** One mount owns every continuation, lease, timer, worker and retained snapshot. */
export class OrbitalLifecycle {
  private state = inactive();
  private listeners = new Set<() => void>();
  private api: NonNullable<Options['api']>;
  private factory: NonNullable<Options['workerFactory']>;
  private clock: () => number;
  private refresh: Options['refreshSettings'];
  private settings: OverviewLinkSettings | undefined;
  private endpoints: OrbitalEndpoints = { aircraft: null, pop: null };
  private visible = true;
  private closed = false;
  private failed = false;
  private generation = 0;
  private session: Session | null = null;
  private worker: WorkerOwner | null = null;
  private catalog: CatalogEnvelope | null = null;
  private timers = new Set<ReturnType<typeof setInterval>>();
  private expiryTimer: ReturnType<typeof setTimeout> | undefined;
  private lastResponse = 0;
  private watchdog: ReturnType<typeof setInterval> | undefined;
  constructor(options: Options) {
    this.api = options.api ?? orbitalCatalogApi;
    this.factory =
      options.workerFactory ?? ((g, s, e) => new OrbitalWorkerClient(g, s, e));
    this.clock = options.clock ?? Date.now;
    this.refresh = options.refreshSettings;
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  getState = () => this.state;
  private publish(state: OrbitalTrafficState) {
    this.state = state;
    for (const listener of this.listeners) listener();
  }
  private status(kind: OrbitalStatusKind, reason?: string | null) {
    this.publish({
      ...this.state,
      status: { kind, diagnostics: this.catalog, reason },
    });
  }
  private enabled() {
    return (
      this.settings?.orbital_traffic_enabled === true &&
      this.settings.starshield_link_enabled === true
    );
  }
  private valid(session: Session) {
    return (
      !this.closed &&
      !this.failed &&
      this.visible &&
      this.enabled() &&
      this.session === session
    );
  }
  mount() {
    this.closed = false;
  }
  update(
    settings: OverviewLinkSettings | undefined,
    endpoints: OrbitalEndpoints
  ) {
    this.settings = settings;
    this.endpoints = endpoints;
    if (settings?.orbital_traffic_enabled === false) this.failed = false;
    if (!this.enabled() || !this.visible || this.closed) {
      this.stop();
      return;
    }
    if (this.failed) {
      this.status('worker-failed');
      return;
    }
    if (this.session) this.worker?.setEndpoints(endpoints);
    else void this.activate();
  }
  setVisible(visible: boolean) {
    if (this.visible === visible) return;
    this.visible = visible;
    if (!visible) {
      this.stop();
      return;
    }
    if (this.failed) {
      this.status('worker-failed');
      return;
    }
    if (!this.enabled() || this.closed) return;
    const generation = this.generation;
    void this.refresh()
      .then((settings) => {
        if (this.closed || !this.visible || this.generation !== generation)
          return;
        this.update(settings, this.endpoints);
      })
      .catch(() => {
        if (!this.closed && this.visible && this.generation === generation)
          this.update(this.settings, this.endpoints);
      });
  }
  private release(id: string) {
    void this.api.release(id).catch(() => {});
  }
  private async activate() {
    const session: Session = {
      generation: ++this.generation,
      id: `orbital-${crypto.randomUUID()}`,
      abort: new AbortController(),
      expiry: 0,
      renewing: false,
      polling: false,
    };
    this.session = session;
    this.status('loading');
    this.interval(() => void this.renew(session), 30000);
    this.interval(() => void this.poll(session), 60000);
    await this.renew(session);
  }
  private interval(callback: () => void, period: number) {
    const timer = setInterval(callback, period);
    this.timers.add(timer);
  }
  private async renew(session: Session) {
    if (!this.valid(session) || session.renewing) return;
    session.renewing = true;
    const wasExpired = session.expiry <= this.clock();
    try {
      const lease = await this.api.acquire(session.id, session.abort.signal);
      if (!this.valid(session)) {
        this.release(session.id);
        return;
      }
      const expiry = Date.parse(lease.expires_at);
      if (!Number.isFinite(expiry) || expiry <= this.clock())
        throw new Error('Expired orbital lease');
      session.expiry = expiry;
      clearTimeout(this.expiryTimer);
      this.expiryTimer = setTimeout(() => {
        if (this.valid(session) && this.clock() >= session.expiry) {
          this.stopWorker();
          this.status('loading', 'Viewer lease expired');
        }
      }, session.expiry - this.clock());
      if (wasExpired) void this.poll(session);
    } catch {
      if (this.valid(session)) {
        this.status('loading', 'Viewer lease unavailable');
        if (session.expiry <= this.clock()) this.stopWorker();
      }
    } finally {
      session.renewing = false;
    }
  }
  private async poll(session: Session) {
    if (
      !this.valid(session) ||
      session.expiry <= this.clock() ||
      session.polling
    )
      return;
    session.polling = true;
    try {
      const catalog = await this.api.catalog(session.id, session.abort.signal);
      if (!this.valid(session) || session.expiry <= this.clock()) return;
      this.catalog = catalog;
      if (!catalog.objects.length || !catalog.eligible_count) {
        this.stopWorker();
        this.status(catalog.suspended ? 'provider-suspended' : catalog.status);
        return;
      }
      if (this.worker) {
        if (
          this.state.current?.catalogGeneration !== catalog.generation &&
          this.installedGeneration !== catalog.generation
        ) {
          this.clearSnapshots();
          this.worker.start(catalog);
          this.installedGeneration = catalog.generation;
        }
        return;
      }
      try {
        const worker = this.factory(
          session.generation,
          (snapshot) => this.receive(session, worker, snapshot),
          () => this.fail(session)
        );
        this.worker = worker;
        this.lastResponse = this.clock();
        this.installedGeneration = catalog.generation;
        worker.start(catalog);
        worker.setEndpoints(this.endpoints);
        this.watchdog = setInterval(() => {
          if (
            this.valid(session) &&
            this.worker === worker &&
            this.clock() - this.lastResponse >= 5000
          )
            this.fail(session);
        }, 1000);
      } catch {
        this.fail(session);
      }
    } catch {
      if (this.valid(session))
        this.status('loading', 'Catalog unavailable; production arc retained');
    } finally {
      session.polling = false;
    }
  }
  private installedGeneration = '';
  private receive(
    session: Session,
    worker: WorkerOwner,
    snapshot: OrbitalSnapshot
  ) {
    if (
      !this.valid(session) ||
      this.worker !== worker ||
      session.expiry <= this.clock()
    )
      return;
    this.lastResponse = this.clock();
    if (!snapshot.valid.some(Boolean)) {
      this.stopWorker();
      this.status('expired');
      return;
    }
    const oldPrevious = this.state.previous,
      oldCurrent = this.state.current;
    const previous =
      oldCurrent?.catalogGeneration === snapshot.catalogGeneration
        ? oldCurrent
        : null;
    this.publish({
      previous,
      current: snapshot,
      route: snapshot.route,
      spritesReady: true,
      status: {
        kind: this.catalog?.suspended
          ? 'provider-suspended'
          : snapshot.route
            ? 'ready'
            : 'disconnected',
        diagnostics: this.catalog,
        reason: snapshot.fallbackReason,
      },
    });
    // Renderers copy physical snapshots into their owned Float32 GPU attributes;
    // only snapshots removed from the published pair are transferred back.
    if (oldPrevious) worker.recycle(oldPrevious);
    if (oldCurrent && oldCurrent !== previous) worker.recycle(oldCurrent);
  }
  private fail(session: Session) {
    if (!this.valid(session)) return;
    this.failed = true;
    this.stop();
    this.status('worker-failed', 'Worker failed; retry with orbital off/on');
  }
  private clearSnapshots() {
    if (this.state.previous) this.worker?.recycle(this.state.previous);
    if (this.state.current) this.worker?.recycle(this.state.current);
    this.publish({
      ...this.state,
      previous: null,
      current: null,
      route: null,
      spritesReady: false,
    });
  }
  private stopWorker() {
    clearInterval(this.watchdog);
    this.watchdog = undefined;
    this.clearSnapshots();
    this.worker?.dispose();
    this.worker = null;
    this.installedGeneration = '';
  }
  private stop() {
    if (
      !this.session &&
      !this.worker &&
      !this.state.current &&
      !this.state.previous &&
      this.state.status.kind === 'off'
    ) {
      this.generation++;
      return;
    }
    const session = this.session;
    this.session = null;
    this.generation++;
    session?.abort.abort();
    for (const timer of this.timers) clearInterval(timer);
    this.timers.clear();
    clearTimeout(this.expiryTimer);
    this.expiryTimer = undefined;
    this.stopWorker();
    if (session) this.release(session.id);
    this.publish(inactive());
  }
  dispose() {
    this.closed = true;
    this.stop();
  }
}
