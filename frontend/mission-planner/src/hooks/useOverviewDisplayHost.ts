import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createOverviewDisplaySession } from '@/services/overview-display-session';

export interface DisplayHostState {
  label: string | null;
}
export function useOverviewDisplayHost(
  onRecenter: () => void
): DisplayHostState {
  const resetRef = useRef(onRecenter);
  const [label, setLabel] = useState<string | null>(null);
  useLayoutEffect(() => {
    resetRef.current = onRecenter;
  }, [onRecenter]);
  useEffect(() => {
    let disposed = false;
    let available = false;
    const session = createOverviewDisplaySession({
      role: 'display',
      onSnapshot: (snapshot) => {
        available = snapshot.available;
        if (!available) setLabel(null);
      },
      readPeer: () => ({ actions: ['recenter'] }),
      onCommand: async (_action, expiresAtMs) => {
        if (disposed || Date.now() >= expiresAtMs) return 'expired';
        resetRef.current();
        return 'accepted';
      },
    });
    if (available) setLabel(session.label);
    return () => {
      disposed = true;
      session.close();
    };
  }, []);
  return { label };
}
