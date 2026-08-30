import type { OverviewVisibility } from './overview-data-types';

export function defaultVisibility(): OverviewVisibility {
  return {
    isHidden: () =>
      typeof document === 'undefined' ? false : document.hidden === true,
    subscribe(listener: () => void) {
      if (typeof document === 'undefined') return () => {};
      document.addEventListener('visibilitychange', listener);
      return () => document.removeEventListener('visibilitychange', listener);
    },
  };
}

export function safeHidden(
  visibility: OverviewVisibility | undefined
): boolean {
  try {
    return visibility?.isHidden() ?? false;
  } catch {
    return false;
  }
}
