import {
  disclosureBounds,
  labelBoundsOverlap,
  type LabelBounds,
  type LabelPoint,
  type OverviewLabelLayoutResult,
} from './overview-label-layout';

const aircraftByStage = new WeakMap<HTMLElement, readonly LabelBounds[]>();

export function positionOverviewDisclosure(
  disclosure: HTMLDetailsElement,
  aircraft?: readonly LabelBounds[]
): void {
  if (!disclosure.open) return;
  const stage = disclosure.closest<HTMLElement>('.overview-map-stage');
  const protectedBounds =
    aircraft ?? (stage && aircraftByStage.get(stage)) ?? [];
  const viewport = stage?.querySelector('canvas')?.getBoundingClientRect();
  if (!viewport) return;
  const summary = disclosure.querySelector('summary')!.getBoundingClientRect();
  const list = disclosure.querySelector('ul')!;
  if (
    disclosure.closest<HTMLElement>('[data-overview-label-id]')?.dataset
      .labelInView === 'false'
  ) {
    list.style.visibility = 'hidden';
    return;
  }
  list.style.maxWidth = `${Math.max(0, viewport.width - 12)}px`;
  list.style.maxHeight = `min(180px, calc(100dvh - 24px), ${Math.max(0, viewport.height - 12)}px)`;
  const painted = list.getBoundingClientRect();
  let bounds = disclosureBounds(
    {
      x: summary.x - viewport.x,
      y: summary.y - viewport.y,
      width: summary.width,
      height: summary.height,
    },
    { width: painted.width, height: painted.height },
    viewport
  );
  const safe = (box: LabelBounds) =>
    !protectedBounds.some((b) => labelBoundsOverlap(box, b, 0));
  if (!safe(bounds)) {
    const options = [
      { ...bounds, y: summary.y - viewport.y - bounds.height - 6 },
      { ...bounds, x: summary.x - viewport.x - bounds.width - 6 },
      { ...bounds, x: summary.right - viewport.x + 6 },
      ...protectedBounds.flatMap((b) => [
        { ...bounds, x: b.x - bounds.width - 6 },
        { ...bounds, x: b.x + b.width + 6 },
        { ...bounds, y: b.y - bounds.height - 6 },
        { ...bounds, y: b.y + b.height + 6 },
      ]),
    ];
    const alternative = options.find(
      (b) =>
        b.x >= 6 &&
        b.y >= 6 &&
        b.x + b.width <= viewport.width - 6 &&
        b.y + b.height <= viewport.height - 6 &&
        safe(b)
    );
    if (alternative) bounds = alternative;
  }
  list.style.visibility = safe(bounds) ? 'visible' : 'hidden';
  list.style.left = `${bounds.x - (summary.x - viewport.x)}px`;
  list.style.top = `${bounds.y - (summary.y - viewport.y)}px`;
  const actual = list.getBoundingClientRect();
  if (
    !safe({
      x: actual.x - viewport.x,
      y: actual.y - viewport.y,
      width: actual.width,
      height: actual.height,
    })
  )
    list.style.visibility = 'hidden';
}

export function applyOverviewLabelLayout(
  stage: HTMLElement,
  layout: OverviewLabelLayoutResult,
  anchors: Record<string, LabelPoint>,
  aircraft: readonly LabelBounds[] = []
): void {
  const roots = [
    ...stage.querySelectorAll<HTMLElement>('[data-overview-label-id]'),
  ];
  const nodes = new Map(
    roots.map((node) => [node.dataset.overviewLabelId!, node])
  );
  const grouped = new Set(layout.groups.flatMap((group) => group.ids));
  for (const root of roots) {
    const id = root.dataset.overviewLabelId!;
    const source = root.querySelector<HTMLElement>('[data-label-source]')!;
    const disclosure = root.querySelector<HTMLDetailsElement>('details')!;
    const offset = layout.offsets[id];
    source.style.visibility =
      offset && !grouped.has(id) && root.dataset.labelInView !== 'false'
        ? 'visible'
        : 'hidden';
    source.dataset.layoutVisible = String(
      source.style.visibility === 'visible'
    );
    disclosure.style.display = 'none';
    if (!layout.groups.some((group) => group.anchorId === id)) {
      disclosure.open = false;
      delete disclosure.dataset.groupIds;
      disclosure
        .querySelector('summary')!
        .removeAttribute('data-poi-label-fallback');
      disclosure.querySelector('summary')!.textContent = '';
      disclosure.querySelector('ul')!.replaceChildren();
      delete disclosure.querySelector('ul')!.dataset.names;
    }
    if (offset)
      source.style.transform = `translate(${offset[0]}px, ${offset[1]}px)`;
    source.dataset.poiLabelOffset = offset?.join(',') ?? '0,0';
    const leader = layout.placements[id]?.leader,
      anchor = anchors[id];
    const d =
      leader && anchor
        ? `M ${leader.start.x - anchor.x} ${leader.start.y - anchor.y} L ${leader.end.x - anchor.x} ${leader.end.y - anchor.y}`
        : '';
    for (const path of root.querySelectorAll('path')) path.setAttribute('d', d);
  }
  for (const group of layout.groups) {
    const root = nodes.get(group.anchorId),
      offset = layout.offsets[group.anchorId];
    if (!root || !offset) continue;
    const disclosure = root.querySelector<HTMLDetailsElement>('details')!;
    disclosure.dataset.groupIds = JSON.stringify(group.ids);
    const summary = disclosure.querySelector('summary')!;
    const allPois = group.ids.every(
      (id) => nodes.get(id)?.dataset.labelKind === 'poi'
    );
    summary.textContent = `+${group.ids.length} ${allPois ? 'POIs' : 'labels'}`;
    summary.setAttribute(
      'aria-label',
      `Show ${group.ids.length} crowded ${allPois ? 'POIs' : 'map labels'}`
    );
    summary.dataset.poiLabelFallback = allPois ? 'true' : 'false';
    const list = disclosure.querySelector('ul')!;
    const names = group.ids.map((id) => nodes.get(id)?.dataset.labelText ?? id);
    if (JSON.stringify(names) !== list.dataset.names) {
      list.replaceChildren(
        ...names.map((name) => {
          const item = document.createElement('li');
          item.textContent = name;
          return item;
        })
      );
      list.dataset.names = JSON.stringify(names);
    }
    disclosure.style.transform = `translate(${offset[0]}px, ${offset[1]}px)`;
    disclosure.style.display = 'block';
    positionOverviewDisclosure(disclosure, aircraft);
  }
  protectOverviewLabels(stage, aircraft);
}

/** Runs after Html/camera updates on every rendered frame and after each worker
 * response. The expensive solver can lag; the aircraft exclusion cannot. */
export function protectOverviewLabels(
  stage: HTMLElement,
  aircraft: readonly LabelBounds[]
): void {
  aircraftByStage.set(stage, aircraft);
  const viewport = stage.querySelector('canvas')?.getBoundingClientRect();
  const clear = (node: HTMLElement) => {
    const rect = node.getBoundingClientRect();
    return !aircraft.some((b) =>
      labelBoundsOverlap(
        {
          x: rect.x - (viewport?.x ?? 0),
          y: rect.y - (viewport?.y ?? 0),
          width: rect.width,
          height: rect.height,
        },
        b,
        0
      )
    );
  };
  for (const root of stage.querySelectorAll<HTMLElement>(
    '[data-overview-label-id]'
  )) {
    let inView = root.dataset.labelInView !== 'false';
    if (viewport) {
      const anchor = root.getBoundingClientRect();
      if (
        anchor.x < viewport.x ||
        anchor.x > viewport.right ||
        anchor.y < viewport.y ||
        anchor.y > viewport.bottom
      ) {
        inView = false;
        root.dataset.labelInView = 'false';
      }
    }
    const source = root.querySelector<HTMLElement>('[data-label-source]')!;
    const safe = clear(source);
    source.style.visibility =
      source.dataset.layoutVisible === 'true' && inView && safe
        ? 'visible'
        : 'hidden';
    const details = root.querySelector<HTMLDetailsElement>('details')!;
    const summary = details.querySelector('summary')!;
    if (details.style.display === 'block' && !clear(summary) && viewport) {
      const rect = summary.getBoundingClientRect();
      const box = {
        x: rect.x - viewport.x,
        y: rect.y - viewport.y,
        width: rect.width,
        height: rect.height,
      };
      const options = aircraft.flatMap((b) => [
        { ...box, x: b.x - box.width - 6 },
        { ...box, x: b.x + b.width + 6 },
        { ...box, y: b.y - box.height - 6 },
        { ...box, y: b.y + b.height + 6 },
      ]);
      const moved = options.find(
        (b) =>
          b.x >= 6 &&
          b.y >= 6 &&
          b.x + b.width <= viewport.width - 6 &&
          b.y + b.height <= viewport.height - 6 &&
          !aircraft.some((a) => labelBoundsOverlap(b, a, 0))
      );
      if (moved) {
        const anchor = root.getBoundingClientRect();
        details.style.transform = `translate(${moved.x - (anchor.x - viewport.x)}px, ${moved.y - (anchor.y - viewport.y)}px)`;
        // The next worker snapshot replaces the old connecting line.
        for (const path of root.querySelectorAll('path'))
          path.setAttribute('d', '');
      }
    }
    const summarySafe = details.style.display !== 'block' || clear(summary);
    details.style.visibility = inView && summarySafe ? 'visible' : 'hidden';
    if (details.open) positionOverviewDisclosure(details, aircraft);
    if (!inView || !summarySafe)
      details.querySelector('ul')!.style.visibility = 'hidden';
    root.dataset.labelAircraftSafe = String(safe && summarySafe);
    root.querySelector<SVGElement>('.overview-label-stick')!.style.visibility =
      inView &&
      (details.style.display === 'block'
        ? summarySafe
        : safe && source.dataset.layoutVisible === 'true')
        ? 'visible'
        : 'hidden';
  }
}
