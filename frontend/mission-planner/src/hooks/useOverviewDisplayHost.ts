import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { DisplayResult } from '@/services/overview-display-protocol';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from '@/services/overview-display-session';
import { requestOverviewFullscreen } from '@/pages/overview-fullscreen';
import { useDocumentFullscreen } from './useDocumentFullscreen';

export interface DisplayHostState {
  label: string | null;
  fullscreenFeedback: DisplayResult | null;
}

export function useOverviewDisplayHost(
  onRecenter: () => void
): DisplayHostState {
  const resetRef = useRef(onRecenter);
  const sessionRef = useRef<OverviewDisplaySession | null>(null);
  const [label, setLabel] = useState<string | null>(null);
  const [fullscreenFeedback, setFullscreenFeedback] =
    useState<DisplayResult | null>(null);
  const isFullscreen = useDocumentFullscreen();
  const [previousFullscreen, setPreviousFullscreen] = useState(isFullscreen);
  if (previousFullscreen !== isFullscreen) {
    setPreviousFullscreen(isFullscreen);
    if (isFullscreen) setFullscreenFeedback(null);
  }
  useLayoutEffect(() => {
    resetRef.current = onRecenter;
  }, [onRecenter]);
  useEffect(() => {
    let disposed = false;
    let available = false;
    let fullscreenRevision = 0;
    const session = createOverviewDisplaySession({
      role: 'display',
      onSnapshot: (snapshot) => {
        available = snapshot.available;
        if (!available) setLabel(null);
      },
      readPeer: () => ({
        fullscreen: document.fullscreenElement === document.documentElement,
        actions: ['recenter', 'fullscreen'],
      }),
      onCommand: async (action, expiresAtMs) => {
        if (disposed || Date.now() >= expiresAtMs) return 'expired';
        if (action === 'recenter') {
          resetRef.current();
          return 'accepted';
        }
        const revision = ++fullscreenRevision;
        const result = await requestOverviewFullscreen();
        const status = Date.now() >= expiresAtMs ? 'expired' : result;
        if (!disposed && available && revision === fullscreenRevision) {
          setFullscreenFeedback(status);
          session.publishPresence();
        }
        return status;
      },
    });
    sessionRef.current = session;
    if (available) setLabel(session.label);
    return () => {
      disposed = true;
      sessionRef.current = null;
      session.close();
    };
  }, []);
  useEffect(() => {
    sessionRef.current?.publishPresence();
  }, [isFullscreen]);
  return { label, fullscreenFeedback };
}
