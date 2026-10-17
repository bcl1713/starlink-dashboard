import { useState } from 'react';
import type { CallInput, OperatorCommand, SavedRecord } from '@/types/operator';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import { CallEditor } from './CallEditor';
import { CallList } from './CallList';
import { callDraft } from './callDraft';
import { JournalHistory } from './JournalHistory';
const button = 'min-h-11 rounded-md border px-3 disabled:opacity-50';
export function OperatorCommunications({
  missionId,
  onDirty,
}: {
  missionId: string;
  onDirty?: (dirty: boolean) => void;
}) {
  const calls = useOperatorJournal(missionId, 'call');
  const [draft, setDraft] = useState<CallInput>(() =>
    callDraft(undefined, 'planned', missionId)
  );
  const [selected, setSelected] = useState<SavedRecord>();
  const [dirty, setDirty] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [needsCurrent, setNeedsCurrent] = useState(false);
  const [historyId, setHistoryId] = useState<string>();
  const unavailable = calls.health.isError || !calls.health.data?.ready;
  const locked = calls.saving || !!calls.pending;
  const disabled = unavailable || locked || calls.blocked || needsCurrent;
  function markDirty(value: boolean) {
    setDirty(value);
    onDirty?.(value);
  }
  function open(
    record?: SavedRecord,
    mode: 'planned' | 'retrospective' = 'planned',
    saved = false
  ) {
    calls.openEditor(record, saved);
    setNeedsCurrent(false);
    setSelected(record);
    setDraft(callDraft(record, mode, missionId));
    setGeneration((n) => n + 1);
    markDirty(false);
  }
  function accepted(result: { current?: SavedRecord } | undefined) {
    if (!result) return;
    if (result.current) open(result.current, 'planned', true);
    else setNeedsCurrent(true);
  }
  async function save(command: OperatorCommand) {
    markDirty(true);
    const result = await calls.save(command);
    accepted(result);
  }
  const items = calls.records.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section
      id="operator-communications"
      aria-label="Communications"
      className="min-w-0 scroll-mt-4 space-y-4"
    >
      <h2 className="text-xl font-semibold">Communications</h2>
      <p className="text-sm text-muted-foreground">
        Plan requirements or record completed calls. Conference sessions remain
        independent. UTC snapshot; refresh to update.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className={button}
          disabled={disabled || dirty}
          onClick={() => open()}
        >
          Schedule call
        </button>
        <button
          className={button}
          disabled={disabled || dirty}
          onClick={() => open(undefined, 'retrospective')}
        >
          Log unscheduled/completed call
        </button>
        <button
          className={button}
          disabled={locked || calls.blocked || calls.records.isFetching}
          onClick={() => void calls.records.refetch()}
        >
          Refresh calls
        </button>
        {dirty && !locked && !calls.blocked && (
          <button className={button} onClick={() => open(selected)}>
            Discard call draft
          </button>
        )}
      </div>
      {dirty && (
        <p role="status">
          Unsaved call draft — save or discard before switching calls or
          missions.
        </p>
      )}
      {calls.saving && <p role="status">Saving call…</p>}
      {calls.saved && !dirty && !needsCurrent && (
        <p role="status">Call saved.</p>
      )}
      {needsCurrent && (
        <p role="status">
          Call save acknowledged. Current saved state unavailable; reread to
          continue. Your draft is retained.
        </p>
      )}
      {unavailable && (
        <p role="alert">
          Communications unavailable. Saved state could not be verified.
        </p>
      )}
      {calls.error && (
        <div role="alert">
          <p>
            {calls.error.message} · {calls.error.code}
          </p>
          {calls.error.fields && (
            <p>{Object.keys(calls.error.fields).join(', ')}</p>
          )}
        </div>
      )}
      {calls.pending && !calls.blocked && (
        <button
          className={button}
          disabled={calls.saving}
          onClick={async () => {
            const result = await calls.retry();
            accepted(result);
          }}
        >
          Retry same call save
        </button>
      )}
      {(calls.blocked || needsCurrent) && (
        <div className="space-y-2">
          <p>
            Call state changed. Your draft is retained; reread before editing
            again.
          </p>
          {calls.latest && (
            <p>
              Latest saved call: {calls.latest.record.payload.title} · version{' '}
              {calls.latest.record.version}
            </p>
          )}
          <button
            className={button}
            disabled={calls.saving}
            onClick={async () => {
              const value = await calls.reconcile();
              if (value) open(value.current, 'planned', needsCurrent);
            }}
          >
            Reread and use saved call
          </button>
          {calls.reconcileError && <p role="alert">{calls.reconcileError}</p>}
          {calls.missingInNewStore && (
            <button
              className={button}
              onClick={() => {
                if (calls.recoverMissing()) {
                  setSelected(undefined);
                  setNeedsCurrent(false);
                  markDirty(true);
                }
              }}
            >
              Keep call draft as new in current store
            </button>
          )}
        </div>
      )}
      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <CallEditor
          key={generation}
          draft={draft}
          disabled={disabled || !!selected?.deleted}
          onDirty={() => markDirty(true)}
          onChange={(value) => {
            setDraft(value);
            markDirty(true);
          }}
          onSubmit={(value) => {
            setDraft(value);
            void save(
              selected
                ? {
                    operation: 'update',
                    record_id: selected.record_id,
                    body: { ...value, expected_version: selected.version },
                  }
                : { operation: 'create', body: value }
            );
          }}
        />
        <div className="min-w-0 space-y-3">
          {calls.records.isError && (
            <p role="alert">Calls unavailable. Refresh calls to retry.</p>
          )}
          {calls.records.isPending && <p>Loading calls…</p>}
          {!unavailable && !calls.records.isError && !calls.blocked && (
            <CallList
              items={items}
              disabled={disabled || dirty}
              incomplete={!!calls.records.hasNextPage}
              asOf={calls.records.data?.pages[0]?.as_of}
              onEdit={(r) => open(r)}
              onHistory={setHistoryId}
              onTransition={(r) =>
                void save({
                  operation: r.deleted ? 'restore' : 'remove',
                  record_id: r.record_id,
                  body: { schema_version: 1, expected_version: r.version },
                })
              }
            />
          )}
          {calls.records.hasNextPage && (
            <button
              className={button}
              disabled={calls.records.isFetching}
              onClick={() => void calls.records.fetchNextPage()}
            >
              Load more calls
            </button>
          )}
          {historyId && calls.identity && !calls.blocked && !unavailable && (
            <JournalHistory
              id={historyId}
              identity={calls.identity}
              onClose={() => setHistoryId(undefined)}
            />
          )}
        </div>
      </div>
    </section>
  );
}
