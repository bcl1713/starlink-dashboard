import { useEffect, useRef } from 'react';
import type { OverviewCameraIntent } from './overview-camera-frame';
interface Props {
  exploring: boolean;
  intent: OverviewCameraIntent;
  followUnavailable: string | null;
  onExploreChange: (exploring: boolean) => void;
  onReset: () => void;
}
export function OverviewMapControls({
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
      <button
        ref={toggle}
        type="button"
        aria-pressed={exploring}
        onClick={() => onExploreChange(!exploring)}
      >
        {exploring ? 'Exit map exploration' : 'Explore map'}
      </button>
      <button type="button" onClick={onReset}>
        Reset map view
      </button>
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
