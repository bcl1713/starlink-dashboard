/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { visibleOverviewOverlayBounds } from './overview-label-dom';

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

it('reserves only the painted part of a panel inside the scrolling sidebar', () => {
  document.body.innerHTML =
    '<aside style="overflow-y:auto"><div></div></aside>';
  const rail = document.querySelector('aside')!;
  const panel = rail.firstElementChild!;
  vi.spyOn(rail, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, 500, 366, 250)
  );
  vi.spyOn(panel, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, -300, 366, 1200)
  );
  expect(
    visibleOverviewOverlayBounds(panel, new DOMRect(0, 65, 390, 779))
  ).toEqual({ x: 12, y: 435, width: 366, height: 250 });
});

it('ignores a panel scrolled completely out of the visible rail', () => {
  document.body.innerHTML =
    '<aside style="overflow-y:auto"><div></div></aside>';
  const rail = document.querySelector('aside')!;
  const panel = rail.firstElementChild!;
  vi.spyOn(rail, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, 500, 366, 250)
  );
  vi.spyOn(panel, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, 100, 366, 100)
  );
  expect(
    visibleOverviewOverlayBounds(panel, new DOMRect(0, 65, 390, 779))
  ).toBeNull();
});
