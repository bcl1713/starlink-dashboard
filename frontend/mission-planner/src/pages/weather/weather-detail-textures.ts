import {
  CanvasTexture,
  ClampToEdgeWrapping,
  LinearFilter,
  NoColorSpace,
  SRGBColorSpace,
  Vector4,
} from 'three';
import {
  detailContextIdentity,
  type DetailContext,
  type DetailPair,
} from './weather-detail';
import type { WeatherWork } from './weather-work';
export type DetailTextureSet = {
  radar: CanvasTexture;
  coverage: CanvasTexture;
  bounds: Vector4[];
  rects: Vector4[];
  valid: Float32Array;
  fades: Float32Array;
};
function texture(canvas: HTMLCanvasElement, radar: boolean) {
  const value = new CanvasTexture(canvas);
  value.colorSpace = radar ? SRGBColorSpace : NoColorSpace;
  value.flipY = false;
  value.generateMipmaps = false;
  value.minFilter = value.magFilter = LinearFilter;
  value.wrapS = value.wrapT = ClampToEdgeWrapping;
  return value;
}
/** Resample into 510px interior and duplicate all edge/corner pixels into gutters. */
function paint(canvas: HTMLCanvasElement, bitmap: ImageBitmap, slot: number) {
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Weather detail canvas unavailable');
  const x = (slot % 4) * 512,
    y = Math.floor(slot / 4) * 512;
  ctx.clearRect(x, y, 512, 512);
  ctx.drawImage(bitmap, 0, 0, 512, 512, x + 1, y + 1, 510, 510);
  for (const dx of [0, 511])
    ctx.drawImage(
      canvas,
      x + (dx === 0 ? 1 : 510),
      y + 1,
      1,
      510,
      x + dx,
      y + 1,
      1,
      510
    );
  for (const dy of [0, 511])
    ctx.drawImage(
      canvas,
      x + 1,
      y + (dy === 0 ? 1 : 510),
      510,
      1,
      x + 1,
      y + dy,
      510,
      1
    );
  for (const dx of [0, 511])
    for (const dy of [0, 511])
      ctx.drawImage(
        canvas,
        x + (dx === 0 ? 1 : 510),
        y + (dy === 0 ? 1 : 510),
        1,
        1,
        x + dx,
        y + dy,
        1,
        1
      );
}
export class WeatherDetailTextureOwner {
  private set: DetailTextureSet | null = null;
  private identity = '';
  private pairs: (DetailPair | null)[] = Array(8).fill(null);
  private starts = new Float64Array(8);
  private release: (() => void) | undefined;
  private work: WeatherWork;
  constructor(work: WeatherWork) {
    this.work = work;
  }
  replace(
    context: DetailContext | null,
    pairs: readonly DetailPair[],
    nowMono: number
  ): DetailTextureSet | null {
    if (
      !context ||
      context.manifest.tile_schema !== 'xyz-rgba-pair-v1' ||
      context.manifest.coverage_encoding !== 'absence-rgba-v1' ||
      context.manifest.tile_size !== 512
    ) {
      this.dispose();
      return null;
    }
    const identity = detailContextIdentity(context);
    if (this.identity !== identity) this.dispose();
    const validPairs = pairs
      .filter(
        (pair) =>
          detailContextIdentity(pair.context) === identity &&
          pair.radar.width === 512 &&
          pair.radar.height === 512 &&
          pair.coverage.width === 512 &&
          pair.coverage.height === 512
      )
      .slice(0, 8);
    if (!validPairs.length) {
      this.dispose();
      return null;
    }
    if (!this.set) {
      this.release = this.work.reserveDecoded(16 * 1024 * 1024);
      const radar = document.createElement('canvas'),
        coverage = document.createElement('canvas');
      radar.width = coverage.width = 2048;
      radar.height = coverage.height = 1024;
      this.set = {
        radar: texture(radar, true),
        coverage: texture(coverage, false),
        bounds: Array.from({ length: 8 }, () => new Vector4()),
        rects: Array.from({ length: 8 }, () => new Vector4()),
        valid: new Float32Array(8),
        fades: new Float32Array(8),
      };
      this.identity = identity;
    }
    const set = this.set;
    for (let slot = 0; slot < 8; slot++)
      if (this.pairs[slot] && !validPairs.includes(this.pairs[slot]!)) {
        set.valid[slot] = 0;
        this.pairs[slot] = null;
      }
    for (const pair of validPairs) {
      if (this.pairs.includes(pair)) continue;
      const slot = this.pairs.indexOf(null);
      if (slot < 0) break;
      set.valid[slot] = 0;
      try {
        paint(set.radar.image, pair.radar, slot);
        paint(set.coverage.image, pair.coverage, slot);
        const n = 2 ** pair.key.z,
          x = (slot % 4) * 512,
          y = Math.floor(slot / 4) * 512;
        set.bounds[slot].set(
          pair.key.x / n,
          pair.key.y / n,
          (pair.key.x + 1) / n,
          (pair.key.y + 1) / n
        );
        set.rects[slot].set(
          (x + 1) / 2048,
          (y + 1) / 1024,
          510 / 2048,
          510 / 1024
        );
        this.pairs[slot] = pair;
        this.starts[slot] = nowMono;
        set.valid[slot] = 1;
        set.radar.needsUpdate = true;
        set.coverage.needsUpdate = true;
      } catch {
        this.pairs[slot] = null;
      }
    }
    this.updateFades(nowMono);
    return set;
  }
  updateFades(nowMono: number) {
    if (this.set)
      for (let slot = 0; slot < 8; slot++)
        this.set.fades[slot] = this.set.valid[slot]
          ? Math.min(1, Math.max(0, (nowMono - this.starts[slot]) / 200))
          : 0;
  }
  dispose() {
    if (this.set) {
      this.set.valid.fill(0);
      this.set.radar.dispose();
      this.set.coverage.dispose();
      this.set.radar.image.width =
        this.set.radar.image.height =
        this.set.coverage.image.width =
        this.set.coverage.image.height =
          0;
    }
    this.set = null;
    this.identity = '';
    this.pairs.fill(null);
    this.release?.();
    this.release = undefined;
  }
}
