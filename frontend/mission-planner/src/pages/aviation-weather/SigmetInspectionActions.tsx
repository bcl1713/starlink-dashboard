import { useEffect, useRef } from 'react';
import {
  useRouteSigmets,
  useSelectSigmet,
  useSetSigmetAcknowledgement,
} from '@/hooks/api/useRouteSigmets';

export function SigmetInspectionActions({
  featureId,
  autoSelect,
  onFocused,
  onAcknowledged,
}: {
  featureId: string;
  autoSelect: boolean;
  onFocused?: (key: string) => void;
  onAcknowledged?: () => void;
}) {
  const view = useRouteSigmets(),
    select = useSelectSigmet(),
    ack = useSetSigmetAcknowledgement();
  const snapshot = view.snapshot;
  const contextKey = snapshot?.context?.context_key;
  const entry = [
    ...(snapshot?.entries ?? []),
    ...(snapshot?.selected_entries ?? []),
  ].find((e) => e.feature_ids.includes(featureId));
  const candidate = snapshot?.selection_candidates.find((e) =>
    e.feature_ids.includes(featureId)
  );
  const attempt = useRef('');
  const key = `${contextKey}:${candidate?.bulletin_key}:${candidate?.semantic_digest}:${featureId}`;
  const pending = !!entry && !entry.acknowledged;
  const mutate = select.mutate;
  useEffect(() => {
    if (
      !autoSelect ||
      !contextKey ||
      !candidate ||
      pending ||
      !view.available ||
      attempt.current === key
    )
      return;
    attempt.current = key;
    mutate(
      {
        context_key: contextKey,
        bulletin_key: candidate.bulletin_key,
        semantic_digest: candidate.semantic_digest,
      },
      {
        onSuccess: (result) => {
          const added = [...result.entries, ...result.selected_entries].find(
            (e) => e.feature_ids.includes(featureId)
          );
          if (added) onFocused?.(added.notice_key);
        },
      }
    );
  }, [
    autoSelect,
    contextKey,
    candidate,
    pending,
    view.available,
    key,
    mutate,
    featureId,
    onFocused,
  ]);
  if (!contextKey)
    return <p>Select a route to add this SIGMET to attention.</p>;
  if (!candidate || !view.available)
    return <p>Report unavailable for selection. Refresh and try again.</p>;
  return (
    <div className="sigmet-inspection-actions">
      {pending && (
        <button
          type="button"
          disabled={ack.isPending}
          onClick={() =>
            ack.mutate(
              {
                context_key: contextKey,
                notice_key: entry.notice_key,
                semantic_digest: entry.semantic_digest,
                acknowledged: true,
              },
              { onSuccess: onAcknowledged }
            )
          }
        >
          Acknowledge
        </button>
      )}
      {!pending && !select.isPending && (
        <button
          type="button"
          onClick={() =>
            mutate({
              context_key: contextKey,
              bulletin_key: candidate.bulletin_key,
              semantic_digest: candidate.semantic_digest,
            })
          }
        >
          Add to attention
        </button>
      )}
      {select.isPending && <p role="status">Adding SIGMET…</p>}
      {(select.error || ack.error) && (
        <p role="alert">Could not save this SIGMET. Try again.</p>
      )}
    </div>
  );
}
