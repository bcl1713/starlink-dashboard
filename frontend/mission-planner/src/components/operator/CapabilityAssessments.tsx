import { CapabilityEditor } from './CapabilityEditor';
import { useState } from 'react';
import type { SavedRecord } from '@/types/operator';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import {
  issueDraftKey,
  type DraftIdentity,
} from '@/hooks/api/useOperatorIssueDraft';
import { issueButton } from './issueForms';
import { operatorUtc } from './issueForms';
import { JournalHistory } from './JournalHistory';
export function CapabilityAssessments({ missionId }: { missionId: string }) {
  const journal = useOperatorJournal(missionId, 'journal_entry', {
    durable: true,
  });
  const [selected, setSelected] = useState<SavedRecord>();
  const [generation, setGeneration] = useState(0);
  const [historyId, setHistoryId] = useState<string>();
  const [needsCurrent, setNeedsCurrent] = useState(false);
  const ready = journal.health.data?.ready && !journal.health.isError;
  const disabled =
    !ready ||
    journal.saving ||
    !!journal.pending ||
    journal.blocked ||
    needsCurrent;
  const asOf = journal.records.data?.pages[0]?.as_of ?? null;
  const records =
    journal.records.data?.pages
      .flatMap((p) => p.items.map((i) => i.record))
      .filter((r) => r.payload.entry_type === 'capability_assessment') ?? [];
  const health = journal.health.data;
  const identity: DraftIdentity = {
    storeId: health?.store_id ?? 'unknown',
    epoch: health?.api_epoch ?? 'unknown',
    sourceMode: health?.source_mode ?? 'unknown',
    simulationRunId: health?.simulation_run_id ?? null,
    missionId,
    recordId: selected?.record_id ?? 'new-capability',
  };
  function choose(record?: SavedRecord) {
    journal.openEditor(record);
    setSelected(record);
    setGeneration((n) => n + 1);
  }
  return (
    <section aria-label="Manual capabilities" className="min-w-0 space-y-3">
      <h3 className="text-lg font-semibold">Manual capabilities</h3>
      <p>
        No automatic aircraft-ready declaration. No assessment means unknown.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className={issueButton}
          disabled={disabled}
          onClick={() => choose()}
        >
          New capability assessment
        </button>
        <button
          className={issueButton}
          disabled={journal.saving}
          onClick={() => void journal.records.refetch()}
        >
          Refresh assessments
        </button>
      </div>
      {journal.records.isError && (
        <p role="alert">
          Assessments unavailable; saved manual capability is unknown here.
        </p>
      )}
      {journal.error && <p role="alert">{journal.error.message}</p>}
      {journal.storageError && <p role="alert">{journal.storageError}</p>}
      {journal.saving && <p role="status">Saving assessment…</p>}
      {journal.saved && <p role="status">Assessment save acknowledged.</p>}
      {journal.pending && !journal.blocked && (
        <button
          className={issueButton}
          onClick={() =>
            void journal.retry().then((result) => {
              if (result) {
                setNeedsCurrent(!result.current);
                choose(selected ? result.current : undefined);
              }
            })
          }
        >
          Retry assessment save
        </button>
      )}
      {(journal.blocked || needsCurrent) && (
        <div role="alert">
          {needsCurrent
            ? 'Assessment save acknowledged. Current state unavailable; the submitted draft is retired. Reread before further edits.'
            : 'Assessment conflict or changed store. Draft retained.'}
          <button
            className={issueButton}
            onClick={() =>
              void journal.reconcile().then((result) => {
                if (result) {
                  setNeedsCurrent(false);
                  choose(result.current);
                }
              })
            }
          >
            Reread assessment for reconciliation
          </button>
        </div>
      )}
      {ready && (
        <CapabilityEditor
          key={JSON.stringify(identity) + generation}
          missionId={missionId}
          record={selected}
          identity={identity}
          disabled={disabled}
          asOf={asOf}
          onSave={async (input, version, currentDimensions) => {
            const result = await journal.save(
              selected && version
                ? {
                    operation: 'update',
                    record_id: selected.record_id,
                    body: { ...input, expected_version: version },
                  }
                : { operation: 'create', body: input },
              {
                draftKey: issueDraftKey(identity),
                captureCurrentTime: true,
                captureDimensions: currentDimensions,
              }
            );
            if (result) {
              setNeedsCurrent(!result.current);
              choose(selected ? result.current : undefined);
              return true;
            }
            return false;
          }}
        />
      )}
      <ul className="space-y-3">
        {records.map((record) => (
          <li
            key={record.record_id}
            className="min-w-0 space-y-2 break-words rounded border p-3 [overflow-wrap:anywhere]"
          >
            <p className="font-medium">
              {record.payload.title}
              {record.deleted ? ' · Removed' : ''}
            </p>
            {record.payload.entry_type === 'capability_assessment' && (
              <>
                <p>
                  Functional: {record.payload.functional_status} · observed{' '}
                  {operatorUtc(record.payload.functional_observed_at)}
                </p>
                <p>
                  Redundancy: {record.payload.redundancy_status} · observed{' '}
                  {operatorUtc(record.payload.redundancy_observed_at)}
                </p>
                <p className="text-sm">
                  Operator reported · Recorded {operatorUtc(record.recorded_at)}
                </p>
              </>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                className={issueButton}
                disabled={disabled || record.deleted}
                onClick={() => choose(record)}
              >
                Assess capability
              </button>
              <button
                className={issueButton}
                onClick={() => setHistoryId(record.record_id)}
              >
                Assessment history
              </button>
              <button
                className={issueButton}
                disabled={disabled}
                onClick={() =>
                  void journal.save({
                    operation: record.deleted ? 'restore' : 'remove',
                    record_id: record.record_id,
                    body: {
                      schema_version: 1,
                      expected_version: record.version,
                    },
                  })
                }
              >
                {record.deleted
                  ? 'Restore assessment record'
                  : 'Remove assessment record'}
              </button>
            </div>
          </li>
        ))}
      </ul>
      {journal.records.hasNextPage && (
        <button
          className={issueButton}
          onClick={() => void journal.records.fetchNextPage()}
        >
          Load remaining assessments
        </button>
      )}
      {historyId && journal.identity && (
        <JournalHistory
          id={historyId}
          identity={journal.identity}
          onClose={() => setHistoryId(undefined)}
        />
      )}
    </section>
  );
}
