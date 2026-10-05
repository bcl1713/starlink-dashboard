import { Expand } from 'lucide-react';
import { useState } from 'react';
import { useDocumentFullscreen } from '@/hooks/useDocumentFullscreen';
import type { FullscreenResult } from './overview-fullscreen';
import { requestOverviewFullscreen } from './overview-fullscreen';
export function OverviewFullscreenControl() {
  const isFullscreen = useDocumentFullscreen();
  const [previousFullscreen, setPreviousFullscreen] = useState(isFullscreen);
  const [result, setResult] = useState<FullscreenResult | null>(null);
  if (previousFullscreen !== isFullscreen) {
    setPreviousFullscreen(isFullscreen);
    setResult(null);
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
            : ''}
          Click Fullscreen in the Overview window to finish.
        </p>
      )}
    </div>
  );
}
