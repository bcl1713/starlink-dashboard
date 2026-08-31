/* eslint-disable react-refresh/only-export-components */
import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react';

export type OverviewLayoutMode = 'mobile' | 'tablet' | 'desktop' | 'wide';
export type OverviewFullscreenMode = 'inline' | 'native' | 'kiosk';

export interface OverviewGridProps {
  readonly map: ReactNode;
  readonly groundEntryPoint: ReactNode;
  readonly obstruction: ReactNode;
  readonly packetLoss: ReactNode;
  readonly poiQuickReference: ReactNode;
  readonly latency: ReactNode;
  readonly throughput: ReactNode;
}

export interface OverviewFullscreenController {
  readonly mode: OverviewFullscreenMode;
  readonly fallbackMessage: string | null;
  readonly enterFromUserGesture: () => Promise<void>;
  readonly exitFromUserGesture: () => Promise<void>;
}

function layoutMode(width: number): OverviewLayoutMode {
  if (width >= 1536) return 'wide';
  if (width >= 1024) return 'desktop';
  if (width >= 768) return 'tablet';
  return 'mobile';
}

function currentLayoutMode(): OverviewLayoutMode {
  if (typeof window === 'undefined') return 'desktop';
  return layoutMode(window.innerWidth);
}

export function useOverviewLayoutMode(): OverviewLayoutMode {
  const [mode, setMode] = useState(currentLayoutMode);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const queries = [
      window.matchMedia('(min-width: 1536px)'),
      window.matchMedia('(min-width: 1024px) and (max-width: 1535px)'),
      window.matchMedia('(min-width: 768px) and (max-width: 1023px)'),
      window.matchMedia('(max-width: 767px)'),
    ];
    const update = () => {
      if (queries[0].matches) setMode('wide');
      else if (queries[1].matches) setMode('desktop');
      else if (queries[2].matches) setMode('tablet');
      else setMode('mobile');
    };

    update();
    for (const query of queries) {
      query.addEventListener('change', update);
    }
    return () => {
      for (const query of queries) {
        query.removeEventListener('change', update);
      }
    };
  }, []);

  return mode;
}

function restoreFocus(
  trigger: HTMLButtonElement | null,
  fallback: HTMLElement
): void {
  if (trigger?.isConnected) {
    trigger.focus();
    return;
  }
  const heading = fallback.querySelector<HTMLElement>('#overview-title');
  (heading ?? fallback).focus();
}

const FULLSCREEN_FALLBACK_MESSAGE =
  'Fullscreen unavailable — using kiosk view.';

export function useOverviewFullscreen(
  targetRef: RefObject<HTMLElement | null>,
  triggerRef: RefObject<HTMLButtonElement | null>,
  ownerDocument: Document = document
): OverviewFullscreenController {
  const [mode, setMode] = useState<OverviewFullscreenMode>('inline');
  const [fallbackMessage, setFallbackMessage] = useState<string | null>(null);
  const modeRef = useRef(mode);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const target = targetRef.current;
    const root = ownerDocument.documentElement;
    const onChange = () => {
      if (ownerDocument.fullscreenElement === target && target) {
        setMode('native');
        target.focus();
        return;
      }
      root.classList.remove('overview-kiosk-active');
      setMode('inline');
      setFallbackMessage(null);
      if (target) restoreFocus(triggerRef.current, target);
    };
    const onError = () => {
      root.classList.add('overview-kiosk-active');
      setMode('kiosk');
      setFallbackMessage(FULLSCREEN_FALLBACK_MESSAGE);
      target?.focus();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || modeRef.current !== 'kiosk') return;
      root.classList.remove('overview-kiosk-active');
      setMode('inline');
      setFallbackMessage(null);
      if (target) restoreFocus(triggerRef.current, target);
    };
    ownerDocument.addEventListener('fullscreenchange', onChange);
    ownerDocument.addEventListener('fullscreenerror', onError, { once: true });
    ownerDocument.addEventListener('keydown', onKeyDown);
    return () => {
      ownerDocument.removeEventListener('fullscreenchange', onChange);
      ownerDocument.removeEventListener('fullscreenerror', onError);
      ownerDocument.removeEventListener('keydown', onKeyDown);
      root.classList.remove('overview-kiosk-active');
    };
  }, [ownerDocument, targetRef, triggerRef]);

  return {
    mode,
    fallbackMessage,
    enterFromUserGesture: async () => {
      const target = targetRef.current;
      if (!target?.requestFullscreen) {
        ownerDocument.documentElement.classList.add('overview-kiosk-active');
        setMode('kiosk');
        setFallbackMessage(FULLSCREEN_FALLBACK_MESSAGE);
        target?.focus();
        return;
      }
      try {
        await target.requestFullscreen();
      } catch {
        ownerDocument.documentElement.classList.add('overview-kiosk-active');
        setMode('kiosk');
        setFallbackMessage(FULLSCREEN_FALLBACK_MESSAGE);
        target.focus();
      }
    },
    exitFromUserGesture: async () => {
      const target = targetRef.current;
      if (ownerDocument.fullscreenElement === target) {
        await ownerDocument.exitFullscreen?.();
        return;
      }
      ownerDocument.documentElement.classList.remove('overview-kiosk-active');
      setMode('inline');
      setFallbackMessage(null);
      if (target) restoreFocus(triggerRef.current, target);
    },
  };
}

export function OverviewGrid(props: OverviewGridProps) {
  const mode = useOverviewLayoutMode();

  return (
    <div
      className={`overview-grid overview-grid--${mode}`}
      data-layout-mode={mode}
      data-testid="overview-grid"
    >
      <section className="overview-map-panel" aria-label="Current Position">
        <div className="overview-map-region">{props.map}</div>
      </section>
      <section
        className="overview-summary-strip"
        aria-label="Operational summaries"
      >
        {props.groundEntryPoint}
        {props.obstruction}
        {props.packetLoss}
      </section>
      <section className="overview-poi-region" aria-label="POI Quick Reference">
        {props.poiQuickReference}
      </section>
      <section className="overview-latency-region" aria-label="Network Latency">
        {props.latency}
      </section>
      <section className="overview-throughput-region" aria-label="Throughput">
        {props.throughput}
      </section>
    </div>
  );
}
