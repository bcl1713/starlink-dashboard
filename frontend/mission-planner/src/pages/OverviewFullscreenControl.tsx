import { Maximize } from 'lucide-react';
import { useDocumentFullscreen } from '@/hooks/useDocumentFullscreen';
export function OverviewFullscreenControl() {
  const isFullscreen = useDocumentFullscreen();
  if (isFullscreen) {
    return null;
  }
  const enterFullscreen = () => {
    const requestFullscreen = document.documentElement.requestFullscreen;
    if (typeof requestFullscreen !== 'function') {
      return;
    }
    void requestFullscreen
      .call(document.documentElement)
      .catch(() => undefined);
  };
  return (
    <button
      type="button"
      className="overview-fullscreen-control"
      aria-label="Enter fullscreen overview"
      onClick={enterFullscreen}
    >
      <Maximize aria-hidden="true" size={18} />
      <span>Fullscreen</span>
    </button>
  );
}
