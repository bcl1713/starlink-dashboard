import { useEffect, useRef, useState } from 'react';
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
  const [origin] = useState(() => ({
    contextKey,
    bulletinKey: candidate?.bulletin_key,
    digest: candidate?.semantic_digest,
  }));
  const attempted = useRef(false);
  const pending = !!entry && !entry.acknowledged;
  const routeChanged = origin.contextKey !== contextKey;
  const reportChanged =
    !!origin.digest &&
    (origin.digest !== candidate?.semantic_digest ||
      origin.bulletinKey !== candidate?.bulletin_key);
  const mutate = select.mutate;
  useEffect(() => {
    if (
      !autoSelect ||
      !contextKey ||
      !candidate ||
      !view.available ||
      attempted.current ||
      routeChanged ||
      reportChanged
    )
      return;
    // One effect belongs to one explicit inspection gesture, even if the
    // bulletin was already pending. Polling must never manufacture a new intent.
    attempted.current = true;
    if (pending && entry) {
      onFocused?.(entry.notice_key);
      return;
    }
    mutate(
      {
        context_key: contextKey,
        bulletin_key: candidate.bulletin_key,
        semantic_digest: candidate.semantic_digest,
      },
      {
        onSuccess: (confirmation) => {
          if (confirmation.notice_key) onFocused?.(confirmation.notice_key);
        },
      }
    );
  }, [
    autoSelect,
    contextKey,
    candidate,
    pending,
    entry,
    view.available,
    routeChanged,
    reportChanged,
    mutate,
    onFocused,
  ]);
  if (routeChanged)
    return <p>Route changed. Select this SIGMET again on the map.</p>;
  if (reportChanged)
    return <p>Report changed. Select this SIGMET again on the map.</p>;
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
