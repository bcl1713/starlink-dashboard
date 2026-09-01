import type { RecordState } from './radar-tile-types';

type FindRecord = (key: string, currentRequest: number) => RecordState | null;
type RevokeUrl = (url: string) => void;

export function bindRadarImage(
  record: RecordState,
  findRecord: FindRecord,
  revoke: RevokeUrl
): () => void {
  const image = record.image;
  if (!image) return () => undefined;
  const onLoad = () => {
    const current = findRecord(record.key, record.requestId);
    if (!current || current.image !== image || !current.candidateUrl) return;
    const old = current.objectUrl;
    current.objectUrl = current.candidateUrl;
    current.candidateUrl = null;
    current.resolveVisibleLoad?.();
    clearVisibleLoad(current);
    if (old) revoke(old);
    current.done?.(undefined, image);
  };
  const onError = () => {
    const current = findRecord(record.key, record.requestId);
    if (!current || current.image !== image || !current.candidateUrl) return;
    revoke(current.candidateUrl);
    current.candidateUrl = null;
    image.src = current.objectUrl ?? '';
    current.rejectVisibleLoad?.(new Error('Radar tile image failed.'));
    clearVisibleLoad(current);
    current.done?.(new Error('Radar tile image failed.'));
  };
  image.addEventListener('load', onLoad);
  image.addEventListener('error', onError);
  return () => {
    image.removeEventListener('load', onLoad);
    image.removeEventListener('error', onError);
  };
}

export function revokeRadarCandidate(
  record: RecordState,
  revoke: RevokeUrl
): void {
  if (record.candidateUrl) revoke(record.candidateUrl);
  record.candidateUrl = null;
  record.rejectVisibleLoad?.(new DOMException('superseded', 'AbortError'));
  clearVisibleLoad(record);
}

export function clearVisibleLoad(record: RecordState): void {
  record.visibleLoad = null;
  record.resolveVisibleLoad = null;
  record.rejectVisibleLoad = null;
}
