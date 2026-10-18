import { useEffect, useState } from 'react';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import type { OperatorCommand, SavedRecord } from '@/types/operator';
import { TransportEditor } from './TransportEditor';
import { TransportDecisionList } from './TransportDecisionList';
import { TransportReview } from './TransportReview';
import { JournalHistory } from './JournalHistory';
import { issueButton } from './issueForms';

export function OperatorTransport({
  missionId,
  eventFeed,
}: {
  missionId: string;
  eventFeed: OperatorEventsState;
}) {
  const journal = useOperatorJournal(missionId, 'transport_decision', {
    durable: true,
  });
  const [selected, setSelected] = useState<SavedRecord>();
  const [generation, setGeneration] = useState(0);
  const [history, setHistory] = useState<string>();
  const [needsCurrent, setNeedsCurrent] = useState(false);
  const ready = !!journal.health.data?.ready && !journal.health.isError;
  const disabled =
    !ready ||
    journal.saving ||
    !!journal.pending ||
    journal.blocked ||
    needsCurrent;
  const records =
    journal.records.data?.pages.flatMap((p) => p.items.map((i) => i.record)) ??
    [];
  function choose(record?: SavedRecord) {
    journal.openEditor(record);
    setSelected(record);
    setGeneration((n) => n + 1);
  }
  function acknowledge(current?: SavedRecord) {
    setNeedsCurrent(!current);
    setSelected(current);
    setGeneration((n) => n + 1);
    eventFeed.refresh();
  }
  async function save(command: OperatorCommand, draftKey: string) {
    const result = await journal.save(command, { draftKey });
    if (!result) return false;
    acknowledge(result.current);
    return true;
  }
  async function action(record: SavedRecord) {
    journal.openEditor(record);
    const result = await journal.save({
      operation: record.deleted ? 'restore' : 'remove',
      record_id: record.record_id,
      body: { schema_version: 1, expected_version: record.version },
    });
    if (result) acknowledge(result.current);
  }
  const [snapshotStale, setSnapshotStale] = useState(true);
  useEffect(() => {
    const remaining = 30_000 - (performance.now() - eventFeed.receivedAt);
    setSnapshotStale(remaining <= 0);
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setSnapshotStale(true), remaining);
    return () => window.clearTimeout(timer);
  }, [eventFeed.receivedAt]);
  const stale = eventFeed.failed || snapshotStale || !ready || journal.blocked;
  return (
    <section
      id="operator-transport"
      aria-label="Operator transport decisions"
      className="min-w-0 scroll-mt-4 space-y-4"
    >
      <h2 className="text-xl font-semibold">Transport decisions</h2>
      <p>
        Service intentions and operator reports · UTC · Actual routing unknown.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className={issueButton}
          disabled={disabled}
          onClick={() => choose()}
        >
          Record another move
        </button>
        <button
          className={issueButton}
          disabled={journal.saving}
          onClick={() => {
            void journal.records.refetch();
            eventFeed.refresh();
          }}
        >
          Refresh transport decisions
        </button>
      </div>
      {journal.error && (
        <p role="alert">
          {journal.error.code}: {journal.error.message}
          {journal.error.record_ids?.length
            ? ` · Related records: ${journal.error.record_ids.join(', ')}`
            : ''}
          {journal.error.fields
            ? ` · ${Object.keys(journal.error.fields).join(', ')}`
            : ''}
        </p>
      )}
      {journal.storageError && <p role="alert">{journal.storageError}</p>}
      {journal.saving && <p role="status">Saving transport decision…</p>}
      {journal.saved && <p role="status">Transport save acknowledged.</p>}
      {journal.pending && !journal.blocked && (
        <button
          className={issueButton}
          disabled={journal.saving}
          onClick={() =>
            void journal.retry().then((result) => {
              if (result) acknowledge(result.current);
            })
          }
        >
          Retry transport save
        </button>
      )}
      {(journal.blocked || needsCurrent) && (
        <div role="alert">
          {needsCurrent
            ? 'Save acknowledged. Reread current state before editing.'
            : 'Transport conflict or changed store. Draft retained; review against saved state.'}
          <button
            className={issueButton}
            disabled={journal.saving}
            onClick={() =>
              void journal.reconcile().then((result) => {
                if (result) {
                  setNeedsCurrent(false);
                  setSelected(result.current);
                  setGeneration((n) => n + 1);
                  eventFeed.refresh();
                }
              })
            }
          >
            Reread transport for reconciliation
          </button>
        </div>
      )}
      {journal.latest && (
        <p>
          Latest saved version {journal.latest.record.version}:{' '}
          {journal.latest.record.payload.title}
        </p>
      )}
      {journal.reconcileError && <p role="alert">{journal.reconcileError}</p>}
      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <div>
          {ready && journal.identity && (
            <TransportEditor
              key={`${journal.identity}:${generation}`}
              missionId={missionId}
              record={selected?.deleted ? undefined : selected}
              identity={journal.identity}
              disabled={disabled}
              onSave={save}
            />
          )}
        </div>
        <TransportReview
          review={eventFeed.snapshot?.transport_review}
          events={eventFeed.snapshot?.events}
          stale={stale}
          error={eventFeed.failed}
        />
      </div>
      {journal.records.isError && (
        <p role="alert">
          Transport records unavailable. Cached decisions may be stale.
        </p>
      )}
      <TransportDecisionList
        records={records}
        disabled={disabled}
        onCorrect={choose}
        onHistory={setHistory}
        onAction={(r) => void action(r)}
      />
      {journal.records.hasNextPage && (
        <button
          className={issueButton}
          onClick={() => void journal.records.fetchNextPage()}
        >
          Load more transport decisions
        </button>
      )}
      {history && journal.identity && (
        <JournalHistory
          id={history}
          identity={journal.identity}
          onClose={() => setHistory(undefined)}
        />
      )}
    </section>
  );
}
