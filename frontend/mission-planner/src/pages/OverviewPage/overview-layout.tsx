import { createContext, useContext, useEffect, useState } from 'react';

export type OverviewLayoutMode = 'mobile' | 'tablet' | 'desktop' | 'wide';

type LayoutMediaListener = (event: MediaQueryListEvent) => void;
type ModernMediaQueryList = {
  readonly addEventListener: (
    type: 'change',
    listener: LayoutMediaListener
  ) => void;
  readonly removeEventListener: (
    type: 'change',
    listener: LayoutMediaListener
  ) => void;
};
type LegacyMediaQueryList = MediaQueryList & {
  readonly addListener: (listener: LayoutMediaListener) => void;
  readonly removeListener: (listener: LayoutMediaListener) => void;
};

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

export const OverviewLayoutContext = createContext<OverviewLayoutMode | null>(
  null
);

function subscribeLayoutQuery(
  query: MediaQueryList,
  listener: LayoutMediaListener
): () => void {
  const modernQuery = query as Partial<ModernMediaQueryList>;
  if (
    typeof modernQuery.addEventListener === 'function' &&
    typeof modernQuery.removeEventListener === 'function'
  ) {
    const add = modernQuery.addEventListener;
    const remove = modernQuery.removeEventListener;
    add('change', listener);
    return () => remove('change', listener);
  }
  const legacyQuery = query as Partial<LegacyMediaQueryList>;
  if (
    typeof legacyQuery.addListener === 'function' &&
    typeof legacyQuery.removeListener === 'function'
  ) {
    const add = legacyQuery.addListener;
    const remove = legacyQuery.removeListener;
    add(listener);
    return () => remove(listener);
  }
  return () => {};
}

function useLocalOverviewLayoutMode(enabled: boolean): OverviewLayoutMode {
  const [mode, setMode] = useState(currentLayoutMode);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
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
    const cleanup = queries.map((query) => subscribeLayoutQuery(query, update));
    return () => {
      cleanup.forEach((unsubscribe) => unsubscribe());
    };
  }, [enabled]);

  return mode;
}

export function useOverviewLayoutMode(): OverviewLayoutMode {
  const sharedMode = useContext(OverviewLayoutContext);
  const localMode = useLocalOverviewLayoutMode(sharedMode === null);
  return sharedMode ?? localMode;
}
