import { useEffect, useSyncExternalStore } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getRouteSigmetSource } from '@/pages/aviation-weather/route-sigmet-source';
import type { NoticeMutation, NoticeSelection } from '@/services/route-sigmets';
import { useAviationSettings } from './useAviationSettings';

/** Configuration and Overview subscribe to the same data owner. */
export function useRouteSigmets() {
  const source = getRouteSigmetSource(useQueryClient());
  const settings = useAviationSettings().data;
  const view = useSyncExternalStore(
    source.subscribe,
    source.snapshot,
    source.snapshot
  );
  useEffect(() => source.setSettings(settings), [source, settings]);
  return view;
}
export function useSetSigmetAcknowledgement() {
  const source = getRouteSigmetSource(useQueryClient());
  return useMutation({
    mutationFn: (change: NoticeMutation) => source.setAcknowledgement(change),
  });
}

export function useSelectSigmet() {
  const source = getRouteSigmetSource(useQueryClient());
  return useMutation({
    mutationFn: (change: NoticeSelection) => source.setSelection(change),
  });
}
