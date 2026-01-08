import { useEffect, useState, useRef, useCallback } from 'react';
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

  const [preview, setPreview] = useState<Timeline | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const calculatePreview = useCallback(
    async (previewRequest: TimelinePreviewRequest) => {
      // Cancel previous request if in flight
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();
      setIsCalculating(true);
      setError(null);

      const result = await timelineService.previewTimeline(
        missionId,
        legId,
        previewRequest,
        abortControllerRef.current.signal
      );

      if (result) {
        setPreview(result);
      } else {
        setError(new Error('Failed to calculate preview'));
      }
      setIsCalculating(false);
    },
    [missionId, legId]
  );

  useEffect(() => {
    if (!enabled || !request || !missionId || !legId) {
      return;
    }

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new debounce timer
    debounceTimerRef.current = setTimeout(() => {
      calculatePreview(request);
    }, debounceMs);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [request, missionId, legId, enabled, debounceMs, calculatePreview]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return {
    preview,
    isCalculating,
    error,
  };
}
