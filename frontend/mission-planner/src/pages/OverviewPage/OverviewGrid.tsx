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
  const mountedRef = useRef(false);
  const attemptRef = useRef<{
    readonly id: number;
    readonly target: HTMLElement;
  } | null>(null);
  const generationRef = useRef(0);
  const staleErrorDebtRef = useRef(0);
  const ownsNativeRef = useRef(false);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    mountedRef.current = true;
    const root = ownerDocument.documentElement;
    const enterKiosk = (target: HTMLElement | null) => {
      if (!mountedRef.current) return;
      root.classList.add('overview-kiosk-active');
      ownsNativeRef.current = false;
      setMode('kiosk');
      setFallbackMessage(FULLSCREEN_FALLBACK_MESSAGE);
      target?.focus();
    };
    const onChange = () => {
      const target = targetRef.current;
      const fullscreenElement = ownerDocument.fullscreenElement;
      if (fullscreenElement === target && target) {
        attemptRef.current = null;
        ownsNativeRef.current = true;
        root.classList.remove('overview-kiosk-active');
        setMode('native');
        setFallbackMessage(null);
        target.focus();
        return;
      }
      if (fullscreenElement) return;
      if (!ownsNativeRef.current) return;
      ownsNativeRef.current = false;
      root.classList.remove('overview-kiosk-active');
      setMode('inline');
      setFallbackMessage(null);
      if (target) restoreFocus(triggerRef.current, target);
    };
    const onError = () => {
      if (staleErrorDebtRef.current > 0) {
        staleErrorDebtRef.current -= 1;
        return;
      }
      const attempt = attemptRef.current;
      if (!attempt) return;
      attemptRef.current = null;
      enterKiosk(attempt.target);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || modeRef.current !== 'kiosk') return;
      const target = targetRef.current;
      root.classList.remove('overview-kiosk-active');
      ownsNativeRef.current = false;
      attemptRef.current = null;
      setMode('inline');
      setFallbackMessage(null);
      if (target) restoreFocus(triggerRef.current, target);
    };
    ownerDocument.addEventListener('fullscreenchange', onChange);
    ownerDocument.addEventListener('fullscreenerror', onError);
    ownerDocument.addEventListener('keydown', onKeyDown);
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      attemptRef.current = null;
      staleErrorDebtRef.current = 0;
      ownsNativeRef.current = false;
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
        ownsNativeRef.current = false;
        attemptRef.current = null;
        setMode('kiosk');
        setFallbackMessage(FULLSCREEN_FALLBACK_MESSAGE);
        target?.focus();
        return;
      }
      const id = generationRef.current + 1;
      if (attemptRef.current) staleErrorDebtRef.current += 1;
      generationRef.current = id;
      attemptRef.current = { id, target };
      try {
        await target.requestFullscreen();
      } catch {
        if (attemptRef.current?.id !== id || !mountedRef.current) {
          if (staleErrorDebtRef.current > 0) staleErrorDebtRef.current -= 1;
          return;
        }
        attemptRef.current = null;
        ownerDocument.documentElement.classList.add('overview-kiosk-active');
        ownsNativeRef.current = false;
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
      attemptRef.current = null;
      ownsNativeRef.current = false;
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
      className={`overview-primary-grid overview-primary-grid--${mode}`}
      data-layout-mode={mode}
      data-testid="overview-grid"
    >
      <section
        className="overview-map-panel"
        aria-label="Current Position"
        aria-labelledby="current-position-heading"
      >
        <h2 id="current-position-heading" className="sr-only">
          Current Position
        </h2>
        <div className="overview-map-region">{props.map}</div>
      </section>
      <section
        className="overview-summary-region"
        aria-label="Operational summaries"
        aria-labelledby="operational-summaries-heading"
      >
        <h2 id="operational-summaries-heading" className="sr-only">
          Operational summaries
        </h2>
        {props.groundEntryPoint}
        {props.obstruction}
        {props.packetLoss}
      </section>
      <section
        className="overview-right-rail"
        aria-label="Operations right rail"
      >
        <section className="overview-poi-region">
          {props.poiQuickReference}
        </section>
        <section className="overview-latency-region">{props.latency}</section>
        <section className="overview-throughput-region">
          {props.throughput}
        </section>
      </section>
    </div>
  );
}
