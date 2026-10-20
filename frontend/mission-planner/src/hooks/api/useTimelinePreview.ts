import { useEffect, useState } from 'react';
import {
  timelineService,
  type Timeline,
  type TimelinePreviewRequest,
} from '../../services/timeline';
interface UseTimelinePreviewOptions {
  debounceMs?: number;
  enabled?: boolean;
}

export function useTimelinePreview(
  missionId: string,
  legId: string,
  request: TimelinePreviewRequest | null,
  options: UseTimelinePreviewOptions = {}
) {
  const { debounceMs = 500, enabled = true } = options;
  const [result, setResult] = useState<{
    missionId: string;
    legId: string;
    request: TimelinePreviewRequest | null;
    preview: Timeline | null;
    error: Error | null;
  } | null>(null);
  useEffect(() => {
    if (!enabled || !request || !missionId || !legId) return;
    let current = true;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      const preview = await timelineService.previewTimeline(
        missionId,
        legId,
        request,
        controller.signal
      );
      // An HTTP adapter may finish despite abort. Only this input generation owns publication.
      if (!current) return;
      setResult({
        missionId,
        legId,
        request,
        preview,
        error: preview ? null : new Error('Failed to calculate preview'),
      });
    }, debounceMs);
    return () => {
      current = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [missionId, legId, request, enabled, debounceMs]);
  const matches =
    enabled &&
    request &&
    result?.missionId === missionId &&
    result?.legId === legId &&
    result?.request === request;
  return {
    preview: matches ? result.preview : null,
    isCalculating: Boolean(
      enabled && request && missionId && legId && !matches
    ),
    error: matches ? result.error : null,
  };
}
