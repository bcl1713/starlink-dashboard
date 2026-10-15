/** @vitest-environment jsdom */
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OverviewMapLabelContent } from './OverviewMapLabel';
import { applyOverviewLabelLayout } from './overview-label-dom';

afterEach(cleanup);

it('draws a connecting line from the projected point to the displaced label border', () => {
  const view = render(
    <OverviewMapLabelContent id="poi:exit" kind="poi" text={'CommKa\nExit'} />
  );
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { 'poi:exit': [30, -20] },
      placements: {
        'poi:exit': {
          bounds: { x: 130, y: 80, width: 100, height: 40 },
          leader: { start: { x: 106, y: 100 }, end: { x: 130, y: 100 } },
        },
      },
      groups: [],
    },
    { 'poi:exit': { x: 100, y: 100 } }
  );
  expect(screen.getByText('CommKa Exit').style.transform).toBe(
    'translate(30px, -20px)'
  );
  expect(
    view.container.querySelector('[data-label-leader]')?.getAttribute('d')
  ).toBe('M 6 0 L 30 0');
});

it('opens only the crowded group and restores individual labels after zoom makes room', () => {
  const view = render(
    <>
      <OverviewMapLabelContent id="enter" kind="poi" text="CommKa Enter" />
      <OverviewMapLabelContent id="exit" kind="poi" text="CommKa Exit" />
      <OverviewMapLabelContent id="airport" kind="poi" text="KADW" />
    </>
  );
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { enter: [12, -14], airport: [12, -14] },
      placements: {},
      groups: [{ anchorId: 'enter', ids: ['enter', 'exit'] }],
    },
    {}
  );
  const summary = screen.getByText('+2 POIs');
  expect(summary.closest('details')?.style.display).toBe('block');
  expect(screen.getByText('KADW').style.visibility).toBe('visible');
  fireEvent.click(summary);
  expect(summary.closest('details')?.querySelectorAll('li')).toHaveLength(2);
  expect(
    [...summary.closest('details')!.querySelectorAll('li')].map(
      (n) => n.textContent
    )
  ).toEqual(['CommKa Enter', 'CommKa Exit']);
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { enter: [12, -14], exit: [-100, 20], airport: [12, -14] },
      placements: {},
      groups: [],
    },
    {}
  );
  expect(screen.getByText('CommKa Exit').style.visibility).toBe('visible');
  expect(summary.closest('details')?.style.display).toBe('none');
});

it('does not restore an offscreen bubble when an earlier worker placement arrives', () => {
  const view = render(
    <OverviewMapLabelContent id="exit" kind="poi" text="CommKa Exit" />
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-overview-label-id]'
  )!;
  root.dataset.labelInView = 'false';
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { exit: [12, -14] },
      placements: {},
      groups: [],
    },
    { exit: { x: 100, y: 100 } }
  );
  expect(screen.getByText('CommKa Exit').style.visibility).toBe('hidden');
});

it('does not reveal an older worker placement over the current aircraft footprint', () => {
  const view = render(
    <OverviewMapLabelContent id="traffic" kind="adsb" text="MYSTC13 · Stale" />
  );
  const source = screen.getByText('MYSTC13 · Stale');
  source.getBoundingClientRect = () => new DOMRect(312, 186, 150, 28);
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { traffic: [12, -14] },
      placements: {},
      groups: [],
    },
    { traffic: { x: 300, y: 200 } },
    [{ x: 290, y: 170, width: 60, height: 60 }]
  );
  expect(source.style.visibility).toBe('hidden');
});

it('keeps an open crowded-label list off the aircraft without closing its focused disclosure', () => {
  const stage = document.createElement('div');
  stage.className = 'overview-map-stage';
  document.body.append(stage);
  const view = render(
    <OverviewMapLabelContent id="poi" kind="poi" text="KADW" />,
    { container: stage }
  );
  const canvas = document.createElement('canvas');
  canvas.getBoundingClientRect = () => new DOMRect(0, 0, 700, 500);
  stage.append(canvas);
  const details = stage.querySelector('details')!;
  const summary = details.querySelector('summary')!;
  const list = details.querySelector('ul')!;
  summary.getBoundingClientRect = () => new DOMRect(300, 200, 96, 28);
  Object.defineProperty(list, 'offsetWidth', { value: 220 });
  Object.defineProperty(list, 'offsetHeight', { value: 100 });
  // The ordinary below-summary placement intersects the aircraft.
  list.getBoundingClientRect = () =>
    new DOMRect(
      300 + parseFloat(list.style.left || '0'),
      200 + parseFloat(list.style.top || '34'),
      220,
      100
    );
  details.open = true;
  summary.focus();
  applyOverviewLabelLayout(
    stage,
    {
      offsets: { poi: [0, 0] },
      placements: {},
      groups: [{ anchorId: 'poi', ids: ['poi'] }],
    },
    {},
    [{ x: 320, y: 240, width: 50, height: 50 }]
  );
  expect(details.open).toBe(true);
  expect(document.activeElement).toBe(summary);
  const box = list.getBoundingClientRect();
  expect(
    box.bottom <= 240 || box.top >= 290 || box.right <= 320 || box.left >= 370
  ).toBe(true);
  // Native toggle handlers must retain the last rendered protection too.
  fireEvent(details, new Event('toggle'));
  expect(list.getBoundingClientRect().bottom).toBeLessThanOrEqual(240);
  view.unmount();
  stage.remove();
});

it('keeps the leader associated with a safe summary even when its hidden long source intersects the aircraft', () => {
  const view = render(
    <OverviewMapLabelContent
      id="poi"
      kind="poi"
      text="A long operational point identity"
    />
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-overview-label-id]'
  )!;
  root.querySelector<HTMLElement>(
    '[data-label-source]'
  )!.getBoundingClientRect = () => new DOMRect(100, 100, 220, 28);
  root.querySelector('summary')!.getBoundingClientRect = () =>
    new DOMRect(100, 100, 96, 28);
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { poi: [10, 0] },
      placements: {
        poi: {
          bounds: { x: 100, y: 100, width: 96, height: 28 },
          leader: { start: { x: 96, y: 100 }, end: { x: 100, y: 100 } },
        },
      },
      groups: [{ anchorId: 'poi', ids: ['poi'] }],
    },
    { poi: { x: 90, y: 100 } },
    [{ x: 250, y: 90, width: 60, height: 60 }]
  );
  expect(
    root.querySelector<SVGElement>('.overview-label-stick')!.style.visibility
  ).toBe('visible');
});

it('does not restore an offscreen summary or its open list from a delayed worker response', () => {
  const view = render(
    <OverviewMapLabelContent id="poi" kind="poi" text="KADW" />
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-overview-label-id]'
  )!;
  root.dataset.labelInView = 'false';
  root.querySelector('details')!.open = true;
  applyOverviewLabelLayout(
    view.container,
    {
      offsets: { poi: [10, 0] },
      placements: {},
      groups: [{ anchorId: 'poi', ids: ['poi'] }],
    },
    {},
    []
  );
  expect(root.querySelector('details')!.style.visibility).toBe('hidden');
  expect(root.querySelector('ul')!.style.visibility).toBe('hidden');
});

it('protects against the fractional painted size of an open disclosure', () => {
  const stage = document.createElement('div');
  stage.className = 'overview-map-stage';
  document.body.append(stage);
  const view = render(
    <OverviewMapLabelContent id="poi" kind="poi" text="KADW" />,
    { container: stage }
  );
  const canvas = document.createElement('canvas');
  canvas.getBoundingClientRect = () => new DOMRect(0, 0, 700, 500);
  stage.append(canvas);
  const details = stage.querySelector('details')!,
    summary = details.querySelector('summary')!,
    list = details.querySelector('ul')!;
  summary.getBoundingClientRect = () => new DOMRect(300, 100, 96, 28);
  Object.defineProperty(list, 'offsetWidth', { value: 220 });
  Object.defineProperty(list, 'offsetHeight', { value: 100 });
  list.getBoundingClientRect = () =>
    new DOMRect(
      300 + parseFloat(list.style.left || '0'),
      100 + parseFloat(list.style.top || '34'),
      220,
      100.4
    );
  details.open = true;
  applyOverviewLabelLayout(
    stage,
    {
      offsets: { poi: [0, 0] },
      placements: {},
      groups: [{ anchorId: 'poi', ids: ['poi'] }],
    },
    {},
    [{ x: 320, y: 234.2, width: 50, height: 50 }]
  );
  const b = list.getBoundingClientRect();
  expect(
    list.style.visibility !== 'visible' ||
      b.bottom <= 234.2 ||
      b.top >= 284.2 ||
      b.right <= 320 ||
      b.left >= 370
  ).toBe(true);
  view.unmount();
  stage.remove();
});
