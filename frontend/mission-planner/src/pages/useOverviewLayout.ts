import { useLayoutEffect, useRef, useState, type RefObject } from 'react';
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
/** Observe the bounded shell; growing scroll content cannot change eligibility. */
export function useOverviewLayout(
  pageRef: RefObject<HTMLElement | null>,
  stageRef: RefObject<HTMLDivElement | null>,
  contentKey: string,
  contentReady: boolean
): Layout {
  const fullscreen = useDocumentFullscreen();
  const flowLatch = useRef({ geometry: '', required: false, ready: false });
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
      // Scrollbars change client dimensions as the flow fallback expands.
      // Reset the latch only when the bounded frame itself changes size.
      const geometry = `${host.offsetWidth}/${host.offsetHeight}/${rootFontSize}`;
      if (
        geometry !== flowLatch.current.geometry ||
        (contentReady && !flowLatch.current.ready)
      ) {
        flowLatch.current = { geometry, required: false, ready: contentReady };
      }
      flowLatch.current.ready = contentReady;
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
        overflow: flowLatch.current.required,
        fullscreen,
      });
      const current = page.dataset.layout;
      if (candidate === 'desktop' && current === 'desktop' && contentReady) {
        const pageBounds = page.getBoundingClientRect();
        const panels = [
          ...page.querySelectorAll<HTMLElement>(
            '.operational-clock, .overview-clock-panel--message, .overview-metric-history, .overview-metric-history-panels__header, .overview-planned-satellite, .globe-legend, .overview-map-status, .overview-arrival, .overview-display-controls, .overview-map-controls'
          ),
        ].filter((node) => node.getBoundingClientRect().height > 0);
        const bounds = panels.map((node) => node.getBoundingClientRect());
        const doesNotFit = panels.some((node, index) => {
          const box = bounds[index];
          return (
            node.scrollHeight > node.clientHeight + 1 ||
            node.scrollWidth > node.clientWidth + 1 ||
            box.left < pageBounds.left - 1 ||
            box.right > pageBounds.right + 1 ||
            box.top < pageBounds.top - 1 ||
            box.bottom > pageBounds.bottom + 1
          );
        });
        const overlaps = bounds.some((a, index) =>
          bounds
            .slice(index + 1)
            .some(
              (b) =>
                a.left < b.right - 1 &&
                a.right > b.left + 1 &&
                a.top < b.bottom - 1 &&
                a.bottom > b.top + 1
            )
        );
        const clearHeight =
          (arrival?.getBoundingClientRect().top ?? pageBounds.bottom) -
          (clock?.getBoundingClientRect().bottom ?? pageBounds.top) -
          40;
        if (
          doesNotFit ||
          overlaps ||
          clearHeight < 120 * Math.max(1, rootFontSize / 16)
        ) {
          blocked = true;
          flowLatch.current.required = true;
        }
      }
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
      const rightHeight =
        page
          .querySelector<HTMLElement>('.overview-right-overlays')
          ?.getBoundingClientRect().height ?? 0;
      if (
        candidate === 'landscape' &&
        current === candidate &&
        rightHeight + overlayHeight + 24 > stage.clientHeight
      )
        blocked = true;
      const mode = blocked ? 'stacked' : candidate;
      if (
        contentReady &&
        mode === 'stacked' &&
        (overlayHeight > 160 ||
          rightHeight > 180 ||
          expanded ||
          rootFontSize > 20)
      )
        flowLatch.current.required = true;
      const flow = mode === 'stacked' && flowLatch.current.required;
      const stageWidth = stage.clientWidth;
      const stageHeight = flow ? 360 : stage.clientHeight;
      const rightWidth =
        mode === 'desktop'
          ? 360
          : (page.querySelector<HTMLElement>('.overview-satellite-overlays')
              ?.offsetWidth ?? 144) + 24;
      const leftWidth = page.querySelector('.overview-metrics-overlays')
        ? 480
        : 20;
      let safeRect =
        mode === 'desktop'
          ? {
              x: leftWidth,
              y: 136,
              width: Math.max(1, stageWidth - leftWidth - 360),
              height: Math.max(1, stageHeight - overlayHeight - 156),
            }
          : {
              x: 12,
              y: 12,
              width: Math.max(1, stageWidth - (flow ? 24 : rightWidth + 12)),
              height: Math.max(
                1,
                stageHeight - (flow ? 24 : overlayHeight + 24)
              ),
            };
      if (mode === 'landscape') {
        // Compact controls share the satellite's upper band, extending left
        // into the opening that the satellite width alone would reserve.
        const controls = page
          .querySelector('.overview-map-controls')
          ?.getBoundingClientRect();
        if (controls && controls.width > 0)
          safeRect.width = Math.max(
            1,
            Math.min(
              safeRect.width,
              controls.left -
                stage.getBoundingClientRect().left -
                safeRect.x -
                20
            )
          );
      }
      if (mode === 'desktop' && fullscreen) {
        const stageBounds = stage.getBoundingClientRect();
        const metrics = page
          .querySelector('.overview-metrics-overlays')
          ?.getBoundingClientRect();
        const upper = [
          ...page.querySelectorAll(
            '.overview-satellite-overlays, .overview-map-controls'
          ),
        ]
          .map((node) => node.getBoundingClientRect())
          .filter((box) => box.height > 0);
        const lower = page
          .querySelector('.overview-map-overlays')
          ?.getBoundingClientRect();
        const x = (metrics?.right ?? stageBounds.left) - stageBounds.left + 20;
        const y =
          Math.max(
            clock?.getBoundingClientRect().bottom ?? stageBounds.top + 116,
            ...upper.map((box) => box.bottom)
          ) -
          stageBounds.top +
          20;
        const bottom =
          Math.min(
            arrival?.getBoundingClientRect().top ?? stageBounds.bottom - 20,
            lower?.top ?? stageBounds.bottom - 20
          ) -
          stageBounds.top -
          20;
        safeRect = {
          x,
          y,
          width: Math.max(1, stageWidth - x - 20),
          height: Math.max(1, bottom - y),
        };
      }
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
        '.overview-arrival, .overview-planned-satellite, .globe-legend, .overview-map-controls, .overview-display-controls, .overview-right-overlays, .overview-metric-history, .overview-metric-history-panels__header'
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
  }, [pageRef, stageRef, contentKey, contentReady, fullscreen]);
  return layout;
}
function clockNode(page: HTMLElement) {
  return page.querySelector<HTMLElement>('.overview-top-overlays');
}
