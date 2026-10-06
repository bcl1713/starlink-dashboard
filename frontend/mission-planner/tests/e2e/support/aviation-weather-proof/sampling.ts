import type { Descriptor } from './model';
export function sampleGrid(
  d: Descriptor,
  values: Int16Array,
  mask: Uint8Array,
  latitude: number,
  longitude: number,
  key = 't'
) {
  const { width: w, height: h } = d.grid;
  const lon = (((longitude + 180) % 360) + 360) % 360;
  const x = lon / 0.5,
    y = (90 - latitude) / 0.5;
  if (y < 0 || y > h - 1 || (w !== 720 && x > w - 1))
    return { value: null, mask: 1 };
  const x0 = Math.floor(x),
    y0 = Math.floor(y),
    x1 = w === 720 ? (x0 + 1) % w : Math.min(x0 + 1, w - 1),
    y1 = Math.min(y0 + 1, h - 1);
  const ids = [y0 * w + x0, y0 * w + x1, y1 * w + x0, y1 * w + x1];
  const invalid = Math.max(...ids.map((i) => mask[i]));
  if (invalid) return { value: null, mask: invalid };
  const tx = x - x0,
    ty = y - y0,
    weights = [(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty];
  const raw = ids.reduce((v, index, i) => v + values[index] * weights[i], 0);
  return {
    value: raw * d.components[key].scale! + d.components[key].offset!,
    mask: 0,
  };
}
export function barb(u: number, v: number) {
  const speed = Math.hypot(u, v);
  return {
    fromEast: speed && u ? -u / speed : 0,
    fromNorth: speed && v ? -v / speed : 0,
    knots: Math.round((speed * 1.94384449) / 5) * 5,
  };
}
