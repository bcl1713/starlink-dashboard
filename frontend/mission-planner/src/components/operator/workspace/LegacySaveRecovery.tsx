import { useState } from 'react';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
type RecoveryRecordType = NonNullable<Parameters<typeof useOperatorJournal>[1]>;

const prefix = 'operator-367-pending:';
const recordTypes: RecoveryRecordType[] = [
  'journal_entry',
  'call',
  'conference',
  'participation',
  'issue',
  'transport_decision',
];

/** Keep exact-request recovery available after retiring the old page. */
export function LegacySaveRecovery() {
  const [keys] = useState(() => {
    try {
      return Object.keys(sessionStorage).filter((key) =>
        key.startsWith(prefix)
      );
    } catch {
      return [];
    }
  });
  return keys.map((key) => {
    const recordType = recordTypes.find((type) => key.endsWith(':' + type));
    const missionId = recordType
      ? key.slice(prefix.length, -(recordType.length + 1))
      : '';
    return recordType && missionId ? (
      <Recovery
        key={key}
        storageKey={key}
        missionId={missionId}
        recordType={recordType}
      />
    ) : (
      <p role="alert" key={key}>
        An older save could not be decoded. Its browser storage is preserved for
        recovery.
      </p>
    );
  });
}
function Recovery({
  storageKey,
  missionId,
  recordType,
}: {
  storageKey: string;
  missionId: string;
  recordType: RecoveryRecordType;
}) {
  const journal = useOperatorJournal(missionId, recordType, {
    pendingStorageKey: storageKey,
    requirePersistence: true,
    readRecords: false,
    healthPolling: false,
  });
  const [released, setReleased] = useState(false);
  if (released)
    return (
      <p role="status">Older save released after rereading saved state.</p>
    );
  if (journal.saved) return <p role="status">Older save confirmed.</p>;
  return (
    <section aria-label="Older save recovery" className="ws-record">
      <h2>Older save recovery</h2>
      <p>
        This save may already have been received. Retry the original request or
        reread saved state before releasing it.
      </p>
      <p>
        {missionId} · {recordType.replaceAll('_', ' ')}
      </p>
      <button
        className="ws-button"
        disabled={!journal.retryReady}
        onClick={() => void journal.retry()}
      >
        Retry original save
      </button>
      <button
        className="ws-button"
        disabled={
          journal.saving ||
          !journal.health.data?.ready ||
          journal.health.isError
        }
        onClick={async () => {
          if (await journal.reconcile()) setReleased(true);
        }}
      >
        Reread and reconcile older save
      </button>
      {journal.missingInNewStore && (
        <button
          className="ws-button"
          disabled={journal.saving}
          onClick={() => {
            if (journal.recoverMissing()) setReleased(true);
          }}
        >
          Release older save absent from current store
        </button>
      )}
      {journal.latest && (
        <p>Latest saved version: {journal.latest.record.version}</p>
      )}
      {journal.error && <p role="alert">{journal.error.message}</p>}
      {journal.storageError && <p role="alert">{journal.storageError}</p>}
      {journal.reconcileError && <p role="alert">{journal.reconcileError}</p>}
    </section>
  );
}
