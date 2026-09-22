export type PoiLabelOffset = readonly [number, number];

export interface ProjectedPoiLabel {
  id: string;
  bounds: { x: number; y: number; width: number; height: number };
}

interface Viewport {
  width: number;
  height: number;
}

interface LabelFallback {
  anchorId: string;
  hiddenIds: string[];
}

export interface PoiLabelLayout {
  offsets: Record<string, PoiLabelOffset>;
  fallback: LabelFallback | null;
}

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

const MAX_SEARCH_RINGS = 12;
const GAP = 8;

function overlaps(first: Bounds, second: Bounds): boolean {
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}

function fitsViewport(bounds: Bounds, viewport: Viewport): boolean {
  return (
    bounds.x >= 0 &&
    bounds.y >= 0 &&
    bounds.x + bounds.width <= viewport.width &&
    bounds.y + bounds.height <= viewport.height
  );
}

function candidateOffsets(stepX: number, stepY: number): PoiLabelOffset[] {
  const candidates: PoiLabelOffset[] = [[0, 0]];

  for (let ring = 1; ring <= MAX_SEARCH_RINGS; ring += 1) {
    for (let column = -ring; column <= ring; column += 1) {
      candidates.push([column * stepX, -ring * stepY]);
      candidates.push([column * stepX, ring * stepY]);
    }
    for (let row = -ring + 1; row < ring; row += 1) {
      candidates.push([-ring * stepX, row * stepY]);
      candidates.push([ring * stepX, row * stepY]);
    }
  }

  return candidates;
}

/**
 * Packs visible POI labels by testing every candidate against their projected
 * browser bounds. It never reuses an occupied rectangle: an impossible pack
 * reports one disclosure fallback instead of emitting unreadable overlaps.
 */
export function layoutOverviewPoiLabels(
  labels: ProjectedPoiLabel[],
  viewport: Viewport
): PoiLabelLayout {
  const ordered = [...labels].sort((left, right) =>
    left.id.localeCompare(right.id)
  );
  if (ordered.length === 0) return { offsets: {}, fallback: null };

  const maxWidth = Math.max(...ordered.map((label) => label.bounds.width));
  const maxHeight = Math.max(...ordered.map((label) => label.bounds.height));
  const candidates = candidateOffsets(maxWidth + GAP, maxHeight + GAP);
  const placed: Bounds[] = [];
  const offsets: Record<string, PoiLabelOffset> = {};

  for (const label of ordered) {
    const offset = candidates.find(([x, y]) => {
      const candidate = {
        ...label.bounds,
        x: label.bounds.x + x,
        y: label.bounds.y + y,
      };
      return (
        fitsViewport(candidate, viewport) &&
        !placed.some((other) => overlaps(candidate, other))
      );
    });

    if (!offset) {
      return {
        offsets: {},
        fallback: {
          anchorId: ordered[0].id,
          hiddenIds: ordered.map((label) => label.id),
        },
      };
    }

    offsets[label.id] = offset;
    placed.push({
      ...label.bounds,
      x: label.bounds.x + offset[0],
      y: label.bounds.y + offset[1],
    });
  }

  return { offsets, fallback: null };
}
