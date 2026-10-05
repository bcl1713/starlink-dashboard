import type { ProjectedPoiLabel } from '../overview-poi-label-layout';
export interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}
function overlap(a: Bounds, b: Bounds): number {
  return (
    Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) *
    Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y))
  );
}
/** Keep every identity. Crowded views use the least overlapping candidate. */
export function layoutAdsbLabels(
  labels: readonly ProjectedPoiLabel[],
  viewport: { width: number; height: number },
  reserved: readonly Bounds[]
): Record<string, readonly [number, number]> {
  const occupied = [...reserved],
    result: Record<string, readonly [number, number]> = {};
  for (const { id, bounds } of [...labels].sort((a, b) =>
    a.id.localeCompare(b.id)
  )) {
    let best: readonly [number, number] = [0, 0],
      score = Infinity;
    search: for (let ring = 0; ring <= 12; ring++)
      for (let y = -ring; y <= ring; y++)
        for (let x = -ring; x <= ring; x++) {
          if (Math.max(Math.abs(x), Math.abs(y)) !== ring) continue;
          const offset: readonly [number, number] = [
            x * (bounds.width + 8),
            y * (bounds.height + 8),
          ];
          const candidate = {
            ...bounds,
            x: bounds.x + offset[0],
            y: bounds.y + offset[1],
          };
          const inside = overlap(candidate, { x: 0, y: 0, ...viewport });
          const value =
            (bounds.width * bounds.height - inside) * 2 +
            occupied.reduce((sum, b) => sum + overlap(candidate, b), 0);
          if (value < score) {
            best = offset;
            score = value;
          }
          if (value === 0) break search;
        }
    result[id] = best;
    occupied.push({ ...bounds, x: bounds.x + best[0], y: bounds.y + best[1] });
  }
  return result;
}
