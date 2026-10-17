import { useState } from 'react';
import type {
  JournalInput,
  OperatorCommand,
  SavedRecord,
  Scope,
} from '@/types/operator';
interface Props {
  missionId: string;
  record?: SavedRecord;
  disabled: boolean;
  onSave: (command: OperatorCommand) => void;
  onDirty?: (dirty: boolean) => void;
  asNewEntry?: boolean;
}
const control =
  'min-h-11 w-full min-w-0 rounded-md border border-input bg-background px-3 py-2';
export function JournalEditor({
  missionId,
  record,
  disabled,
  onSave,
  onDirty,
  asNewEntry,
}: Props) {
  const [base] = useState(record);
  const [draft, setDraft] = useState<JournalInput>(() => ({
    schema_version: 1,
    record_type: 'journal_entry',
    mission_id: record?.mission_id ?? missionId,
    leg_id: record?.leg_id ?? null,
    scope: record?.scope ?? 'mission',
    time: record
      ? { ...record.time }
      : {
          occurred_at: null,
          ended_at: null,
          precision: 'unknown',
          end_state: 'unknown',
          planned_start_at: null,
          planned_end_at: null,
        },
    payload: record
      ? {
          ...record.payload,
          entry_type:
            record.payload.entry_type === 'call_observation'
              ? 'call_observation'
              : 'note',
        }
      : {
          schema_version: 1,
          entry_type: 'note',
          title: '',
          note: '',
          previous_leg_id: null,
          next_leg_id: null,
        },
  }));
  const [audit, setAudit] = useState('');
  const target = asNewEntry ? undefined : base;
  function change(update: Partial<JournalInput>) {
    setDraft((d) => ({ ...d, ...update }));
    onDirty?.(true);
  }
  function payload(update: Partial<JournalInput['payload']>) {
    change({ payload: { ...draft.payload, ...update } });
  }
  function time(update: Partial<JournalInput['time']>) {
    change({ time: { ...draft.time, ...update } });
  }
  return (
    <form
      className="min-w-0 space-y-4 rounded-lg border bg-card p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (disabled || !draft.payload.title.trim()) return;
        onSave(
          target
            ? {
                operation: 'update',
                record_id: target.record_id,
                body: {
                  ...draft,
                  expected_version: target.version,
                  ...(audit.trim() ? { audit_note: audit } : {}),
                },
              }
            : { operation: 'create', body: draft }
        );
      }}
    >
      <h2 className="text-lg font-semibold">
        {target
          ? `Edit entry · version ${target.version}`
          : 'New journal entry'}
      </h2>
      <fieldset
        disabled={disabled}
        className="min-w-0 space-y-4 disabled:opacity-70"
      >
        <label className="block">
          Entry mission ID
          <input
            className={control}
            required
            value={draft.mission_id}
            onChange={(e) => change({ mission_id: e.target.value })}
          />
        </label>
        <div className="grid min-w-0 gap-4 sm:grid-cols-2">
          <label>
            Scope
            <select
              className={control}
              value={draft.scope}
              onChange={(e) =>
                change({
                  scope: e.target.value as Scope,
                  leg_id: e.target.value === 'leg' ? '' : null,
                })
              }
            >
              <option value="mission">Mission</option>
              <option value="preflight">Preflight</option>
              <option value="leg">Leg</option>
              <option value="between_legs">Between legs</option>
              <option value="postflight">Postflight</option>
            </select>
          </label>
          {draft.scope === 'leg' && (
            <label>
              Leg ID
              <input
                className={control}
                required
                value={draft.leg_id ?? ''}
                onChange={(e) => change({ leg_id: e.target.value })}
              />
            </label>
          )}
          {draft.scope === 'between_legs' && (
            <>
              <label>
                Previous leg ID (optional)
                <input
                  className={control}
                  value={draft.payload.previous_leg_id ?? ''}
                  onChange={(e) =>
                    payload({ previous_leg_id: e.target.value || null })
                  }
                />
              </label>
              <label>
                Next leg ID (optional)
                <input
                  className={control}
                  value={draft.payload.next_leg_id ?? ''}
                  onChange={(e) =>
                    payload({ next_leg_id: e.target.value || null })
                  }
                />
              </label>
            </>
          )}
        </div>
        <label className="block">
          Entry type
          <select
            className={control}
            value={draft.payload.entry_type}
            onChange={(e) =>
              payload({
                entry_type: e.target.value as 'note' | 'call_observation',
              })
            }
          >
            <option value="note">Note</option>
            <option value="call_observation">Call observation</option>
          </select>
        </label>
        <label className="block">
          Title
          <input
            className={control}
            required
            maxLength={200}
            value={draft.payload.title}
            onChange={(e) => payload({ title: e.target.value })}
          />
        </label>
        <label className="block">
          Note
          <textarea
            className={control}
            rows={5}
            maxLength={8000}
            value={draft.payload.note}
            onChange={(e) => payload({ note: e.target.value })}
          />
        </label>
        <label className="block">
          Time precision
          <select
            className={control}
            value={draft.time.precision}
            onChange={(e) =>
              time(
                e.target.value === 'unknown'
                  ? {
                      precision: 'unknown',
                      occurred_at: null,
                      ended_at: null,
                      end_state: 'unknown',
                    }
                  : { precision: e.target.value as 'exact' | 'approximate' }
              )
            }
          >
            <option value="unknown">Unknown</option>
            <option value="approximate">Approximate</option>
            <option value="exact">Exact</option>
          </select>
        </label>
        <p className="text-sm text-muted-foreground">
          All times are UTC. Enter YYYY-MM-DDTHH:mm:ss.ssssssZ; leave unknown
          times blank.
        </p>
        <div className="grid min-w-0 gap-4 sm:grid-cols-2">
          <label>
            Occurred at (UTC)
            <input
              className={control}
              type="text"
              placeholder="2026-10-17T12:00:00Z"
              disabled={draft.time.precision === 'unknown'}
              required={draft.time.precision !== 'unknown'}
              pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z"
              value={draft.time.occurred_at ?? ''}
              onChange={(e) => time({ occurred_at: e.target.value || null })}
            />
          </label>
          <label>
            End state
            <select
              className={control}
              disabled={draft.time.precision === 'unknown'}
              value={draft.time.end_state}
              onChange={(e) =>
                time({
                  end_state: e.target
                    .value as JournalInput['time']['end_state'],
                  ...(e.target.value === 'known' ? {} : { ended_at: null }),
                })
              }
            >
              <option value="unknown">Unknown</option>
              <option value="instant">Instant</option>
              <option value="ongoing">Ongoing</option>
              <option value="known">Known</option>
            </select>
          </label>
          {draft.time.end_state === 'known' && (
            <label>
              Ended at (UTC)
              <input
                className={control}
                required
                value={draft.time.ended_at ?? ''}
                onChange={(e) => time({ ended_at: e.target.value || null })}
              />
            </label>
          )}
        </div>
        {target && (
          <label className="block">
            Audit note (optional)
            <textarea
              className={control}
              rows={2}
              maxLength={1000}
              value={audit}
              onChange={(e) => {
                setAudit(e.target.value);
                onDirty?.(true);
              }}
            />
          </label>
        )}
      </fieldset>
      <button
        className="min-h-11 rounded-md bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
        type="submit"
        disabled={disabled}
      >
        Save entry
      </button>
    </form>
  );
}
