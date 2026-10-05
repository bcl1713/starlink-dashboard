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

function overlaps(a: LabelBounds, b: LabelBounds): boolean {
  return (
    a.x < b.x + b.width + GAP &&
    a.x + a.width + GAP > b.x &&
    a.y < b.y + b.height + GAP &&
    a.y + a.height + GAP > b.y
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
function throughBox(line: LabelLeader, box: LabelBounds): boolean {
  const within = (p: LabelPoint) =>
    p.x > box.x &&
    p.x < box.x + box.width &&
    p.y > box.y &&
    p.y < box.y + box.height;
  if (within(line.start) || within(line.end)) return true;
  const corners = [
    { x: box.x, y: box.y },
    { x: box.x + box.width, y: box.y },
    { x: box.x + box.width, y: box.y + box.height },
    { x: box.x, y: box.y + box.height },
  ];
  return corners.some((p, i) =>
    intersects(line, { start: p, end: corners[(i + 1) % 4] })
  );
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
  previous: Record<string, OverviewLabelOffset> = {}
): OverviewLabelLayoutResult {
  const ordered = [...labels].sort(
    (a, b) =>
      (b.priority ?? 0) - (a.priority ?? 0) ||
      a.bounds.x - b.bounds.x ||
      a.bounds.y - b.bounds.y ||
      a.id.localeCompare(b.id)
  );
  const entries: Entry[] = [];
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
      ...anchors,
      ...entries.map((e) => e.placement.bounds),
    ];
    const rectangleValid = (box: LabelBounds) =>
      inside(box, viewport) && !blockers.some((b) => overlaps(box, b));
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
      // An exceptionally crowded traffic view keeps every identity. Prefer an
      // in-viewport bubble with the least occupied area if a clean pack is impossible.
      const options = candidates(source, ordered).filter((box) =>
        inside(box, viewport)
      );
      const area = (a: LabelBounds, b: LabelBounds) =>
        Math.max(
          0,
          Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)
        ) *
        Math.max(
          0,
          Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y)
        );
      const blockers = [...reserved, ...entries.map((e) => e.placement.bounds)];
      let box = options[0] ?? { ...source.bounds, x: GAP, y: GAP };
      let bestArea = Infinity;
      for (const option of options) {
        const score = blockers.reduce(
          (sum, blocker) => sum + area(option, blocker),
          0
        );
        if (score < bestArea) {
          box = option;
          bestArea = score;
        }
        if (score === 0) break;
      }
      entries.push({
        label: source,
        ids: [source.id],
        placement: { bounds: box, leader: calloutLeader(source.bounds, box) },
      });
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
    const grouped = place(group);
    if (grouped)
      entries.push({ label: group, ids, placement: grouped, grouped: true });
    else {
      // Reserve a compact disclosure even in a fully constrained viewport.
      // Never turn one crowded area into a global removal of map labels.
      const box = {
        ...group.bounds,
        x: Math.max(
          GAP,
          Math.min(group.bounds.x, viewport.width - GROUP_WIDTH - GAP)
        ),
        y: Math.max(
          GAP,
          Math.min(
            group.bounds.y + MARKER_GAP,
            viewport.height - GROUP_HEIGHT - GAP
          )
        ),
      };
      entries.push({
        label: group,
        ids,
        placement: { bounds: box, leader: calloutLeader(group.bounds, box) },
        grouped: true,
      });
    }
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
