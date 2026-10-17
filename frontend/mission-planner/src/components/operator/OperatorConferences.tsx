import { useEffect, useState } from 'react';
import { readOperatorRecords } from '@/services/operator';
import type {
  ConferenceInput,
  ParticipationInput,
  OperatorCommand,
  SavedRecord,
} from '@/types/operator';
import { useOperatorJournal } from '@/hooks/api/useOperatorJournal';
import { useOperatorProtection } from '@/hooks/api/useOperatorProtection';
import {
  conferenceDraft,
  conferenceCommand,
  recordInput,
  joinCommand,
  leaveCommand,
  resumeCommand,
  unknownTime,
} from './conferenceCommands';
import { ConferenceCard } from './ConferenceCard';
import { ParticipationRow } from './ParticipationRow';
import { ConferenceEditor } from './ConferenceEditor';
import { ParticipationEditor } from './ParticipationEditor';
import { JournalHistory } from './JournalHistory';
import { revisionUtc } from './revisionUtc';
const button = 'min-h-11 rounded border px-3 disabled:opacity-50';
export function OperatorConferences({
  missionId,
  onDirty,
}: {
  missionId: string;
  onDirty?: (dirty: boolean) => void;
}) {
  const conferences = useOperatorJournal(missionId, 'conference');
  const customers = useOperatorJournal(missionId, 'participation');
  const calls = useOperatorJournal(missionId, 'call');
  const [draft, setDraft] = useState<ConferenceInput | ParticipationInput>();
  const [selected, setSelected] = useState<SavedRecord>();
  const [historyId, setHistoryId] = useState<string>();
  const [localError, setLocalError] = useState<string>();
  const [capturingTime, setCapturingTime] = useState(false);
  const hooks = [conferences, customers, calls];
  // Auto-page only bounded snapshots; no polling or repeated mutation.
  useEffect(() => {
    for (const hook of hooks)
      if (
        hook.records.hasNextPage &&
        !hook.records.isFetching &&
        !hook.records.isError
      )
        void hook.records.fetchNextPage();
  });
  const records = hooks.flatMap(
    (hook, index) =>
      hook.records.data?.pages
        .flatMap((p) => p.items.map((i) => i.record))
        .filter(
          (r) =>
            r.record_type === ['conference', 'participation', 'call'][index]
        ) ?? []
  );
  const complete = hooks.every(
    (h) => !!h.records.data && !h.records.hasNextPage && !h.records.isError
  );
  const asOf = conferences.records.data?.pages[0]?.as_of ?? '';
  const protection = useOperatorProtection(missionId, records, asOf, complete);
  const disabled =
    capturingTime ||
    hooks.some(
      (h) =>
        h.saving ||
        !!h.pending ||
        h.blocked ||
        !h.health.data?.ready ||
        h.health.isError
    );
  function edit(
    record?: SavedRecord,
    kind: 'conference' | 'participation' = 'conference'
  ) {
    const hook =
      (record?.record_type ?? kind) === 'conference' ? conferences : customers;
    hook.openEditor(record);
    setSelected(record);
    if (record) setDraft(recordInput(record));
    else if (kind === 'conference') setDraft(conferenceDraft(missionId));
    else
      setDraft({
        ...conferenceDraft(missionId),
        record_type: 'participation',
        payload: {
          ...conferenceDraft(missionId).payload,
          entry_type: 'participation',
          title: 'Customer interval',
          call_id: null,
          conference_id: null,
          participant: null,
          state: 'connected',
          resumes_participation_id: null,
        },
        time: { ...unknownTime },
      });
    onDirty?.(true);
  }
  function accept(result: { current?: SavedRecord } | undefined) {
    if (!result) return;
    setDraft(undefined);
    setSelected(undefined);
    onDirty?.(false);
    void conferences.records.refetch();
    void customers.records.refetch();
    void calls.records.refetch();
    void protection.refetch();
  }
  async function save(command: OperatorCommand, target?: SavedRecord) {
    setLocalError(undefined);
    const type =
      command.operation === 'create' || command.operation === 'update'
        ? command.body.record_type
        : target?.record_type;
    const hook = type === 'conference' ? conferences : customers;
    if (!draft) hook.openEditor(target);
    accept(await hook.save(command));
  }
  async function action(
    build: (now: string) => OperatorCommand,
    target: SavedRecord
  ) {
    if (capturingTime) return;
    setCapturingTime(true);
    try {
      const clock = await readOperatorRecords({
        mission_id: missionId,
        record_type: 'conference',
      });
      await save(build(clock.as_of), target);
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : 'Action unavailable'
      );
    } finally {
      setCapturingTime(false);
    }
  }
  function transition(record: SavedRecord) {
    void save(
      {
        operation: record.deleted ? 'restore' : 'remove',
        record_id: record.record_id,
        body: { schema_version: 1, expected_version: record.version },
      },
      record
    );
  }
  return (
    <section
      aria-label="Conferences and customers"
      className="space-y-3 border-t pt-4 [&_button]:min-h-11 [&_button]:rounded [&_button]:border [&_button]:px-3"
    >
      <h3 className="text-lg font-semibold">Conferences and customers</h3>
      <p>
        Conference readiness, customer presence and call completion are
        independent. UTC snapshot: {revisionUtc(asOf || null)}.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className={button}
          disabled={disabled || !!draft}
          onClick={() => edit()}
        >
          New conference
        </button>
        <button
          className={button}
          disabled={disabled || !!draft}
          onClick={() => edit(undefined, 'participation')}
        >
          Log customer interval
        </button>
        <button
          className={button}
          disabled={disabled}
          onClick={() => {
            hooks.forEach((h) => void h.records.refetch());
            void protection.refetch();
          }}
        >
          Refresh conferences and customers
        </button>
      </div>
      {!complete && (
        <p role="status">
          Operational list incomplete or unavailable. No all-clear is implied.
        </p>
      )}
      {hooks.some((h) => h.saving) && (
        <p role="status">Saving conference/customer action…</p>
      )}
      {hooks.some((h) => h.saved) && !draft && (
        <p role="status">Conference/customer action saved.</p>
      )}
      {localError && <p role="alert">{localError}</p>}
      {[conferences, customers].map((hook, index) => (
        <div key={index}>
          {hook.error && (
            <p role="alert">
              {hook.error.message} · {hook.error.code}
              {hook.error.fields &&
                ` · ${Object.values(hook.error.fields).join('; ')}`}
            </p>
          )}
          {hook.pending && !hook.blocked && (
            <button
              disabled={hook.saving}
              onClick={async () => accept(await hook.retry())}
            >
              Retry same {index === 0 ? 'conference' : 'customer'} save
            </button>
          )}
          {hook.blocked && (
            <button
              disabled={hook.saving}
              onClick={async () => {
                const result = await hook.reconcile();
                if (result && result.current) {
                  setSelected(result.current);
                  setDraft(recordInput(result.current));
                }
              }}
            >
              Reread {index === 0 ? 'conference' : 'customer'} state
            </button>
          )}
          {hook.reconcileError && <p role="alert">{hook.reconcileError}</p>}
        </div>
      ))}
      {draft && (
        <>
          <p role="status">
            Unsaved conference/customer draft. Save or discard before switching.
          </p>
          {draft.record_type === 'conference' ? (
            <ConferenceEditor
              draft={draft}
              disabled={disabled}
              onChange={setDraft}
              onSubmit={(input) =>
                void save(
                  selected
                    ? {
                        operation: 'update',
                        record_id: selected.record_id,
                        body: {
                          ...input,
                          payload: {
                            ...input.payload,
                            title: input.payload.title.trim() || 'Conference',
                          },
                          expected_version: selected.version,
                        },
                      }
                    : {
                        operation: 'create',
                        body: {
                          ...input,
                          payload: {
                            ...input.payload,
                            title: input.payload.title.trim() || 'Conference',
                          },
                        },
                      }
                )
              }
            />
          ) : (
            <ParticipationEditor
              draft={draft}
              records={records}
              disabled={disabled}
              onChange={setDraft}
              onSubmit={(input) =>
                void save(
                  selected
                    ? {
                        operation: 'update',
                        record_id: selected.record_id,
                        body: { ...input, expected_version: selected.version },
                      }
                    : { operation: 'create', body: input }
                )
              }
            />
          )}
          <button
            disabled={disabled}
            onClick={() => {
              setDraft(undefined);
              setSelected(undefined);
              onDirty?.(false);
            }}
          >
            Discard conference/customer draft
          </button>
        </>
      )}
      {records
        .filter((r) => r.record_type === 'conference')
        .map((record) => (
          <ConferenceCard
            key={record.record_id}
            record={record}
            participations={records}
            disabled={disabled || !!draft}
            onAction={(a) =>
              action((now) => conferenceCommand(record, a, now), record)
            }
            onEdit={() => edit(record)}
            onJoin={() =>
              action(
                (now) =>
                  joinCommand(
                    {
                      ...conferenceDraft(missionId),
                      record_type: 'participation',
                      payload: {
                        ...conferenceDraft(missionId).payload,
                        entry_type: 'participation',
                        title: 'Unknown customer',
                        participant: null,
                        call_id: null,
                        conference_id: record.record_id,
                        state: 'connected',
                        resumes_participation_id: null,
                      },
                    },
                    now
                  ),
                record
              )
            }
            onHistory={() => setHistoryId(record.record_id)}
            onRemove={() => transition(record)}
          />
        ))}
      {records
        .filter((r) => r.record_type === 'participation')
        .map((record) => (
          <ParticipationRow
            key={record.record_id}
            record={record}
            conference={
              record.payload.entry_type === 'participation'
                ? records.find(
                    (r) =>
                      record.payload.entry_type === 'participation' &&
                      r.record_id === record.payload.conference_id
                  )
                : undefined
            }
            disabled={disabled || !!draft}
            onAction={(a) =>
              action(
                (now) =>
                  a === 'restore'
                    ? resumeCommand(record, now)
                    : leaveCommand(record, a, now),
                record
              )
            }
            onEdit={() => edit(record)}
            onHistory={() => setHistoryId(record.record_id)}
            onRemove={() => transition(record)}
          />
        ))}
      <aside
        aria-label="Protected call advisories"
        className="space-y-2 rounded border p-3"
      >
        <h4 className="font-semibold">Protected call advisories</h4>
        <p>Coverage: {protection.snapshot.coverage}</p>
        {protection.snapshot.limitations.map((text) => (
          <p key={text}>{text}</p>
        ))}
        {!protection.snapshot.items.length && (
          <p>
            No overlaps found in the available snapshot. This is not an
            all-clear.
          </p>
        )}
        <ul>
          {protection.snapshot.items.map((item, index) => (
            <li key={index} className="border-t py-2">
              {item.classification.replaceAll('_', ' ')} · {item.relevance}{' '}
              transport relevance · leg {item.legId} · {revisionUtc(item.start)}{' '}
              to {revisionUtc(item.end)} · model computed{' '}
              {revisionUtc(item.computedAt)}
            </li>
          ))}
        </ul>
      </aside>
      {historyId && conferences.identity && (
        <JournalHistory
          id={historyId}
          identity={conferences.identity}
          onClose={() => setHistoryId(undefined)}
        />
      )}
    </section>
  );
}
