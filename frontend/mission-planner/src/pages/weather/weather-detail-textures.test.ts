/** @vitest-environment jsdom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { readyWeather } from '@/test/weather-fixtures';
import { WeatherWork } from './weather-work';
import { WeatherDetailTextureOwner } from './weather-detail-textures';
import type { DetailContext, DetailPair } from './weather-detail';
const context: DetailContext = {
  generation: 1,
  settingsRevision: 1,
  manifest: readyWeather(),
};
const draw = vi.fn(),
  clear = vi.fn();
beforeEach(() =>
  vi
    .spyOn(HTMLCanvasElement.prototype, 'getContext')
    .mockReturnValue({
      drawImage: draw,
      clearRect: clear,
    } as unknown as CanvasRenderingContext2D)
);
afterEach(() => {
  vi.restoreAllMocks();
  draw.mockClear();
  clear.mockClear();
});
function pair(x = 16): DetailPair {
  return {
    context,
    key: { z: 5, x, y: 16 },
    radar: { width: 512, height: 512 } as ImageBitmap,
    coverage: { width: 512, height: 512 } as ImageBitmap,
    dispose: vi.fn(),
  };
}
it('allocates exactly two fixed atlases, in-place updates, gutters and no mipmaps', () => {
  const work = new WeatherWork(),
    owner = new WeatherDetailTextureOwner(work),
    a = pair();
  const set = owner.replace(context, [a], 0)!;
  expect(set.radar.image.width).toBe(2048);
  expect(set.radar.image.height).toBe(1024);
  expect(set.radar.generateMipmaps).toBe(false);
  expect(set.coverage.generateMipmaps).toBe(false);
  expect(2 * set.radar.image.width * set.radar.image.height * 4).toBe(
    16 * 1024 * 1024
  );
  expect(work.snapshot().decodedBytes).toBe(16 * 1024 * 1024);
  expect(draw).toHaveBeenCalled();
  const disposal = vi.spyOn(set.radar, 'dispose');
  const b = pair(17);
  expect(owner.replace(context, [a, b], 200)!.radar).toBe(set.radar);
  expect(set.valid.filter(Boolean)).toHaveLength(2);
  expect(set.rects[0].z * 2048).toBe(510);
  expect(set.rects[0].w * 1024).toBe(510);
  owner.replace(context, [b], 400);
  expect(set.valid.filter(Boolean)).toHaveLength(1);
  owner.dispose();
  owner.dispose();
  expect(disposal).toHaveBeenCalledTimes(1);
  expect(work.snapshot().decodedBytes).toBe(0);
  expect(a.dispose).not.toHaveBeenCalled();
});
it('rejects mismatched identity/dimensions and tears down before context replacement', () => {
  const owner = new WeatherDetailTextureOwner(new WeatherWork());
  expect(
    owner.replace(
      context,
      [{ ...pair(), context: { ...context, generation: 2 } }],
      0
    )
  ).toBeNull();
  const first = owner.replace(context, [pair()], 0)!;
  const disposed = vi.spyOn(first.coverage, 'dispose');
  owner.replace({ ...context, generation: 2 }, [], 1);
  expect(disposed).toHaveBeenCalledTimes(1);
  expect(
    owner.replace(
      context,
      [{ ...pair(), radar: { width: 256, height: 512 } as ImageBitmap }],
      2
    )
  ).toBeNull();
  owner.dispose();
});
it('clears validity before writing reused slots and fades for 200 monotonic ms', () => {
  const owner = new WeatherDetailTextureOwner(new WeatherWork()),
    set = owner.replace(context, [pair()], 100)!;
  expect(set.fades[0]).toBe(0);
  owner.replace(context, [pair()], 200);
  // A different bitmap pair restarts its own fade, even at identical XYZ.
  expect(set.fades[0]).toBe(0);
  const b = pair(17);
  draw.mockImplementationOnce(() => expect(set.valid[0]).toBe(0));
  owner.replace(context, [b], 300);
  owner.updateFades(400);
  expect(set.fades[0]).toBe(0.5);
  owner.updateFades(500);
  expect(set.fades[0]).toBe(1);
  owner.dispose();
});
