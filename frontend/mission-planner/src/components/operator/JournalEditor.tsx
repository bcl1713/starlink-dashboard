import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { readOperatorRecords } from '@/services/operator';
import { unknownTime } from './issueForms';
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
  captureNow?: () => Promise<string>;
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
  captureNow,
}: Props) {
  const [base] = useState(record);
  const [localDraft, setDraft] = useState<JournalInput>(() => ({
    schema_version: 1,
    record_type: 'journal_entry',
    mission_id: record?.mission_id ?? missionId,
    leg_id: record?.leg_id ?? null,
    scope: record?.scope ?? 'mission',
    time: record ? { ...record.time } : { ...unknownTime },
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
  const latestDraft = useRef(draft);
  useLayoutEffect(() => {
    latestDraft.current = draft;
  }, [draft]);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const needsInitialClock = !record && !controlledDraft;
  const [capturing, setCapturing] = useState(needsInitialClock);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [initialCapture] = useState(
    () =>
      captureNow ??
      (async () =>
        (await readOperatorRecords({ mission_id: missionId, limit: 1 })).as_of)
  );
  useEffect(() => {
    if (!needsInitialClock) return;
    let active = true;
    void initialCapture()
      .then((now) => {
        if (!active) return;
        if (!now || !Number.isFinite(Date.parse(now)))
          throw new Error('Source clock unavailable');
        const next = { ...latestDraft.current, time: createNoteTime(now) };
        latestDraft.current = next;
        setDraft(next);
        onChange?.(next);
      })
      .catch(() => {
        if (active)
          setCaptureError(
            'Could not read the source clock. Retry Now or choose a backdate.'
          );
      })
      .finally(() => {
        if (active) setCapturing(false);
      });
    return () => {
      active = false;
    };
    // The initial occurrence belongs to this editor instance, not later refetches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCapture, needsInitialClock]);
  const [localAudit, setAudit] = useState('');
  const audit = auditNote ?? localAudit;
  const target = asNewEntry ? undefined : base;
  function change(update: Partial<JournalInput>) {
    const next = { ...draft, ...update };
    latestDraft.current = next;
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
  async function chooseNow() {
    if (capturing) return;
    setCapturing(true);
    setCaptureError(null);
    try {
      const now = await (
        captureNow ??
        (async () =>
          (
            await readOperatorRecords({
              mission_id: draft.mission_id,
              limit: 1,
            })
          ).as_of)
      )();
      if (!mounted.current) return;
      if (!now || !Number.isFinite(Date.parse(now)))
        throw new Error('Source clock unavailable');
      const current = latestDraft.current;
      const nextTime = target
        ? {
            ...current.time,
            occurred_at: now,
            precision:
              current.time.precision === 'unknown'
                ? ('exact' as const)
                : current.time.precision,
          }
        : createNoteTime(now);
      onOccurrencePartsChange?.({
        date: now.slice(0, 10),
        time: now.slice(11, 16),
      });
      const next = { ...current, time: nextTime };
      latestDraft.current = next;
      setDraft(next);
      onChange?.(next);
      onDirty?.(true);
    } catch {
      if (mounted.current)
        setCaptureError(
          'Could not read the source clock. Retry Now or choose a backdate.'
        );
    } finally {
      if (mounted.current) setCapturing(false);
    }
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
        if (disabled || saveDisabled || capturing || !title) return;
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
        {target ? `Edit Entry · Version ${target.version}` : 'New Note'}
      </h2>
      <fieldset
        disabled={disabled}
        className="min-w-0 space-y-4 disabled:opacity-70"
      >
        {!contextual && (
          <>
            <label className="block">
              Entry Mission ID
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
                  <option value="between_legs">Between Legs</option>
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
                    Previous Leg ID (Optional)
                    <input
                      className={control}
                      value={draft.payload.previous_leg_id ?? ''}
                      onChange={(e) =>
                        payload({ previous_leg_id: e.target.value || null })
                      }
                    />
                  </label>
                  <label>
                    Next Leg ID (Optional)
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
            disabled={capturing}
            onClick={() => void chooseNow()}
          >
            Now
          </button>
        </div>
        {captureError && <p role="alert">{captureError}</p>}
        {capturing && <p role="status">Capturing Current Zulu…</p>}
        <details>
          <summary className="min-h-11 cursor-pointer">
            Backdate / Change Occurrence
          </summary>
          <UtcDateTime
            label="Occurred At"
            required={draft.time.precision !== 'unknown'}
            disabled={capturing}
            value={draft.time.occurred_at}
            parts={occurrenceParts}
            onPartsChange={onOccurrencePartsChange}
            onChange={(value) =>
              time(
                value
                  ? {
                      occurred_at: value,
                      precision:
                        draft.time.precision === 'unknown'
                          ? 'exact'
                          : draft.time.precision,
                      ...(!target ? { end_state: 'instant' } : {}),
                    }
                  : target
                    ? { occurred_at: null }
                    : {
                        occurred_at: null,
                        precision: 'unknown',
                        ended_at: null,
                        end_state: 'unknown',
                      }
              )
            }
          />
        </details>
        <details>
          <summary className="min-h-11 cursor-pointer">
            Historical Entry Details
          </summary>
          <div className="space-y-3">
            <label className="block">
              Entry Type
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
                <option value="call_observation">Call Observation</option>
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
              Time Precision
              <select
                className={control}
                value={draft.time.precision}
                onChange={(e) => {
                  if (e.target.value === 'unknown')
                    onOccurrencePartsChange?.({ date: '', time: '' });
                  time(
                    e.target.value === 'unknown'
                      ? {
                          precision: 'unknown',
                          occurred_at: null,
                          ended_at: null,
                          end_state: 'unknown',
                        }
                      : { precision: e.target.value as 'exact' | 'approximate' }
                  );
                }}
              >
                <option value="unknown">Unknown</option>
                <option value="approximate">Approximate</option>
                <option value="exact">Exact</option>
              </select>
            </label>
            <label>
              End State
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
                label="Ended At"
                value={draft.time.ended_at}
                required
                onChange={(value) => time({ ended_at: value })}
              />
            )}
          </div>
        </details>
        {target && (
          <label className="block">
            Audit Note (Optional)
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
        disabled={disabled || saveDisabled || capturing}
      >
        Save Entry
      </button>
    </form>
  );
}
