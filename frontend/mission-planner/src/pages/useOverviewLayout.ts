import { useLayoutEffect, useState, type RefObject } from 'react';
import { useDocumentFullscreen } from '@/hooks/useDocumentFullscreen';
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

/** Composition depends on the bounded shell, never on disclosure content. */
export function useOverviewLayout(
  pageRef: RefObject<HTMLElement | null>,
  stageRef: RefObject<HTMLDivElement | null>,
  contentKey: string,
  contentReady: boolean,
  visibilityKey = ''
): Layout {
  const fullscreen = useDocumentFullscreen();
  const [layout, setLayout] = useState<Layout>({
    mode: 'stacked',
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
    let frame = 0;
    const measure = () => {
      frame = 0;
      if (!host.clientWidth || !host.clientHeight) return;
      const rootFontSize =
        parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      const mode = resolveOverviewLayout({
        width: host.clientWidth,
        height: host.clientHeight,
        rootFontSize,
        clockHeight: 0,
        overlayHeight: 0,
      });
      // The canvas fills the dashboard; panel-free bounds determine camera fit.
      const globe = page.querySelector<HTMLElement>('.overview-globe');
      const bounds = (globe ?? stage).getBoundingClientRect();
      const padding = mode === 'desktop' ? 20 : 12;
      let left = padding,
        top = padding,
        right = bounds.width - padding,
        bottom = bounds.height - padding;
      const overlappingPanel = (selector: string) => {
        const box = page.querySelector(selector)?.getBoundingClientRect();
        return box &&
          box.width > 0 &&
          box.height > 0 &&
          box.left < bounds.right &&
          box.right > bounds.left &&
          box.top < bounds.bottom &&
          box.bottom > bounds.top
          ? box
          : null;
      };
      const fixedClock = overlappingPanel('.overview-top-overlays');
      const fixedArrival = overlappingPanel('.overview-arrival-overlays');
      if (fixedClock)
        top = Math.max(top, fixedClock.bottom - bounds.top + padding);
      if (fixedArrival)
        bottom = Math.min(bottom, fixedArrival.top - bounds.top - padding);
      const opening = page
        .querySelector('.overview-map-opening')
        ?.getBoundingClientRect();
      if (mode !== 'desktop' && opening && opening.width > 0) {
        left = Math.max(padding, opening.left - bounds.left + padding);
        top = Math.max(padding, opening.top - bounds.top + padding);
        right = Math.min(
          bounds.width - padding,
          opening.right - bounds.left - padding
        );
        bottom = Math.min(
          bounds.height - padding,
          opening.bottom - bounds.top - padding
        );
      }
      if (mode === 'desktop') {
        const panel = (selector: string) => {
          const box = page.querySelector(selector)?.getBoundingClientRect();
          return box && box.width > 0 && box.height > 0 ? box : null;
        };
        const metrics = panel('.overview-metrics-overlays');
        const clock = panel('.overview-top-overlays');
        // Corner actions and display identity don't occupy an information rail.
        // Keep this content test in sync with OverviewOverlayLayout.css.
        const hasRightPanels = page.querySelector(
          '.overview-satellite-overlays, .overview-starshield-advisory, .overview-map-overlays > :not(.overview-display-label)'
        );
        const controls = hasRightPanels
          ? panel('.overview-right-overlays')
          : null;
        const arrival = panel('.overview-arrival-overlays');
        if (metrics)
          left = Math.max(left, metrics.right - bounds.left + padding);
        if (clock) top = Math.max(top, clock.bottom - bounds.top + padding);
        if (controls)
          right = Math.min(right, controls.left - bounds.left - padding);
        if (arrival)
          bottom = Math.min(bottom, arrival.top - bounds.top - padding);
        if (fullscreen) {
          // Preserve the large-screen route opening below the upper controls
          // and above the legend. It can extend right of the narrow center
          // strip while still keeping the whole framed route clear of panels.
          const upper = [
            ...page.querySelectorAll(
              '.overview-satellite-overlays, .overview-map-controls, .overview-display-controls'
            ),
          ]
            .map((node) => node.getBoundingClientRect())
            .filter((box) => box.width > 0 && box.height > 0);
          const wideTop = Math.max(
            top,
            ...upper.map((box) => box.bottom - bounds.top + padding)
          );
          const wideRight = bounds.width - padding;
          const lower = panel('.overview-map-overlays');
          const wideBottom = lower
            ? Math.min(bottom, lower.top - bounds.top - padding)
            : bottom;
          // A wider but shallow gap can force a dramatic zoom-out. Prefer the
          // opening with the larger limiting dimension for a readable globe.
          if (
            Math.min(wideRight - left, wideBottom - wideTop) >
            Math.min(right - left, bottom - top)
          ) {
            top = wideTop;
            right = wideRight;
            bottom = wideBottom;
          }
        }
      }
      const safeRect = {
        x: Math.max(0, Math.min(left, bounds.width - 1)),
        y: Math.max(0, Math.min(top, bounds.height - 1)),
        width: Math.max(1, right - left),
        height: Math.max(1, bottom - top),
      };
      setLayout((previous) => {
        if (
          previous.mode === mode &&
          JSON.stringify(previous.safeRect) === JSON.stringify(safeRect)
        )
          return previous;
        return { mode, flow: false, safeRect, revision: previous.revision + 1 };
      });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    const observer = new ResizeObserver(schedule);
    [
      host,
      stage,
      ...page.querySelectorAll<HTMLElement>(
        '.overview-map-opening, .overview-overlay-layout, .overview-globe, .overview-globe-viewport, .overview-top-overlays, .overview-arrival-overlays, .overview-sidebar, .overview-right-overlays, .overview-metrics-overlays'
      ),
    ].forEach((node) => observer.observe(node));
    const mutations = new MutationObserver(schedule);
    mutations.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['style', 'class'],
    });
    mutations.observe(page, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-expanded', 'data-layout'],
    });
    window.addEventListener('resize', schedule);
    document.addEventListener('fullscreenchange', schedule);
    measure();
    return () => {
      observer.disconnect();
      mutations.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', schedule);
      document.removeEventListener('fullscreenchange', schedule);
    };
  }, [pageRef, stageRef, contentKey, contentReady, visibilityKey, fullscreen]);
  return layout;
}
