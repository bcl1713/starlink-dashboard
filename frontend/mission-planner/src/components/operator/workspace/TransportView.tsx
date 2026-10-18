import { useEffect, useState } from 'react';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import type { SavedRecord } from '@/types/operator';
import { TransportDecisionList } from '../TransportDecisionList';
import { TransportReview } from '../TransportReview';
export function TransportView({
  records,
  events,
  disabled,
  onCreate,
  onEdit,
  onHistory,
  onTransition,
}: {
  records: SavedRecord[];
  events: OperatorEventsState;
  disabled: boolean;
  onCreate: () => void;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
}) {
  const [expired, setExpired] = useState<number | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(
      () => setExpired(events.receivedAt),
      Math.max(0, 30_000 - (performance.now() - events.receivedAt))
    );
    return () => window.clearTimeout(timer);
  }, [events.receivedAt]);
  return (
    <section
      aria-label="Transport"
      id="operator-transport"
      className="space-y-4"
    >
      <h2>Transport decisions</h2>
      <p>
        Record intended, requested, applied and checked stages independently.
        Applied-only reports remain available during protected customer
        activity.
      </p>
      <button className="ws-button" disabled={disabled} onClick={onCreate}>
        Record another move
      </button>
      <TransportReview
        review={events.snapshot?.transport_review}
        stale={
          events.failed || !events.snapshot || expired === events.receivedAt
        }
        error={events.failed}
        events={events.snapshot?.events}
      />
      {!records.some(
        (record) => record.record_type === 'transport_decision'
      ) && <p>No transport decisions recorded.</p>}
      <TransportDecisionList
        records={records.filter(
          (record) => record.record_type === 'transport_decision'
        )}
        disabled={disabled}
        onCorrect={onEdit}
        onHistory={onHistory}
        onAction={onTransition}
      />
    </section>
  );
}
