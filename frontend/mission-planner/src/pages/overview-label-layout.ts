export type OverviewLabelOffset = readonly [number, number];
export interface LabelPoint {
  x: number;
  y: number;
}
export interface LabelBounds extends LabelPoint {
  width: number;
  height: number;
}
export interface ProjectedOverviewLabel {
  id: string;
  bounds: LabelBounds;
  /** ADS-B identities remain individually labelled even in an impossible pack. */
  retainIdentity?: boolean;
  priority?: number;
}
export interface LabelLeader {
  start: LabelPoint;
  end: LabelPoint;
}
export interface OverviewLabelGeometry {
  /** Full rendered own-aircraft bounds, already expanded by its visibility margin. */
  aircraft: readonly LabelBounds[];
  markers?: readonly LabelBounds[];
  paths?: readonly LabelLeader[];
}
export interface LabelPlacement {
  bounds: LabelBounds;
  leader: LabelLeader | null;
}
export interface LabelGroup {
  anchorId: string;
  ids: string[];
}
export interface OverviewLabelLayoutResult {
  offsets: Record<string, OverviewLabelOffset>;
  placements: Record<string, LabelPlacement>;
  groups: LabelGroup[];
}
interface Viewport {
  width: number;
  height: number;
}
interface Entry {
  label: ProjectedOverviewLabel;
  ids: string[];
  placement: LabelPlacement;
  grouped?: boolean;
}
const GAP = 6;
const MARKER_GAP = 12;
const GROUP_WIDTH = 96;
const GROUP_HEIGHT = 28;
const NEIGHBOR_DISTANCE = 96;

export function labelBoundsOverlap(
  a: LabelBounds,
  b: LabelBounds,
  gap = GAP
): boolean {
  return (
    a.x < b.x + b.width + gap &&
    a.x + a.width + gap > b.x &&
    a.y < b.y + b.height + gap &&
    a.y + a.height + gap > b.y
  );
}
function inside(b: LabelBounds, v: Viewport): boolean {
  return (
    b.x >= GAP &&
    b.y >= GAP &&
    b.x + b.width <= v.width - GAP &&
    b.y + b.height <= v.height - GAP
  );
}
export function disclosureBounds(
  summary: LabelBounds,
  size: Viewport,
  viewport: Viewport
): LabelBounds {
  const width = Math.min(size.width, Math.max(0, viewport.width - GAP * 2));
  const height = Math.min(size.height, Math.max(0, viewport.height - GAP * 2));
  const below = summary.y + summary.height + GAP;
  return {
    x: Math.max(GAP, Math.min(summary.x, viewport.width - width - GAP)),
    y:
      below + height <= viewport.height - GAP
        ? below
        : Math.max(GAP, summary.y - height - GAP),
    width,
    height,
  };
}
export function calloutLeader(
  anchor: LabelPoint,
  box: LabelBounds
): LabelLeader | null {
  const end = {
    x: Math.max(box.x, Math.min(anchor.x, box.x + box.width)),
    y: Math.max(box.y, Math.min(anchor.y, box.y + box.height)),
  };
  const dx = end.x - anchor.x,
    dy = end.y - anchor.y,
    length = Math.hypot(dx, dy);
  if (length <= 6) return null;
  return {
    start: { x: anchor.x + (dx * 6) / length, y: anchor.y + (dy * 6) / length },
    end,
  };
}
function cross(a: LabelPoint, b: LabelPoint, c: LabelPoint): number {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}
function intersects(a: LabelLeader, b: LabelLeader): boolean {
  return (
    cross(a.start, a.end, b.start) * cross(a.start, a.end, b.end) < -0.01 &&
    cross(b.start, b.end, a.start) * cross(b.start, b.end, a.end) < -0.01
  );
}
export function throughBox(line: LabelLeader, box: LabelBounds): boolean {
  let low = 0,
    high = 1;
  for (const axis of ['x', 'y'] as const) {
    const start = line.start[axis],
      delta = line.end[axis] - start;
    const min = box[axis],
      max = min + (axis === 'x' ? box.width : box.height);
    if (Math.abs(delta) < 1e-9) {
      if (start < min || start > max) return false;
    } else {
      const a = (min - start) / delta,
        b = (max - start) / delta;
      low = Math.max(low, Math.min(a, b));
      high = Math.min(high, Math.max(a, b));
      if (low > high) return false;
    }
  }
  return true;
}
function candidates(
  label: ProjectedOverviewLabel,
  labels: ProjectedOverviewLabel[],
  previous?: OverviewLabelOffset
): LabelBounds[] {
  const { x, y, width, height } = label.bounds;
  const neighbor = labels
    .filter(
      (l) =>
        l.id !== label.id &&
        Math.hypot(l.bounds.x - x, l.bounds.y - y) < NEIGHBOR_DISTANCE &&
        Math.abs(l.bounds.x - x) > 1
    )
    .sort(
      (a, b) =>
        Math.hypot(a.bounds.x - x, a.bounds.y - y) -
        Math.hypot(b.bounds.x - x, b.bounds.y - y)
    )[0];
  const leftFirst = neighbor && neighbor.bounds.x > x;
  const result: LabelBounds[] = previous
    ? [{ x: x + previous[0], y: y + previous[1], width, height }]
    : [];
  for (let ring = 0; ring <= (label.retainIdentity ? 32 : 8); ring++) {
    const gap = MARKER_GAP + ring * 24;
    const left = { x: x - gap - width, y: y - height / 2, width, height };
    const right = { x: x + gap, y: y - height / 2, width, height };
    result.push(
      ...(leftFirst ? [left, right] : [right, left]),
      { x: x - width / 2, y: y - gap - height, width, height },
      { x: x - width / 2, y: y + gap, width, height },
      { x: x - gap - width, y: y - gap - height, width, height },
      { x: x + gap, y: y - gap - height, width, height },
      { x: x - gap - width, y: y + gap, width, height },
      { x: x + gap, y: y + gap, width, height }
    );
  }
  return result;
}

/** One placement pass for all overview identities. Source bounds start at the
 * projected marker. Prefer short leaders, preserve nearby east/west order, and
 * retain a valid previous placement so camera motion does not reshuffle labels.
 * Only the local POI group is disclosed if it cannot fit; unrelated labels stay.
 */
export function layoutOverviewLabels(
  labels: ProjectedOverviewLabel[],
  viewport: Viewport,
  reserved: readonly LabelBounds[] = [],
  previous: Record<string, OverviewLabelOffset> = {},
  geometry: OverviewLabelGeometry = { aircraft: [] }
): OverviewLabelLayoutResult {
  const ordered = [...labels].sort(
    (a, b) =>
      (b.priority ?? 0) - (a.priority ?? 0) ||
      a.bounds.x - b.bounds.x ||
      a.bounds.y - b.bounds.y ||
      a.id.localeCompare(b.id)
  );
  const entries: Entry[] = [];
  const aircraftSafe = (box: LabelBounds) =>
    inside(box, viewport) &&
    !geometry.aircraft.some((b) => labelBoundsOverlap(box, b));
  // Relax soft collisions only after trying clean placements. The own-aircraft
  // exclusion is never relaxed, including ADS-B and compact group fallbacks.
  const fallback = (label: ProjectedOverviewLabel): LabelPlacement | null => {
    const options = candidates(
      { ...label, retainIdentity: true },
      ordered
    ).filter(aircraftSafe);
    const blockers = [
      ...reserved,
      ...(geometry.markers ?? []),
      ...entries.map((e) => e.placement.bounds),
    ];
    const score = (box: LabelBounds) =>
      blockers.reduce(
        (sum, b) =>
          sum +
          Math.max(
            0,
            Math.min(box.x + box.width, b.x + b.width) - Math.max(box.x, b.x)
          ) *
            Math.max(
              0,
              Math.min(box.y + box.height, b.y + b.height) -
                Math.max(box.y, b.y)
            ),
        0
      ) +
      (geometry.paths ?? []).filter((line) => throughBox(line, box)).length *
        box.width;
    let box: LabelBounds | undefined,
      best = Infinity;
    for (const option of options) {
      const occupied = score(option);
      if (occupied < best) {
        box = option;
        best = occupied;
      }
      if (occupied === 0) break;
    }
    return box
      ? { bounds: box, leader: calloutLeader(label.bounds, box) }
      : null;
  };
  const place = (
    label: ProjectedOverviewLabel,
    prev?: OverviewLabelOffset
  ): LabelPlacement | null => {
    const options = candidates(label, ordered, prev);
    const previousBox = prev ? options.shift() : undefined;
    const anchors = ordered
      .filter((l) => l.id !== label.id)
      .map((l) => ({
        x: l.bounds.x - 4,
        y: l.bounds.y - 4,
        width: 8,
        height: 8,
      }));
    const blockers = [
      ...reserved,
      ...geometry.aircraft,
      ...(geometry.markers ?? []),
      ...anchors,
      ...entries.map((e) => e.placement.bounds),
    ];
    const rectangleValid = (box: LabelBounds) =>
      inside(box, viewport) &&
      !blockers.some((b) => labelBoundsOverlap(box, b)) &&
      !(geometry.paths ?? []).some((line) => throughBox(line, box));
    const valid = (box: LabelBounds) => {
      if (!rectangleValid(box)) return false;
      const leader = calloutLeader(label.bounds, box);
      if (
        leader &&
        (anchors.some((b) => throughBox(leader, b)) ||
          reserved.some(
            (b) =>
              !(
                label.bounds.x >= b.x &&
                label.bounds.x <= b.x + b.width &&
                label.bounds.y >= b.y &&
                label.bounds.y <= b.y + b.height
              ) && throughBox(leader, b)
          ) ||
          entries.some(
            (e) =>
              throughBox(leader, e.placement.bounds) ||
              (e.placement.leader &&
                (intersects(leader, e.placement.leader) ||
                  throughBox(e.placement.leader, box)))
          ))
      )
        return false;
      return entries.every((e) => {
        const dx = label.bounds.x - e.label.bounds.x;
        if (
          Math.abs(dx) <= 1 ||
          Math.hypot(dx, label.bounds.y - e.label.bounds.y) >= NEIGHBOR_DISTANCE
        )
          return true;
        return (
          dx *
            (box.x +
              box.width / 2 -
              e.placement.bounds.x -
              e.placement.bounds.width / 2) >=
          0
        );
      });
    };
    const distance = (box: LabelBounds) => {
      const line = calloutLeader(label.bounds, box);
      return line
        ? Math.hypot(line.end.x - line.start.x, line.end.y - line.start.y)
        : 0;
    };
    // Small improvements do not shuffle a stable label. A large improvement
    // releases offsets stranded by the initial camera-framing animation.
    const previousValid = previousBox && valid(previousBox);
    if (previousValid && distance(previousBox) <= MARKER_GAP + 48)
      return {
        bounds: previousBox,
        leader: calloutLeader(label.bounds, previousBox),
      };
    const nearbyBox = options.find(
      (box) =>
        (!previousValid || distance(box) < distance(previousBox) - 48) &&
        valid(box)
    );
    const box = nearbyBox ?? (previousValid ? previousBox : undefined);
    return box
      ? { bounds: box, leader: calloutLeader(label.bounds, box) }
      : null;
  };
  for (const source of ordered) {
    const placement = place(source, previous[source.id]);
    if (placement) {
      entries.push({ label: source, ids: [source.id], placement });
      continue;
    }
    if (source.retainIdentity) {
      const safe = fallback(source);
      if (safe)
        entries.push({ label: source, ids: [source.id], placement: safe });
      continue;
    }
    const nearby = entries.filter(
      (e) =>
        !e.label.retainIdentity &&
        Math.hypot(
          e.label.bounds.x - source.bounds.x,
          e.label.bounds.y - source.bounds.y
        ) < NEIGHBOR_DISTANCE
    );
    const ids = [...nearby.flatMap((e) => e.ids), source.id];
    for (const entry of nearby) entries.splice(entries.indexOf(entry), 1);
    const anchor = nearby[0]?.label ?? source;
    const group = {
      ...anchor,
      bounds: { ...anchor.bounds, width: GROUP_WIDTH, height: GROUP_HEIGHT },
    };
    const grouped = place(group) ?? fallback(group);
    if (grouped)
      entries.push({ label: group, ids, placement: grouped, grouped: true });
  }
  const result: OverviewLabelLayoutResult = {
    offsets: {},
    placements: {},
    groups: [],
  };
  for (const entry of entries) {
    const id = entry.label.id,
      box = entry.placement.bounds;
    result.offsets[id] = [
      box.x - entry.label.bounds.x,
      box.y - entry.label.bounds.y,
    ];
    result.placements[id] = entry.placement;
    if (entry.grouped) result.groups.push({ anchorId: id, ids: entry.ids });
  }
  return result;
}
