import { useEffect, useState } from 'react';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import type { SavedRecord } from '@/types/operator';
import { TransportDecisionList } from '../TransportDecisionList';
import { TransportAssignments } from './TransportAssignments';
import type { CatalogItem } from '@/services/transportCatalog';
import { TransportReview } from '../TransportReview';
export function TransportView({
  records,
  missionId,
  identity,
  legId,
  onApply,
  events,
  disabled,
  onCreate,
  onEdit,
  onHistory,
  onTransition,
}: {
  missionId: string;
  identity: string | null;
  records: SavedRecord[];
  legId: string | null;
  onApply: (service: CatalogItem, transport: CatalogItem) => Promise<void>;
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
      <h2>Service transport</h2>
      <p className="ws-meta">
        Record the transport each service is reported to be using.
      </p>
      <TransportAssignments
        missionId={missionId}
        identity={identity}
        records={records}
        legId={legId}
        disabled={disabled}
        onApply={onApply}
      />
      <details>
        <summary>History and advanced records</summary>
        <button className="ws-button" disabled={disabled} onClick={onCreate}>
          Create advanced transport record
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
      </details>
    </section>
  );
}
