import { useState } from 'react';
import { UtcDateTime, type UtcParts } from './UtcDateTime';
import { createNoteTime } from './noteTime';
import type {
  JournalInput,
  OperatorCommand,
  SavedRecord,
  Scope,
} from '@/types/operator';
interface Props {
  formId?: string;
  missionId: string;
  record?: SavedRecord;
  disabled: boolean;
  onSave: (command: OperatorCommand) => void;
  onDirty?: (dirty: boolean) => void;
  asNewEntry?: boolean;
  draft?: JournalInput;
  onChange?: (draft: JournalInput) => void;
  auditNote?: string;
  onAuditNoteChange?: (value: string) => void;
  contextual?: boolean;
  saveDisabled?: boolean;
  occurrenceParts?: UtcParts;
  onOccurrencePartsChange?: (parts: UtcParts) => void;
}
const control =
  'min-h-11 w-full min-w-0 rounded-md border border-input bg-background px-3 py-2';
export function JournalEditor({
  formId,
  missionId,
  record,
  disabled,
  onSave,
  onDirty,
  asNewEntry,
  draft: controlledDraft,
  onChange,
  auditNote,
  onAuditNoteChange,
  contextual = false,
  saveDisabled = false,
  occurrenceParts,
  onOccurrencePartsChange,
}: Props) {
  const [base] = useState(record);
  const [localDraft, setDraft] = useState<JournalInput>(() => ({
    schema_version: 1,
    record_type: 'journal_entry',
    mission_id: record?.mission_id ?? missionId,
    leg_id: record?.leg_id ?? null,
    scope: record?.scope ?? 'mission',
    time: record ? { ...record.time } : createNoteTime(),
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
  const draft = controlledDraft ?? localDraft;
  const [localAudit, setAudit] = useState('');
  const audit = auditNote ?? localAudit;
  const target = asNewEntry ? undefined : base;
  function change(update: Partial<JournalInput>) {
    const next = { ...draft, ...update };
    setDraft(next);
    onChange?.(next);
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
      id={formId}
      className="min-w-0 space-y-4 rounded-lg border bg-card p-4"
      onSubmit={(event) => {
        event.preventDefault();
        const title =
          draft.payload.title.trim() ||
          draft.payload.note.trim().split(/\r?\n/)[0].slice(0, 200);
        if (disabled || saveDisabled || !title) return;
        const body = { ...draft, payload: { ...draft.payload, title } };
        onSave(
          target
            ? {
                operation: 'update',
                record_id: target.record_id,
                body: {
                  ...body,
                  expected_version: target.version,
                  ...(audit.trim() ? { audit_note: audit } : {}),
                },
              }
            : { operation: 'create', body }
        );
      }}
    >
      <h2 className="text-lg font-semibold">
        {target ? `Edit entry · version ${target.version}` : 'New note'}
      </h2>
      <fieldset
        disabled={disabled}
        className="min-w-0 space-y-4 disabled:opacity-70"
      >
        {!contextual && (
          <>
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
          </>
        )}
        <label className="block">
          Note
          <textarea
            className={control}
            rows={5}
            maxLength={8000}
            value={draft.payload.note}
            onChange={(e) =>
              payload({
                note: e.target.value,
                ...(!target && draft.payload.entry_type === 'note'
                  ? {
                      title: e.target.value
                        .trim()
                        .split(/\r?\n/)[0]
                        .slice(0, 200),
                    }
                  : {}),
              })
            }
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm">
            Occurrence:{' '}
            {draft.time.occurred_at
              ? `${draft.time.occurred_at.slice(0, 16).replace('T', ' ')} Zulu`
              : 'Unknown'}
          </span>
          <button
            type="button"
            className="min-h-11 rounded-md border px-3"
            onClick={() => {
              const nextTime = createNoteTime();
              onOccurrencePartsChange?.({
                date: nextTime.occurred_at!.slice(0, 10),
                time: nextTime.occurred_at!.slice(11, 16),
              });
              change({ time: nextTime });
            }}
          >
            Now
          </button>
        </div>
        <details>
          <summary className="min-h-11 cursor-pointer">
            Backdate / change occurrence
          </summary>
          <UtcDateTime
            label="Occurred at"
            value={draft.time.occurred_at}
            parts={occurrenceParts}
            onPartsChange={onOccurrencePartsChange}
            onChange={(value) =>
              time({
                occurred_at: value,
                ...(!target
                  ? {
                      precision: value ? 'exact' : 'unknown',
                      end_state: value ? 'instant' : 'unknown',
                    }
                  : {}),
              })
            }
          />
        </details>
        <details>
          <summary className="min-h-11 cursor-pointer">
            Historical entry details
          </summary>
          <div className="space-y-3">
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
                name="title"
                className={control}
                maxLength={200}
                value={draft.payload.title}
                onChange={(e) => payload({ title: e.target.value })}
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
              <UtcDateTime
                label="Ended at"
                value={draft.time.ended_at}
                required
                onChange={(value) => time({ ended_at: value })}
              />
            )}
          </div>
        </details>
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
                onAuditNoteChange?.(e.target.value);
                onDirty?.(true);
              }}
            />
          </label>
        )}
      </fieldset>
      <button
        className="min-h-11 rounded-md bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
        type="submit"
        hidden={!!formId}
        disabled={disabled || saveDisabled}
      >
        Save entry
      </button>
    </form>
  );
}
