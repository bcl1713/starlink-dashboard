import { useLayoutEffect, useState, type RefObject } from 'react';
import {
  resolveOverviewLayout,
  type OverviewLayoutMode,
  type OverviewSafeRect,
} from './overview-responsive-layout';

interface Layout {
  mode: OverviewLayoutMode;
  flow: boolean;
  safeRect: OverviewSafeRect;
  revision: number;
}
/** Observe the bounded shell; growing scroll content cannot change eligibility. */
export function useOverviewLayout(
  pageRef: RefObject<HTMLElement | null>,
  stageRef: RefObject<HTMLDivElement | null>,
  contentKey: string
): Layout {
  const [layout, setLayout] = useState<Layout>({
    mode: 'desktop',
    flow: false,
    safeRect: { x: 0, y: 0, width: 0, height: 0 },
    revision: 0,
  });
  useLayoutEffect(() => {
    const page = pageRef.current,
      stage = stageRef.current,
      host = page?.parentElement;
    if (!page || !stage || !host || typeof ResizeObserver === 'undefined')
      return;
    let frame = 0,
      blocked = false,
      previousInput = '';
    const measure = () => {
      frame = 0;
      const width = host.clientWidth,
        height = host.clientHeight;
      if (!width || !height) return;
      const rootFontSize =
        parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      const input = `${width}/${height}/${rootFontSize}/${contentKey}`;
      if (input !== previousInput) {
        blocked = false;
        previousInput = input;
      }
      const clock = page.querySelector<HTMLElement>('.overview-top-overlays');
      const arrival = page.querySelector<HTMLElement>('.overview-arrival');
      const clockHeight =
        page
          .querySelector<HTMLElement>('.operational-clock')
          ?.getBoundingClientRect().height ??
        clock?.getBoundingClientRect().height ??
        56;
      const overlayHeight = arrival?.getBoundingClientRect().height ?? 90;
      const candidate = resolveOverviewLayout({
        width,
        height,
        rootFontSize,
        clockHeight,
        overlayHeight,
      });
      const current = page.dataset.layout;
      const expanded = Boolean(
        page.querySelector('.globe-legend button[aria-expanded="true"]')
      );
      if (
        candidate === 'landscape' &&
        (expanded ||
          (current === candidate &&
            stage.clientHeight - overlayHeight - 24 <
              120 * Math.max(1, rootFontSize / 16)))
      )
        blocked = true;
      const mode = blocked ? 'stacked' : candidate;
      const rightHeight =
        page
          .querySelector<HTMLElement>('.overview-right-overlays')
          ?.getBoundingClientRect().height ?? 0;
      const flow =
        mode === 'stacked' &&
        (overlayHeight > 160 ||
          rightHeight > 180 ||
          expanded ||
          rootFontSize > 20);
      const stageWidth = stage.clientWidth;
      const stageHeight = flow ? 360 : stage.clientHeight;
      const rightWidth =
        mode === 'desktop'
          ? 360
          : (page.querySelector<HTMLElement>('.overview-satellite-overlays')
              ?.offsetWidth ?? 144) + 24;
      const safeRect = {
        x: 12,
        y: 12,
        width: Math.max(1, stageWidth - rightWidth - 12),
        height: Math.max(1, stageHeight - (flow ? 24 : overlayHeight + 24)),
      };
      setLayout((previous) => {
        if (
          previous.mode === mode &&
          previous.flow === flow &&
          JSON.stringify(previous.safeRect) === JSON.stringify(safeRect)
        )
          return previous;
        return { mode, flow, safeRect, revision: previous.revision + 1 };
      });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    const observer = new ResizeObserver(schedule);
    [
      host,
      stage,
      clockNode(page),
      ...page.querySelectorAll<HTMLElement>(
        '.overview-arrival, .overview-planned-satellite, .globe-legend'
      ),
    ].forEach((node) => {
      if (node) observer.observe(node);
    });
    const mutations = new MutationObserver(schedule);
    mutations.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['style', 'class'],
    });
    mutations.observe(page, {
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-expanded'],
    });
    window.addEventListener('resize', schedule);
    measure();
    return () => {
      observer.disconnect();
      mutations.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', schedule);
    };
  }, [pageRef, stageRef, contentKey]);
  return layout;
}
function clockNode(page: HTMLElement) {
  return page.querySelector<HTMLElement>('.overview-top-overlays');
}
