import { useEffect, useState } from 'react';
function isDocumentFullscreen() {
  return document.fullscreenElement === document.documentElement;
}
export function useDocumentFullscreen() {
  const [isFullscreen, setIsFullscreen] = useState(isDocumentFullscreen);
  useEffect(() => {
    const updateFullscreenState = () => {
      setIsFullscreen(isDocumentFullscreen());
    };
    document.addEventListener('fullscreenchange', updateFullscreenState);
    return () => {
      document.removeEventListener('fullscreenchange', updateFullscreenState);
    };
  }, []);
  return isFullscreen;
}
