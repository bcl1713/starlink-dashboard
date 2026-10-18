import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import {
  issueDraftKey,
  type DraftIdentity,
} from '@/hooks/api/useOperatorIssueDraft';
import type { OperatorCommand, SavedRecord } from '@/types/operator';
import { readOperatorRecords } from '@/services/operator';
import { issueButton, issueInput, instant } from './issueForms';
import { IssueEditor } from './IssueEditor';
import { IssueActivity } from './IssueActivity';
import { IssueCorrection } from './IssueCorrection';
import { JournalHistory } from './JournalHistory';
import { CapabilityAssessments } from './CapabilityAssessments';
import { operatorUtc } from './issueForms';
export function OperatorIssues({ missionId }: { missionId: string }) {
  const journal = useOperatorJournal(missionId, 'issue', { durable: true });
  const [selected, setSelected] = useState<SavedRecord>();
  const [generation, setGeneration] = useState(0);
  const [activityId, setActivityId] = useState<string>();
  const [historyId, setHistoryId] = useState<string>();
  const [correction, setCorrection] = useState<SavedRecord>();
  const [needsCurrent, setNeedsCurrent] = useState(false);
  const ready = !!journal.health.data?.ready && !journal.health.isError;
  const disabled =
    !ready ||
    journal.saving ||
    !!journal.pending ||
    journal.blocked ||
    needsCurrent;
  const health = journal.health.data;
  const identity: DraftIdentity = {
    storeId: health?.store_id ?? 'unknown',
    epoch: health?.api_epoch ?? 'unknown',
    sourceMode: health?.source_mode ?? 'unknown',
    simulationRunId: health?.simulation_run_id ?? null,
    missionId,
    recordId: selected?.record_id ?? 'new-issue',
  };
  const pages = journal.records.data?.pages ?? [];
  const asOf = pages[0]?.as_of ?? null;
  const items = pages.flatMap((p) => p.items);
  const related = useInfiniteQuery({
    queryKey: ['operator-brief', missionId, journal.identity],
    queryFn: ({ pageParam }) =>
      readOperatorRecords({ mission_id: missionId }, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.cursor ?? undefined,
    enabled: !!missionId && !!journal.identity && ready,
    retry: false,
  });
  const relatedRecords =
    related.data?.pages.flatMap((p) => p.items.map((i) => i.record)) ?? [];
  function choose(record?: SavedRecord) {
    journal.openEditor(record);
    setSelected(record);
    setGeneration((n) => n + 1);
    setCorrection(undefined);
  }
  async function save(
    command: OperatorCommand,
    useCurrentTime = false,
    draftKey?: string
  ) {
    const result = await journal.save(command, {
      captureCurrentTime: useCurrentTime,
      draftKey,
    });
    if (!result) return false;
    setNeedsCurrent(!result.current);
    if (result.current && selected?.record_id === result.current.record_id)
      setSelected(result.current);
    setGeneration((n) => n + 1);
    return true;
  }
  async function retry() {
    const result = await journal.retry();
    if (!result) return;
    setNeedsCurrent(!result.current);
    if (result.current && selected) setSelected(result.current);
    setGeneration((n) => n + 1);
  }
  async function action(
    record: SavedRecord,
    status: 'open' | 'monitoring' | 'resolved' | 'reopened'
  ) {
    const input = issueInput(missionId, record);
    await save(
      {
        operation: 'update',
        record_id: record.record_id,
        body: {
          ...input,
          expected_version: record.version,
          time: instant(asOf),
          payload: {
            ...input.payload,
            status,
            ...(status === 'resolved' ? { follow_up_at: null } : {}),
          },
        },
      },
      true
    );
  }
  const active = items
    .filter(
      (i) =>
        !i.record.deleted &&
        i.record.payload.entry_type === 'issue' &&
        i.record.payload.status !== 'resolved'
    )
    .sort((a, b) => {
      if (
        a.record.payload.entry_type !== 'issue' ||
        b.record.payload.entry_type !== 'issue'
      )
        return 0;
      const aTime = a.record.payload.follow_up_at
        ? Date.parse(a.record.payload.follow_up_at)
        : Infinity;
      const bTime = b.record.payload.follow_up_at
        ? Date.parse(b.record.payload.follow_up_at)
        : Infinity;
      if (aTime !== bTime) return aTime < bTime ? -1 : 1;
      const priorities = { urgent: 0, high: 1, normal: 2, low: 3 };
      return (
        priorities[a.record.payload.priority ?? 'low'] +
          (a.record.payload.priority ? 0 : 1) -
          (priorities[b.record.payload.priority ?? 'low'] +
            (b.record.payload.priority ? 0 : 1)) ||
        a.record.record_id.localeCompare(b.record.record_id)
      );
    });
  const resolved = items.filter(
    (i) =>
      !i.record.deleted &&
      i.record.payload.entry_type === 'issue' &&
      i.record.payload.status === 'resolved'
  );
  const removed = items.filter((i) => i.record.deleted);
  const activityCurrent = items.find(
    (i) => i.record.record_id === activityId
  )?.record;
  function row(item: (typeof items)[number]) {
    const record = item.record;
    if (record.payload.entry_type !== 'issue') return null;
    return (
      <li
        key={record.record_id}
        className="min-w-0 space-y-2 break-words rounded-lg border bg-card p-4 [overflow-wrap:anywhere]"
      >
        <h3 className="font-semibold">{record.payload.title}</h3>
        <p>
          {record.deleted ? 'Removed' : record.payload.status} · Priority{' '}
          {record.payload.priority ?? 'unspecified'} · Mitigation{' '}
          {record.payload.mitigation ?? 'unknown'}
        </p>
        <p>
          Follow-up {item.follow_up?.state ?? 'unknown'} ·{' '}
          {operatorUtc(record.payload.follow_up_at)}
        </p>
        <p className="text-xs text-muted-foreground">
          Operator reported · Recorded {operatorUtc(record.recorded_at)} ·{' '}
          {record.scope.replaceAll('_', ' ')}
        </p>
        <div className="flex flex-wrap gap-2">
          {!record.deleted && (
            <>
              <button
                className={issueButton}
                disabled={disabled}
                onClick={() => choose(record)}
              >
                Add update / follow up
              </button>
              {record.payload.status === 'resolved' ? (
                <button
                  className={issueButton}
                  disabled={disabled}
                  onClick={() => void action(record, 'reopened')}
                >
                  Reopen
                </button>
              ) : (
                <>
                  <button
                    className={issueButton}
                    disabled={disabled}
                    onClick={() =>
                      void action(
                        record,
                        record.payload.entry_type === 'issue' &&
                          record.payload.status === 'monitoring'
                          ? 'open'
                          : 'monitoring'
                      )
                    }
                  >
                    {record.payload.status === 'monitoring'
                      ? 'Return to open'
                      : 'Monitor'}
                  </button>
                  <button
                    className={issueButton}
                    disabled={disabled}
                    onClick={() => void action(record, 'resolved')}
                  >
                    Resolve
                  </button>
                </>
              )}
            </>
          )}
          <button
            className={issueButton}
            onClick={() => {
              setActivityId(record.record_id);
              setCorrection(undefined);
            }}
          >
            Issue activity
          </button>
          <button
            className={issueButton}
            onClick={() => setHistoryId(record.record_id)}
          >
            Audit history
          </button>
          <button
            className={issueButton}
            disabled={disabled}
            onClick={() =>
              void save({
                operation: record.deleted ? 'restore' : 'remove',
                record_id: record.record_id,
                body: { schema_version: 1, expected_version: record.version },
              })
            }
          >
            {record.deleted ? 'Restore issue record' : 'Remove issue record'}
          </button>
        </div>
      </li>
    );
  }
  return (
    <section
      id="operator-issues"
      aria-label="Issue management"
      className="min-w-0 scroll-mt-20 space-y-4"
    >
      <h2 className="text-xl font-semibold">Issues and manual capabilities</h2>
      <p>
        Exceptions, workarounds and check-ins · follow-up is snapshot-derived,
        not a live reminder.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className={issueButton}
          disabled={disabled}
          onClick={() => choose()}
        >
          New issue
        </button>
        <button
          className={issueButton}
          disabled={journal.saving}
          onClick={() => void journal.records.refetch()}
        >
          Refresh issues
        </button>
      </div>
      <p className="text-sm">
        Issue snapshot {operatorUtc(asOf)} · refresh to update.
      </p>
      {journal.records.isPending && <p>Loading issues…</p>}
      {journal.records.isError && (
        <p role="alert">
          Issues unavailable. Cached state may be stale; refresh after recovery.
        </p>
      )}
      {journal.records.hasNextPage && (
        <p role="status">
          Issues incomplete.{' '}
          <button
            className={issueButton}
            onClick={() => void journal.records.fetchNextPage()}
          >
            Load remaining issues
          </button>
        </p>
      )}
      {journal.error && (
        <p role="alert">
          {journal.error.message}
          {journal.error.fields && (
            <span> Check {Object.keys(journal.error.fields).join(', ')}.</span>
          )}
        </p>
      )}
      {journal.storageError && <p role="alert">{journal.storageError}</p>}
      {journal.saving && <p role="status">Saving issue…</p>}
      {journal.saved && <p role="status">Issue save acknowledged.</p>}
      {journal.pending && !journal.blocked && (
        <button
          className={issueButton}
          disabled={journal.saving}
          onClick={() => void retry()}
        >
          Retry issue save
        </button>
      )}
      {(journal.blocked || needsCurrent) && (
        <div role="alert">
          {needsCurrent
            ? 'Save acknowledged. Current state unavailable; the submitted draft is retired. Reread before further edits.'
            : 'Issue conflict or changed store. Your draft is retained; review against saved state.'}
          <button
            className={issueButton}
            onClick={() =>
              void journal.reconcile().then((result) => {
                if (result) {
                  setNeedsCurrent(false);
                  setSelected(result.current);
                  setGeneration((n) => n + 1);
                }
              })
            }
          >
            Reread issue for reconciliation
          </button>
        </div>
      )}
      {journal.latest && (
        <p>
          Latest saved version {journal.latest.record.version}:{' '}
          {journal.latest.record.payload.title}
          {journal.latest.record.payload.entry_type === 'issue'
            ? ` · ${journal.latest.record.payload.status}`
            : ''}
        </p>
      )}
      {journal.reconcileError && <p role="alert">{journal.reconcileError}</p>}
      {ready && (
        <IssueEditor
          key={JSON.stringify(identity) + generation}
          missionId={missionId}
          record={selected}
          identity={identity}
          disabled={disabled}
          asOf={asOf}
          onSave={(command, useCurrentTime) =>
            save(command, useCurrentTime, issueDraftKey(identity))
          }
          related={relatedRecords}
        />
      )}
      {(related.isError || related.hasNextPage) && (
        <p>
          Optional associations {related.isError ? 'unavailable' : 'incomplete'}
          . Logging an unlinked issue remains available.
          {related.hasNextPage && (
            <button
              className={issueButton}
              onClick={() => void related.fetchNextPage()}
            >
              Load more associations
            </button>
          )}
        </p>
      )}
      <ul className="space-y-3">{active.map(row)}</ul>
      <details>
        <summary className="min-h-11 cursor-pointer">
          Resolved issues ({resolved.length})
        </summary>
        <ul className="space-y-3">{resolved.map(row)}</ul>
      </details>
      <details>
        <summary className="min-h-11 cursor-pointer">
          Removed issue records ({removed.length})
        </summary>
        <ul className="space-y-3">{removed.map(row)}</ul>
      </details>
      {activityId && journal.identity && (
        <>
          <IssueActivity
            id={activityId}
            identity={journal.identity}
            disabled={disabled || !!activityCurrent?.deleted}
            onCorrect={(target) => setCorrection(target)}
          />
          {correction && activityCurrent && (
            <IssueCorrection
              current={activityCurrent}
              target={correction}
              identity={identity}
              disabled={disabled}
              onSave={(command) =>
                save(
                  command,
                  false,
                  issueDraftKey({
                    ...identity,
                    recordId:
                      activityCurrent.record_id +
                      ':correction:' +
                      correction.version,
                  })
                )
              }
              onClose={() => setCorrection(undefined)}
            />
          )}
        </>
      )}
      {historyId && journal.identity && (
        <JournalHistory
          id={historyId}
          identity={journal.identity}
          onClose={() => setHistoryId(undefined)}
        />
      )}
      <CapabilityAssessments
        key={missionId + ':capabilities'}
        missionId={missionId}
      />
    </section>
  );
}
