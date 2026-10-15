import type { ReadyWeatherManifest } from '@/services/overview-weather';
import { WeatherWork } from './weather-work';
import { abortable, type BrowserWeatherClock } from './weather-state';

export type WeatherAtlasPair = {
  radar: HTMLCanvasElement;
  coverage: HTMLCanvasElement;
  frameTimeMs: number;
  coverageToken: number;
  coverageExpiresAtMs: number;
  dispose(): void;
};
type Coverage = {
  canvas: HTMLCanvasElement;
  token: number;
  expires: number;
  refs: number;
  product: string;
  release: () => void;
};
function canvas() {
  const value = document.createElement('canvas');
  value.width = value.height = 2048;
  return value;
}
function clear(value: HTMLCanvasElement) {
  value.width = value.height = 0;
}
function release(entry: Coverage) {
  if (--entry.refs === 0) {
    clear(entry.canvas);
    entry.release();
  }
}

export class WeatherAtlasLoader {
  private coverage: Coverage | null = null;
  private currentLoad: AbortController | null = null;
  private fetcher: typeof fetch;
  private clock: BrowserWeatherClock;
  readonly work: WeatherWork;
  constructor(
    fetcher: typeof fetch,
    clock: BrowserWeatherClock,
    work = new WeatherWork()
  ) {
    // Browser fetch is a Window capability; invoking it as a loader method
    // supplies an invalid receiver. Preserve its global receiver explicitly.
    this.work = work;
    this.fetcher = fetcher.bind(globalThis);
    this.clock = clock;
  }

  private async tile(
    template: string,
    x: number,
    y: number,
    target: HTMLCanvasElement,
    signal: AbortSignal
  ) {
    return this.work.run('coarse', signal, async () => {
      signal.throwIfAborted();
      const url = template
        .replace('{z}', '2')
        .replace('{x}', String(x))
        .replace('{y}', String(y));
      const response = await this.fetcher(url, {
        signal,
        credentials: 'same-origin',
      });
      if (
        !response.ok ||
        response.headers.get('content-type')?.split(';')[0] !== 'image/png'
      )
        throw new Error('Invalid weather image');
      const blob = await response.blob();
      signal.throwIfAborted();
      if (blob.size > 2097152) throw new Error('Oversized weather image');
      const release = this.work.reserveDecoded(512 * 512 * 4);
      let bitmap: ImageBitmap | undefined;
      try {
        bitmap = await createImageBitmap(blob);
        signal.throwIfAborted();
        if (bitmap.width !== 512 || bitmap.height !== 512)
          throw new Error('Invalid weather dimensions');
        const context = target.getContext('2d');
        if (!context) throw new Error('Weather canvas unavailable');
        context.drawImage(bitmap, x * 512, y * 512);
      } finally {
        bitmap?.close();
        release();
      }
    });
  }

  async load(
    manifest: ReadyWeatherManifest,
    signal: AbortSignal
  ): Promise<WeatherAtlasPair> {
    this.currentLoad?.abort();
    const abort = new AbortController();
    this.currentLoad = abort;
    const stop = () => abort.abort(signal.reason);
    signal.addEventListener('abort', stop, { once: true });
    if (signal.aborted) stop();
    const started = this.clock.nowMono();
    const deadline = setTimeout(
      () =>
        abort.abort(new DOMException('Weather load timed out', 'TimeoutError')),
      45000
    );
    let releaseRadar: (() => void) | undefined,
      radar: HTMLCanvasElement | undefined;
    let coverage: Coverage | undefined;
    let transferred = false;
    try {
      releaseRadar = this.work.reserveDecoded(2048 * 2048 * 4);
      radar = canvas();
      const cached =
        this.coverage?.product === manifest.product_id &&
        this.coverage.token === manifest.coverage_token &&
        this.coverage.expires === manifest.coverage_expires_at_ms
          ? this.coverage
          : null;
      coverage = cached ?? {
        release: this.work.reserveDecoded(2048 * 2048 * 4),
        product: manifest.product_id,
        canvas: canvas(),
        token: manifest.coverage_token,
        expires: manifest.coverage_expires_at_ms,
        refs: 1,
      };
      if (cached) coverage.refs++;
      const jobs: Promise<void>[] = [];
      for (let y = 0; y < 4; y++)
        for (let x = 0; x < 4; x++) {
          jobs.push(
            this.tile(manifest.radar_tile_template, x, y, radar, abort.signal)
          );
          if (!cached)
            jobs.push(
              this.tile(
                manifest.coverage_tile_template,
                x,
                y,
                coverage.canvas,
                abort.signal
              )
            );
        }
      await abortable(Promise.all(jobs), abort.signal);
      abort.signal.throwIfAborted();
      const utc = manifest.generated_at_ms + this.clock.nowMono() - started;
      if (
        utc >= manifest.coverage_expires_at_ms ||
        utc - manifest.frame_time_ms >= 3600000
      )
        throw new Error('Weather expired during loading');
      if (!cached) {
        if (this.coverage) release(this.coverage);
        this.coverage = coverage;
        coverage.refs++; // cache owns one lease, returned pair owns the other
      }
      transferred = true;
      const heldRadar = radar,
        heldCoverage = coverage,
        freeRadar = releaseRadar;
      let disposed = false;
      return {
        radar,
        coverage: coverage.canvas,
        frameTimeMs: manifest.frame_time_ms,
        coverageToken: manifest.coverage_token,
        coverageExpiresAtMs: manifest.coverage_expires_at_ms,
        dispose: () => {
          if (!disposed) {
            disposed = true;
            clear(heldRadar);
            freeRadar();
            release(heldCoverage);
          }
        },
      };
    } finally {
      clearTimeout(deadline);
      signal.removeEventListener('abort', stop);
      if (this.currentLoad === abort) this.currentLoad = null;
      if (!transferred) {
        abort.abort();
        if (radar) clear(radar);
        releaseRadar?.();
        if (coverage) release(coverage);
      }
    }
  }

  dispose() {
    this.currentLoad?.abort();
    this.currentLoad = null;
    if (this.coverage) release(this.coverage);
    this.coverage = null;
  }
}
