import { OperatorIssues } from '@/components/operator/OperatorIssues';
import { OperatorEventStrip } from '@/components/operator/OperatorEventStrip';
import { useOperatorEvents } from '@/hooks/api/useOperatorEvents';
import { OperatorCommunications } from '@/components/operator/OperatorCommunications';
import { OperatorDisplayTools } from '@/components/operator/OperatorDisplayTools';
import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { OperatorBrief } from '@/components/operator/OperatorBrief';
import { readOperatorRecords } from '@/services/operator';
import { useSearchParams } from 'react-router-dom';
import { JournalEditor } from '@/components/operator/JournalEditor';
import { JournalHistory } from '@/components/operator/JournalHistory';
import { JournalList } from '@/components/operator/JournalList';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import { operatorFailure } from '@/services/operator';
import type { OperatorCommand, SavedRecord } from '@/types/operator';
export function OperatorJournalPage() {
  const [params, setParams] = useSearchParams();
  const missionId = params.get('mission_id') ?? '';
  const [missionDraft, setMissionDraft] = useState(missionId);
  const journal = useOperatorJournal(missionId);
  const eventFeed = useOperatorEvents(
    missionId,
    !journal.blocked ? journal.identity : null
  );
  const brief = useInfiniteQuery({
    queryKey: ['operator-brief', missionId, journal.identity],
    queryFn: ({ pageParam }) =>
      readOperatorRecords({ mission_id: missionId }, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    enabled:
      !!missionId &&
      !!journal.identity &&
      !journal.health.isError &&
      !journal.blocked,
    retry: false,
    networkMode: 'always',
  });
  const [selected, setSelected] = useState<SavedRecord>();
  const [editorVersion, setEditorVersion] = useState(0);
  const [journalDirty, setDirty] = useState(false);
  const [callDirty, setCallDirty] = useState(false);
  const dirty = journalDirty || callDirty;
  const [createFromDraft, setCreateFromDraft] = useState(false);
  const [historyId, setHistoryId] = useState<string>();
  const locked = journal.saving || !!journal.pending;
  const unavailable = journal.health.isError || !journal.health.data?.ready;
  const disabled = unavailable || locked || journal.blocked;
  function select(record?: SavedRecord, acknowledged = false) {
    journal.openEditor(record, acknowledged);
    setSelected(record);
    setCreateFromDraft(false);
    setEditorVersion((n) => n + 1);
    setDirty(false);
  }
  async function save(command: OperatorCommand) {
    const receipt = await journal.save(command);
    if (receipt) select(receipt.current, true);
  }
  if (journal.health.isPending)
    return <main className="p-6">Loading Operator journal…</main>;
  if (
    journal.health.isError &&
    operatorFailure(journal.health.error).status === 404
  )
    return <main className="p-6">Operator journal is disabled.</main>;
  return (
    <main className="mx-auto w-full min-w-0 max-w-7xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Mission workspace
          </p>
          <h1 className="text-2xl font-semibold">Operator</h1>
          <p className="text-sm text-muted-foreground">
            {journal.health.data?.source_mode === 'simulation'
              ? 'Simulation · '
              : ''}
            Single mission manager / counterpart · UTC
          </p>
        </div>
        <nav aria-label="Operator sections" className="flex flex-wrap gap-2">
          <a
            href="#operator-events"
            className="inline-flex min-h-11 items-center rounded-md border px-3"
          >
            Upcoming
          </a>
          <a
            href="#operator-communications"
            className="inline-flex min-h-11 items-center rounded-md border px-3"
          >
            Communications
          </a>
          <a
            href="#operator-issues"
            className="inline-flex min-h-11 items-center rounded-md border px-3"
          >
            Issues
          </a>
          <a
            href="#operator-journal"
            className="inline-flex min-h-11 items-center rounded-md border px-3"
          >
            Journal
          </a>
          <a
            href="#display-tools"
            className="inline-flex min-h-11 items-center rounded-md border px-3"
          >
            Display tools
          </a>
        </nav>
      </header>
      {missionId && <OperatorEventStrip events={eventFeed} />}
      <div id="operator-brief" className="scroll-mt-4">
        <OperatorBrief
          missionId={missionId}
          liveEvents={!!eventFeed.snapshot && !eventFeed.failed}
          pages={brief.data?.pages ?? []}
          unavailable={unavailable || journal.blocked}
          loading={brief.isPending}
          failed={brief.isError}
          incomplete={!!brief.hasNextPage}
        />
        {missionId && (
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              className="min-h-11 rounded-md border px-3 disabled:opacity-50"
              disabled={
                brief.isFetching || !journal.identity || journal.blocked
              }
              onClick={() => void brief.refetch()}
            >
              Refresh summary
            </button>
            {brief.hasNextPage && (
              <button
                className="min-h-11 rounded-md border px-3 disabled:opacity-50"
                disabled={
                  brief.isFetching || !journal.identity || journal.blocked
                }
                onClick={() => void brief.fetchNextPage()}
              >
                Load more summary records
              </button>
            )}
            <button
              className="min-h-11 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50"
              disabled={disabled || dirty}
              onClick={() => {
                select();
                requestAnimationFrame(() => {
                  document
                    .getElementById('operator-journal')
                    ?.scrollIntoView({ block: 'start' });
                  document
                    .querySelector<HTMLInputElement>(
                      '#operator-journal input[name="title"]'
                    )
                    ?.focus();
                });
              }}
            >
              Record observation
            </button>
          </div>
        )}
      </div>
      <OperatorDisplayTools missionId={missionId} />
      {missionId && (
        <OperatorCommunications
          key={missionId}
          missionId={missionId}
          onDirty={setCallDirty}
        />
      )}
      {missionId && (
        <OperatorIssues key={`issues:${missionId}`} missionId={missionId} />
      )}
      <section
        id="operator-journal"
        aria-label="Operator journal"
        className="scroll-mt-4 space-y-5"
      >
        <h2 className="text-xl font-semibold">Operator journal</h2>
        <p role="status" aria-live="polite">
          {journal.saving
            ? journal.pending
              ? 'Saving…'
              : 'Rereading…'
            : dirty
              ? 'Unsaved changes.'
              : journal.saved
                ? 'Saved.'
                : ''}
        </p>
        <p>
          Mission notes and call observations. Select a mission and choose the
          entry scope explicitly.
        </p>
        <form
          className="flex min-w-0 flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!locked && !dirty && !journal.blocked) {
              setParams({ mission_id: missionDraft });
              select();
              setHistoryId(undefined);
            }
          }}
        >
          <label className="min-w-0 flex-1">
            Mission ID
            <input
              className="min-h-11 w-full min-w-0 rounded-md border bg-background px-3"
              required
              value={missionDraft}
              disabled={locked || dirty || journal.blocked}
              onChange={(e) => setMissionDraft(e.target.value)}
            />
          </label>
          <button
            className="min-h-11 rounded-md border px-4 disabled:opacity-50"
            disabled={locked || dirty || journal.blocked}
          >
            Open mission
          </button>
        </form>
        {unavailable && (
          <p role="alert">
            Operator store unavailable. Drafts remain here; saving is
            unavailable.{' '}
            <button
              className="min-h-11 underline"
              onClick={() => void journal.health.refetch()}
            >
              Check availability
            </button>
          </p>
        )}
        {journal.error && (
          <div
            role="alert"
            className="space-y-2 break-words rounded-lg border p-4 [overflow-wrap:anywhere]"
          >
            <p>{journal.error.message}</p>
            {journal.error.fields && (
              <ul>
                {Object.entries(journal.error.fields).map(
                  ([field, message]) => (
                    <li key={field}>
                      {field}: {message}
                    </li>
                  )
                )}
              </ul>
            )}
            {journal.pending && !journal.blocked && (
              <>
                <p>
                  Save outcome is uncertain. Retry sends the original entry
                  unchanged.
                </p>
                <button
                  className="min-h-11 rounded-md border px-3"
                  disabled={journal.saving}
                  onClick={async () => {
                    const receipt = await journal.retry();
                    if (receipt) select(receipt.current, true);
                  }}
                >
                  Retry exact save
                </button>
              </>
            )}
            {journal.blocked && (
              <>
                <p>
                  Reread and reconcile before another save. Your draft is
                  retained.
                </p>
                {journal.reconcileError && (
                  <p role="alert">{journal.reconcileError}</p>
                )}
                {journal.missingInNewStore && (
                  <button
                    className="min-h-11 rounded-md border px-3"
                    disabled={journal.saving}
                    onClick={() => {
                      if (journal.recoverMissing()) setCreateFromDraft(true);
                    }}
                  >
                    Keep draft as new entry
                  </button>
                )}
                {journal.latest && (
                  <p>
                    Latest saved version {journal.latest.record.version}:{' '}
                    {journal.latest.record.payload.title} ·{' '}
                    {journal.latest.record.payload.note}
                  </p>
                )}
                <button
                  className="min-h-11 rounded-md border px-3"
                  disabled={journal.saving}
                  onClick={async () => {
                    const reconciled = await journal.reconcile();
                    if (reconciled) select(reconciled.current);
                  }}
                >
                  Reread and use saved state
                </button>
              </>
            )}
          </div>
        )}
        {missionId ? (
          <>
            <div className="flex flex-wrap gap-3">
              <button
                className="min-h-11 rounded-md border px-3 disabled:opacity-50"
                disabled={locked || dirty || journal.blocked}
                onClick={() => select()}
              >
                New entry
              </button>
              {dirty && !locked && !journal.blocked && (
                <button
                  className="min-h-11 rounded-md border px-3"
                  onClick={() => select(createFromDraft ? undefined : selected)}
                >
                  Discard draft
                </button>
              )}
              {dirty && (
                <p className="py-2 text-sm">
                  Unsaved draft — save or discard before switching entries or
                  missions.
                </p>
              )}
            </div>
            <div className="grid min-w-0 gap-6 lg:grid-cols-2">
              <JournalEditor
                key={`${missionId}:${selected?.record_id ?? 'new'}:${editorVersion}`}
                missionId={missionId}
                record={selected}
                asNewEntry={createFromDraft}
                disabled={
                  disabled || (!createFromDraft && selected?.deleted === true)
                }
                onSave={(command) => void save(command)}
                onDirty={setDirty}
              />
              <div className="min-w-0 space-y-4">
                {journal.records.isError && (
                  <p role="alert">
                    Journal entries unavailable.{' '}
                    <button
                      className="min-h-11 underline"
                      onClick={() => void journal.records.refetch()}
                    >
                      Retry entries
                    </button>
                  </p>
                )}
                {journal.records.isFetching && !journal.records.data && (
                  <p>Loading journal entries…</p>
                )}
                {journal.records.data &&
                  !unavailable &&
                  !journal.records.isError && (
                    <JournalList
                      items={journal.records.data.pages.flatMap((page) =>
                        page.items.filter(
                          (item) =>
                            item.record.payload.entry_type !==
                            'capability_assessment'
                        )
                      )}
                      disabled={disabled || dirty}
                      onEdit={select}
                      onHistory={setHistoryId}
                      onTransition={(record) =>
                        void save({
                          operation: record.deleted ? 'restore' : 'remove',
                          record_id: record.record_id,
                          body: {
                            schema_version: 1,
                            expected_version: record.version,
                          },
                        })
                      }
                    />
                  )}
                {journal.records.hasNextPage && (
                  <button
                    className="min-h-11 border px-3"
                    disabled={journal.records.isFetchingNextPage}
                    onClick={() => void journal.records.fetchNextPage()}
                  >
                    More entries
                  </button>
                )}
                {historyId &&
                  journal.identity &&
                  !journal.blocked &&
                  !unavailable && (
                    <JournalHistory
                      id={historyId}
                      identity={journal.identity}
                      onClose={() => setHistoryId(undefined)}
                    />
                  )}
              </div>
            </div>
          </>
        ) : (
          <p>Enter a mission ID to open its journal.</p>
        )}
      </section>
    </main>
  );
}
