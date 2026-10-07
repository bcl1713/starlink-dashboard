import type { GridLease } from '@/services/aviation-grid';
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
