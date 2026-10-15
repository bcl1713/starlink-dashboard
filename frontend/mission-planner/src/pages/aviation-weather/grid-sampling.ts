import type { GridLease } from '@/services/aviation-grid';
/** Allocation-free wind sampling; out is [east m/s, north m/s, validity mask]. */
export function sampleWindInto(
  lease: GridLease,
  latitude: number,
  longitude: number,
  out: Float64Array
): void {
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    Math.abs(latitude) > 90
  ) {
    out[0] = out[1] = NaN;
    out[2] = 1;
    return;
  }
  const x = ((((longitude + 180) % 360) + 360) % 360) * 2,
    y = (90 - latitude) * 2;
  const col = Math.floor(x),
    row = Math.floor(y),
    next = (col + 1) % 720,
    lower = Math.min(row + 1, 360);
  const fx = x - col,
    fy = y - row;
  const a = row * 720 + col,
    b = row * 720 + next,
    c = lower * 720 + col,
    d = lower * 720 + next;
  const wa = (1 - fx) * (1 - fy),
    wb = fx * (1 - fy),
    wc = (1 - fx) * fy,
    wd = fx * fy;
  let mask = 0;
  if (wa > 0) mask = Math.max(mask, lease.mask[a]);
  if (wb > 0) mask = Math.max(mask, lease.mask[b]);
  if (wc > 0) mask = Math.max(mask, lease.mask[c]);
  if (wd > 0) mask = Math.max(mask, lease.mask[d]);
  out[2] = mask;
  if (mask) {
    out[0] = out[1] = NaN;
    return;
  }
  const u = lease.u,
    v = lease.v,
    components = lease.descriptor.grid.components;
  out[0] =
    (u[a] * wa + u[b] * wb + u[c] * wc + u[d] * wd) * components[0].scale! +
    components[0].offset!;
  out[1] =
    (v[a] * wa + v[b] * wb + v[c] * wc + v[d] * wd) * components[1].scale! +
    components[1].offset!;
}
/** Only positive-weight contributors participate in the shared validity mask. */
export function sampleGrid(
  lease: GridLease,
  latitude: number,
  longitude: number
) {
  const invalid = (mask: number) => ({ u: null, v: null, t: null, mask });
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    Math.abs(latitude) > 90
  )
    return invalid(1);
  const x = ((((longitude + 180) % 360) + 360) % 360) * 2,
    y = (90 - latitude) * 2;
  const col = Math.floor(x),
    row = Math.floor(y),
    fx = x - col,
    fy = y - row;
  const nodes = [
    [row * 720 + col, (1 - fx) * (1 - fy)],
    [row * 720 + ((col + 1) % 720), fx * (1 - fy)],
    [Math.min(row + 1, 360) * 720 + col, (1 - fx) * fy],
    [Math.min(row + 1, 360) * 720 + ((col + 1) % 720), fx * fy],
  ];
  let mask = 0;
  for (const [i, w] of nodes) if (w > 0) mask = Math.max(mask, lease.mask[i]);
  if (mask) return invalid(mask);
  const values = [lease.u, lease.v, lease.t].map((buffer, n) => {
    let value = 0;
    for (const [i, w] of nodes) if (w > 0) value += buffer[i] * w;
    const component = lease.descriptor.grid.components[n];
    return value * component.scale! + component.offset!;
  });
  return { u: values[0], v: values[1], t: values[2], mask: 0 };
}
