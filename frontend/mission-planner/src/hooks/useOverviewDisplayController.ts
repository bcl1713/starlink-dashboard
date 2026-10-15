import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  DisplayAction,
  DisplaySnapshot,
} from '@/services/overview-display-protocol';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from '@/services/overview-display-session';

export interface DisplayControllerState extends DisplaySnapshot {
  send(targetId: string, action: DisplayAction): string | null;
}

export function useOverviewDisplayController(): DisplayControllerState {
  const sessionRef = useRef<OverviewDisplaySession | null>(null);
  const [snapshot, setSnapshot] = useState<DisplaySnapshot>({
    available: false,
    peers: [],
    feedback: null,
  });
  useEffect(() => {
    const session = createOverviewDisplaySession({
      role: 'controller',
      onSnapshot: setSnapshot,
    });
    sessionRef.current = session;
    return () => {
      sessionRef.current = null;
      session.close();
    };
  }, []);
  const send = useCallback(
    (targetId: string, action: DisplayAction) =>
      sessionRef.current?.request(targetId, action) ?? null,
    []
  );
  return { ...snapshot, send };
}
