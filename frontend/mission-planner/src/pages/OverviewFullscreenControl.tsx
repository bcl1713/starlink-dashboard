import { Expand } from 'lucide-react';
import { useState } from 'react';
import { useDocumentFullscreen } from '@/hooks/useDocumentFullscreen';
import type { DisplayResult } from '@/services/overview-display-protocol';
import { requestOverviewFullscreen } from './overview-fullscreen';
export function OverviewFullscreenControl({
  feedback = null,
}: {
  feedback?: DisplayResult | null;
}) {
  const isFullscreen = useDocumentFullscreen();
  const [observed, setObserved] = useState({ feedback, isFullscreen });
  const [result, setResult] = useState(feedback);
  if (
    observed.feedback !== feedback ||
    observed.isFullscreen !== isFullscreen
  ) {
    setObserved({ feedback, isFullscreen });
    setResult(observed.isFullscreen !== isFullscreen ? null : feedback);
  }
  if (isFullscreen) {
    return null;
  }
  const enterFullscreen = () => {
    void requestOverviewFullscreen().then(setResult);
  };
  return (
    <div className="overview-fullscreen-controls">
      <button
        type="button"
        className="overview-fullscreen-control"
        aria-label="Enter fullscreen overview"
        onClick={enterFullscreen}
      >
        <Expand aria-hidden="true" size={20} />
        <span>Fullscreen</span>
      </button>
      {result && result !== 'accepted' && (
        <p role="status" className="overview-fullscreen-feedback">
          {result === 'unsupported'
            ? 'Fullscreen is unavailable in this browser. '
            : result === 'expired'
              ? 'Fullscreen request expired. '
              : ''}
          Click Fullscreen in the Overview window to finish.
        </p>
      )}
    </div>
  );
}
