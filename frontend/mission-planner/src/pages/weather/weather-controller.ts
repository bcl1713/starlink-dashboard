import type {
  overviewWeatherApi,
  WeatherSettingsObservation,
  ReadyWeatherManifest,
} from '@/services/overview-weather';
import { WeatherDetailOwner, manifestResourceIdentity } from './weather-detail';
import type { DetailDemand } from './weather-detail-selection';
import { WeatherAtlasLoader, type WeatherAtlasPair } from './weather-atlas';
import {
  abortable,
  emptyWeatherView,
  frameState,
  type BrowserWeatherClock,
  type WeatherLayerView,
} from './weather-state';

export class WeatherController {
  private observation: WeatherSettingsObservation | undefined;
  private configured = false;
  private documentVisible = true;
  private active = false;
  private minimumFresh = -Infinity;
  private atlas: WeatherAtlasPair | null = null;
  private displayed: ReadyWeatherManifest | null = null;
  private displayGeneration = 0;
  readonly detail: WeatherDetailOwner;
  private unsubscribeDetail: () => void;
  private anchor: { utc: number; mono: number } | null = null;
  private failed = false;
  private closed = false;
  private generation = 0;
  private request: AbortController | null = null;
  private pendingCoverageExpiry: number | null = null;
  private nextCheck = Infinity;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private listeners = new Set<() => void>();
  private view: WeatherLayerView = emptyWeatherView;
  private api: typeof overviewWeatherApi;
  private loader: WeatherAtlasLoader;
  private clock: BrowserWeatherClock;
  constructor(
    api: typeof overviewWeatherApi,
    loader: WeatherAtlasLoader,
    clock: BrowserWeatherClock
  ) {
    this.api = api;
    this.loader = loader;
    this.clock = clock;
    this.detail = new WeatherDetailOwner(fetch, clock, loader.work);
    this.unsubscribeDetail = this.detail.subscribe(() => this.emit());
  }

  snapshot = () => this.view;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private utc() {
    return this.anchor
      ? this.anchor.utc + this.clock.nowMono() - this.anchor.mono
      : 0;
  }
  private cancelPending() {
    this.generation++;
    this.request?.abort();
    this.request = null;
    this.pendingCoverageExpiry = null;
  }
  private discardAtlas() {
    this.atlas?.dispose();
    this.atlas = null;
    this.displayed = null;
    this.displayGeneration++;
    this.detail.setContext(null);
  }

  setSettings(observation: WeatherSettingsObservation | undefined) {
    if (this.closed) return;
    if (
      observation &&
      this.observation &&
      (observation.settings.revision < this.observation.settings.revision ||
        (observation.settings.revision === this.observation.settings.revision &&
          observation.settings.enabled !== this.observation.settings.enabled))
    )
      return;
    const changed =
      observation?.settings.revision !== this.observation?.settings.revision;
    this.observation = observation;
    if (observation) this.configured = observation.settings.enabled;
    if (changed || !this.configured) {
      this.cancelPending();
      this.discardAtlas();
      this.loader.dispose();
      this.active = false;
      this.failed = false;
    }
    this.updateActivity();
  }
  setVisible(visible: boolean) {
    if (visible === this.documentVisible || this.closed) return;
    this.documentVisible = visible;
    if (visible) this.minimumFresh = this.clock.nowMono();
    else {
      this.cancelPending();
      this.active = false;
    }
    this.updateActivity();
  }
  setDetailDemand = (demand: DetailDemand) => {
    if (this.active) this.detail.setDemand(demand);
  };
  disconnect() {
    this.minimumFresh = Infinity;
    this.cancelPending();
    this.active = false;
    this.emit();
    this.schedule();
  }
  reconnect() {
    if (this.closed || !this.documentVisible) return;
    this.minimumFresh = this.clock.nowMono();
    this.cancelPending();
    this.active = false;
    this.updateActivity();
  }
  private updateActivity() {
    const observation = this.observation;
    const canRun =
      !this.closed &&
      this.documentVisible &&
      this.configured &&
      !!observation &&
      observation.receivedAtMono >= this.minimumFresh &&
      this.clock.nowMono() - observation.receivedAtMono < 15000;
    if (!canRun) {
      this.cancelPending();
      this.active = false;
    } else if (!this.active) {
      this.active = true;
      this.startCheck();
    }
    this.emit();
    this.schedule();
  }

  private startCheck() {
    if (!this.active || this.request) return;
    const abort = new AbortController();
    this.request = abort;
    const generation = ++this.generation;
    const revision = this.observation!.settings.revision;
    this.nextCheck = this.clock.nowMono() + 300000;
    const timer = setTimeout(
      () =>
        abort.abort(
          new DOMException('Weather check timed out', 'TimeoutError')
        ),
      45000
    );
    this.emit();
    void this.perform(abort, generation, revision).finally(() => {
      clearTimeout(timer);
      if (this.request === abort) {
        this.request = null;
        this.pendingCoverageExpiry = null;
        this.emit();
        this.schedule();
      }
    });
  }
  private async perform(
    abort: AbortController,
    generation: number,
    revision: number
  ) {
    const current = () =>
      !this.closed && this.active && generation === this.generation;
    try {
      const manifest = await abortable(
        this.api.getFrame(abort.signal),
        abort.signal
      );
      if (!current()) return;
      if (manifest.settings_revision !== revision || manifest.state !== 'ready')
        throw new Error('Weather unavailable');
      // Start the next interval after validation reaches the browser, so the
      // provider's 300-second metadata cache has expired on the next read.
      this.nextCheck = this.clock.nowMono() + 300000;
      this.anchor = {
        utc: Math.max(this.utc(), manifest.generated_at_ms),
        mono: this.clock.nowMono(),
      };
      if (
        this.utc() >= manifest.coverage_expires_at_ms ||
        this.utc() - manifest.frame_time_ms >= 3600000
      )
        throw new Error('Weather expired');
      if (
        this.atlas &&
        this.displayed &&
        manifestResourceIdentity(this.displayed) ===
          manifestResourceIdentity(manifest)
      ) {
        this.displayed = manifest;
        this.failed = false;
        return;
      }
      this.pendingCoverageExpiry = manifest.coverage_expires_at_ms;
      this.schedule();
      const decoded = this.loader
        .load(manifest as ReadyWeatherManifest, abort.signal)
        .then((pair) => {
          if (!current() || abort.signal.aborted) {
            pair.dispose();
            throw new DOMException('Aborted', 'AbortError');
          }
          return pair;
        });
      const pair = await abortable(decoded, abort.signal);
      if (
        this.utc() >= pair.coverageExpiresAtMs ||
        this.utc() - pair.frameTimeMs >= 3600000
      ) {
        pair.dispose();
        throw new Error('Weather expired');
      }
      this.discardAtlas();
      this.atlas = pair;
      this.displayed = manifest;
      this.failed = false;
    } catch {
      if (current()) this.failed = true;
    }
  }
  private expire() {
    const utc = this.utc();
    const coverageExpired =
      (this.atlas && utc >= this.atlas.coverageExpiresAtMs) ||
      (this.pendingCoverageExpiry !== null &&
        utc >= this.pendingCoverageExpiry);
    if (
      this.atlas &&
      (coverageExpired ||
        frameState(this.atlas.frameTimeMs, utc, false) === 'unavailable')
    )
      this.discardAtlas();
    if (coverageExpired) {
      this.cancelPending();
      this.loader.dispose();
      this.failed = true;
      this.startCheck();
    }
  }
  private emit() {
    const atlas =
      this.active &&
      this.atlas &&
      this.utc() < this.atlas.coverageExpiresAtMs &&
      frameState(this.atlas.frameTimeMs, this.utc(), this.failed) !==
        'unavailable'
        ? this.atlas
        : null;
    const detailContext =
      atlas && this.displayed
        ? {
            generation: this.displayGeneration,
            settingsRevision: this.displayed.settings_revision,
            manifest: this.displayed,
          }
        : null;
    this.detail.setContext(detailContext);
    this.view = {
      detailContext,
      detailPairs: this.detail.snapshot(),
      work: this.loader.work,
      onDemand: this.setDetailDemand,
      configuredEnabled: this.configured,
      visible: !!atlas,
      atlas,
      state: !this.configured
        ? 'off'
        : !this.active
          ? 'unavailable'
          : atlas
            ? frameState(atlas.frameTimeMs, this.utc(), this.failed)
            : this.request
              ? 'loading'
              : 'unavailable',
      frameTimeMs: atlas?.frameTimeMs ?? null,
      ageMs: atlas ? Math.max(0, this.utc() - atlas.frameTimeMs) : null,
    };
    this.listeners.forEach((listener) => listener());
  }
  private schedule() {
    clearTimeout(this.timer);
    this.timer = undefined;
    if (!this.active || this.closed || !this.observation) return;
    const now = this.clock.nowMono();
    const waits = [
      1000,
      this.nextCheck - now,
      this.observation.receivedAtMono + 15000 - now,
    ];
    if (this.atlas)
      waits.push(
        this.atlas.coverageExpiresAtMs - this.utc(),
        this.atlas.frameTimeMs + 3600000 - this.utc()
      );
    if (this.pendingCoverageExpiry !== null)
      waits.push(this.pendingCoverageExpiry - this.utc());
    this.timer = setTimeout(
      () => {
        if (
          !this.observation ||
          this.clock.nowMono() - this.observation.receivedAtMono >= 15000
        ) {
          this.updateActivity();
          return;
        }
        this.expire();
        if (this.clock.nowMono() >= this.nextCheck) this.startCheck();
        this.emit();
        this.schedule();
      },
      Math.max(1, Math.min(...waits))
    );
  }
  dispose() {
    this.closed = true;
    this.active = false;
    this.cancelPending();
    this.unsubscribeDetail();
    this.discardAtlas();
    this.detail.dispose();
    this.loader.dispose();
    clearTimeout(this.timer);
    this.listeners.clear();
    this.view = emptyWeatherView;
  }
}
