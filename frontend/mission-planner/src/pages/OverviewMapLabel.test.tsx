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
