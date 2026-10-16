import { useEffect, useRef, type ReactNode } from 'react';
import type { OverviewCameraIntent } from './overview-camera-frame';
interface Props {
  children?: ReactNode;
  exploring: boolean;
  intent: OverviewCameraIntent;
  followUnavailable: string | null;
  onExploreChange: (exploring: boolean) => void;
  onReset: () => void;
}
export function OverviewMapControls({
  children,
  exploring,
  intent,
  followUnavailable,
  onExploreChange,
  onReset,
}: Props) {
  const toggle = useRef<HTMLButtonElement>(null);
  const wasExploring = useRef(false);
  useEffect(() => {
    if (wasExploring.current && !exploring)
      toggle.current?.focus({ preventScroll: true });
    wasExploring.current = exploring;
    if (!exploring) return;
    const exit = () => {
      onExploreChange(false);
      toggle.current?.focus({ preventScroll: true });
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        exit();
      }
    };
    window.addEventListener('keydown', key);
    window.addEventListener('blur', exit);
    return () => {
      window.removeEventListener('keydown', key);
      window.removeEventListener('blur', exit);
    };
  }, [exploring, onExploreChange]);
  return (
    <div className="overview-map-controls" aria-label="Map interaction">
      <div
        className="overview-map-toolbar"
        role="group"
        aria-label="Map actions"
      >
        <button
          ref={toggle}
          type="button"
          aria-label={exploring ? 'Exit map exploration' : 'Explore map'}
          title={exploring ? 'Exit map exploration' : 'Explore map'}
          aria-pressed={exploring}
          onClick={() => onExploreChange(!exploring)}
        >
          {exploring ? 'Exit' : 'Explore'}
        </button>
        <button
          type="button"
          aria-label="Reset map view"
          title="Reset map view"
          onClick={onReset}
        >
          Reset
        </button>
        {children}
      </div>
      {intent === 'overview' && <p role="status">Route overview</p>}
      {intent === 'follow' && (
        <p role="status" id="overview-follow-status">
          {followUnavailable
            ? `Follow paused · ${followUnavailable}`
            : 'Following aircraft'}
        </p>
      )}
    </div>
  );
}
