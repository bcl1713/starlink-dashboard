import {
  disclosureBounds,
  type LabelPoint,
  type OverviewLabelLayoutResult,
} from './overview-label-layout';

export function positionOverviewDisclosure(
  disclosure: HTMLDetailsElement
): void {
  if (!disclosure.open) return;
  const viewport = disclosure
    .closest('.overview-map-stage')
    ?.querySelector('canvas')
    ?.getBoundingClientRect();
  if (!viewport) return;
  const summary = disclosure.querySelector('summary')!.getBoundingClientRect();
  const list = disclosure.querySelector('ul')!;
  const bounds = disclosureBounds(
    {
      x: summary.x - viewport.x,
      y: summary.y - viewport.y,
      width: summary.width,
      height: summary.height,
    },
    { width: list.offsetWidth, height: list.offsetHeight },
    viewport
  );
  list.style.left = `${bounds.x - (summary.x - viewport.x)}px`;
  list.style.top = `${bounds.y - (summary.y - viewport.y)}px`;
}

export function applyOverviewLabelLayout(
  stage: HTMLElement,
  layout: OverviewLabelLayoutResult,
  anchors: Record<string, LabelPoint>
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
    positionOverviewDisclosure(disclosure);
  }
}
