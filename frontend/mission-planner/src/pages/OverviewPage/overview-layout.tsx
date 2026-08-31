/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

export type OverviewLayoutMode = 'mobile' | 'tablet' | 'desktop' | 'wide';

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

const OverviewLayoutContext = createContext<OverviewLayoutMode | null>(null);

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
    for (const query of queries) {
      query.addEventListener('change', update);
    }
    return () => {
      for (const query of queries) {
        query.removeEventListener('change', update);
      }
    };
  }, [enabled]);

  return mode;
}

export function OverviewLayoutProvider({
  children,
}: {
  readonly children: ReactNode;
}) {
  const mode = useLocalOverviewLayoutMode(true);

  return (
    <OverviewLayoutContext.Provider value={mode}>
      {children}
    </OverviewLayoutContext.Provider>
  );
}

export function useOverviewLayoutMode(): OverviewLayoutMode {
  const sharedMode = useContext(OverviewLayoutContext);
  const localMode = useLocalOverviewLayoutMode(sharedMode === null);
  return sharedMode ?? localMode;
}
