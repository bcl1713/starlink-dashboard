import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createOverviewDisplaySession } from '@/services/overview-display-session';

export interface DisplayHostState {
  label: string | null;
}
export function useOverviewDisplayHost(
  onRecenter: () => void,
  onFollow?: () => boolean
): DisplayHostState {
  const resetRef = useRef(onRecenter);
  const followRef = useRef(onFollow);
  const [label, setLabel] = useState<string | null>(null);
  useLayoutEffect(() => {
    resetRef.current = onRecenter;
    followRef.current = onFollow;
  }, [onRecenter, onFollow]);
  useEffect(() => {
    let disposed = false;
    let available = false;
    const session = createOverviewDisplaySession({
      role: 'display',
      onSnapshot: (snapshot) => {
        available = snapshot.available;
        if (!available) setLabel(null);
      },
      readPeer: () => ({
        actions: followRef.current
          ? ['recenter', 'follow_aircraft']
          : ['recenter'],
      }),
      onCommand: async (action, expiresAtMs) => {
        if (disposed || Date.now() >= expiresAtMs) return 'expired';
        if (action === 'follow_aircraft')
          return followRef.current?.() ? 'accepted' : 'unsupported';
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
