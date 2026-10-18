import { useState } from 'react';
import type {
  CallInput,
  CallPayload,
  Scope,
  SavedRecord,
} from '@/types/operator';
import { shiftCallTime } from './callTiming';
const fieldClass =
  'min-h-11 w-full min-w-0 rounded-md border bg-background px-3 py-2';
const buttonClass = 'min-h-11 rounded-md border px-3 disabled:opacity-50';
function whole(value: string, max: number): number | null {
  if (!value.trim()) return null;
  if (!/^\d+$/.test(value) || Number(value) > max)
    throw new Error(
      `Enter whole minutes from 0 to ${max}, or leave blank for unknown.`
    );
  return Number(value);
}
function timestamp(value: string | null) {
  if (!value) return null;
  if (
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(value) ||
    !Number.isFinite(Date.parse(value))
  )
    throw new Error(
      'Enter UTC as YYYY-MM-DDTHH:MM:SSZ, or leave blank for unknown.'
    );
  // Reject calendar normalization such as February 30 while retaining microseconds.
  if (new Date(value).toISOString().slice(0, 19) !== value.slice(0, 19))
    throw new Error('Enter a valid UTC calendar date and time.');
  return value;
}
export interface CallEditorState {
  lead: string;
  duration: string;
  shift: string;
  unit: string;
  originalTime: CallInput['time'];
  originalDuration: string;
}
export function CallEditor({
  draft,
  disabled,
  creating = true,
  onChange,
  onSubmit,
  onDirty,
  saveDisabled = false,
  editorState,
  onEditorStateChange,
  records,
  contextual = false,
}: {
  draft: CallInput;
  disabled: boolean;
  creating?: boolean;
  onChange: (draft: CallInput) => void;
  onSubmit: (draft: CallInput) => void;
  onDirty?: () => void;
  saveDisabled?: boolean;
  editorState?: Partial<CallEditorState>;
  onEditorStateChange?: (state: CallEditorState) => void;
  records?: SavedRecord[];
  contextual?: boolean;
}) {
  const [lead, setLead] = useState(
    editorState?.lead ??
      (draft.payload.prep_lead_minutes == null
        ? ''
        : String(draft.payload.prep_lead_minutes))
  );
  const [duration, setDuration] = useState(
    editorState?.duration ??
      (draft.time.planned_start_at && draft.time.planned_end_at
        ? String(
            (Date.parse(draft.time.planned_end_at) -
              Date.parse(draft.time.planned_start_at)) /
              60000
          )
        : '')
  );
  const [originalTime] = useState(
    editorState?.originalTime ?? { ...draft.time }
  );
  const [originalDuration] = useState(
    editorState?.originalDuration ?? duration
  );
  const [shift, setShift] = useState(editorState?.shift ?? '');
  const [unit, setUnit] = useState(editorState?.unit ?? 'minutes');
  const [error, setError] = useState<string | null>(null);
  function retain(patch: Partial<CallEditorState>) {
    onEditorStateChange?.({
      lead,
      duration,
      shift,
      unit,
      originalTime,
      originalDuration,
      ...patch,
    });
  }
  const payload = (patch: Partial<CallPayload>) =>
    onChange({ ...draft, payload: { ...draft.payload, ...patch } });
  const time = (
    name: 'planned_start_at' | 'occurred_at' | 'ended_at',
    value: string
  ) => onChange({ ...draft, time: { ...draft.time, [name]: value || null } });
  function submit() {
    try {
      const start = timestamp(draft.time.planned_start_at);
      const actual = timestamp(draft.time.occurred_at);
      const end = timestamp(draft.time.ended_at);
      if (creating && draft.payload.status === 'scheduled' && !start)
        throw new Error('Scheduled calls require a planned start.');
      if (end && (!actual || Date.parse(end) < Date.parse(actual)))
        throw new Error('Actual end requires a start and cannot precede it.');
      let minutes: number | null = null;
      if (duration.trim()) {
        if (
          !/^\d+(?:\.\d+)?$/.test(duration) ||
          !Number.isFinite(Number(duration)) ||
          Number(duration) > 525600
        )
          throw new Error(
            'Enter duration minutes from 0 to 525600, or leave blank for unknown.'
          );
        minutes = Number(duration);
      }
      if (minutes !== null && !start)
        throw new Error('Duration requires a planned start.');
      if (draft.scope === 'leg' && !draft.leg_id?.trim())
        throw new Error('Choose a leg ID for leg scope.');
      const plannedEnd =
        start === originalTime.planned_start_at && duration === originalDuration
          ? originalTime.planned_end_at
          : start && minutes !== null
            ? new Date(Date.parse(start) + minutes * 60000).toISOString()
            : null;
      const value: CallInput = {
        ...draft,
        time: {
          ...draft.time,
          planned_start_at: start,
          planned_end_at: plannedEnd,
          occurred_at: actual,
          ended_at: end,
          precision: actual
            ? draft.time.precision === 'unknown'
              ? 'exact'
              : draft.time.precision
            : 'unknown',
          end_state: end
            ? 'known'
            : actual
              ? draft.time.end_state === 'ongoing'
                ? 'ongoing'
                : 'unknown'
              : 'unknown',
        },
        payload: {
          ...draft.payload,
          title:
            draft.payload.party?.trim() ||
            draft.payload.title ||
            'Unscheduled call',
          prep_lead_minutes: whole(lead, 10080),
        },
      };
      setError(null);
      onSubmit(value);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <form
      aria-label="Call editor"
      className="min-w-0 space-y-3 rounded-xl border bg-card p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled && !saveDisabled) submit();
      }}
    >
      <h3 className="text-lg font-semibold">
        {draft.payload.status === 'completed' && !draft.time.planned_start_at
          ? 'Completed / unscheduled call'
          : 'Communication requirement'}
      </h3>
      <p className="text-sm text-muted-foreground">
        All dates and times are UTC. Blank optional fields remain unknown.
      </p>
      {error && <p role="alert">{error}</p>}
      <fieldset
        onChange={onDirty}
        disabled={disabled}
        className="min-w-0 space-y-3 disabled:opacity-60"
      >
        <label className="block">
          Party / participant (optional)
          <input
            className={fieldClass}
            maxLength={200}
            value={draft.payload.party ?? ''}
            onChange={(e) => payload({ party: e.target.value || null })}
          />
        </label>
        <label className="block">
          Planned start (UTC)
          <input
            className={fieldClass}
            placeholder="2026-10-17T16:00:00Z"
            value={draft.time.planned_start_at ?? ''}
            onChange={(e) => time('planned_start_at', e.target.value)}
          />
        </label>
        <label className="block">
          Status
          <select
            aria-label="Status"
            className={fieldClass}
            value={draft.payload.status}
            onChange={(e) =>
              payload({ status: e.target.value as CallPayload['status'] })
            }
          >
            {[
              'tentative',
              'scheduled',
              'delayed',
              'cancelled',
              'completed',
            ].map((status) => (
              <option key={status} value={status}>
                {status === 'cancelled'
                  ? 'Canceled'
                  : status[0].toUpperCase() + status.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <details>
          <summary className="min-h-11 cursor-pointer py-2">
            Timing, association and optional details
          </summary>
          <div className="space-y-3">
            <label className="block">
              Communications type
              <select
                aria-label="Communications type"
                className={fieldClass}
                value={draft.payload.communications_kind ?? ''}
                onChange={(e) =>
                  payload({
                    communications_kind: (e.target.value ||
                      null) as CallPayload['communications_kind'],
                  })
                }
              >
                <option value="">Unknown</option>
                <option value="voice">Voice</option>
                <option value="vtc">VTC</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="block">
              Duration minutes (blank = unknown)
              <input
                className={fieldClass}
                inputMode="numeric"
                value={duration}
                onChange={(e) => {
                  setDuration(e.target.value);
                  retain({ duration: e.target.value });
                }}
              />
            </label>
            <label className="block">
              Preparation lead minutes (blank = unknown)
              <input
                className={fieldClass}
                inputMode="numeric"
                value={lead}
                onChange={(e) => {
                  setLead(e.target.value);
                  retain({ lead: e.target.value });
                }}
              />
            </label>
            <div className="flex min-w-0 flex-wrap items-end gap-2">
              <label className="min-w-0 flex-1">
                Shift amount
                <input
                  className={fieldClass}
                  inputMode="text"
                  placeholder="+2 or -15"
                  value={shift}
                  onChange={(e) => {
                    setShift(e.target.value);
                    retain({ shift: e.target.value });
                  }}
                />
              </label>
              <label>
                Shift unit
                <select
                  aria-label="Shift unit"
                  className={fieldClass}
                  value={unit}
                  onChange={(e) => {
                    setUnit(e.target.value);
                    retain({ unit: e.target.value });
                  }}
                >
                  <option value="minutes">Minutes</option>
                  <option value="hours">Hours</option>
                </select>
              </label>
              <button
                type="button"
                className={buttonClass}
                onClick={() => {
                  try {
                    if (!/^[+-]?\d+$/.test(shift))
                      throw new Error('Enter a signed whole-number shift.');
                    onChange({
                      ...draft,
                      time: shiftCallTime(
                        draft.time,
                        Number(shift) * (unit === 'hours' ? 60 : 1)
                      ),
                    });
                    setError(null);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Apply shift
              </button>
            </div>
            <label className="block">
              Actual start (UTC, optional)
              <input
                className={fieldClass}
                placeholder="2026-10-17T14:30:00Z"
                value={draft.time.occurred_at ?? ''}
                onChange={(e) => time('occurred_at', e.target.value)}
              />
            </label>
            <label className="block">
              Actual end (UTC, optional)
              <input
                className={fieldClass}
                placeholder="2026-10-17T14:42:00Z"
                value={draft.time.ended_at ?? ''}
                onChange={(e) => time('ended_at', e.target.value)}
              />
            </label>
            <label className="block">
              Actual time precision
              <select
                aria-label="Actual time precision"
                className={fieldClass}
                value={draft.time.precision}
                onChange={(e) =>
                  onChange({
                    ...draft,
                    time: {
                      ...draft.time,
                      precision: e.target
                        .value as CallInput['time']['precision'],
                    },
                  })
                }
              >
                <option value="unknown">Unknown</option>
                <option value="exact">Exact</option>
                <option value="approximate">Approximate</option>
              </select>
            </label>
            <label className="block">
              Ground coordinator (optional)
              <input
                className={fieldClass}
                maxLength={200}
                value={draft.payload.coordinator ?? ''}
                onChange={(e) =>
                  payload({ coordinator: e.target.value || null })
                }
              />
            </label>
            <label className="block">
              {records
                ? 'Conference (optional)'
                : 'Conference record ID (optional)'}
              {records ? (
                <select
                  className={fieldClass}
                  value={draft.payload.conference_id ?? ''}
                  onChange={(event) =>
                    payload({ conference_id: event.target.value || null })
                  }
                >
                  <option value="">Unknown / unassigned</option>
                  {draft.payload.conference_id &&
                    !records.some(
                      (record) =>
                        record.record_id === draft.payload.conference_id
                    ) && (
                      <option value={draft.payload.conference_id}>
                        Unresolved conference · {draft.payload.conference_id}
                      </option>
                    )}
                  {records
                    .filter(
                      (record) =>
                        record.record_type === 'conference' && !record.deleted
                    )
                    .map((record) => (
                      <option key={record.record_id} value={record.record_id}>
                        {record.payload.title}
                      </option>
                    ))}
                </select>
              ) : (
                <input
                  className={fieldClass}
                  value={draft.payload.conference_id ?? ''}
                  onChange={(e) =>
                    payload({ conference_id: e.target.value || null })
                  }
                />
              )}
            </label>
            <label className="block" hidden={contextual}>
              Scope
              <select
                aria-label="Scope"
                className={fieldClass}
                value={draft.scope}
                onChange={(e) =>
                  onChange({
                    ...draft,
                    scope: e.target.value as Scope,
                    leg_id: e.target.value === 'leg' ? draft.leg_id : null,
                  })
                }
              >
                {[
                  'mission',
                  'preflight',
                  'leg',
                  'between_legs',
                  'postflight',
                ].map((scope) => (
                  <option key={scope} value={scope}>
                    {scope.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
            {draft.scope === 'leg' && (
              <label className="block">
                Leg ID
                <input
                  className={fieldClass}
                  value={draft.leg_id ?? ''}
                  onChange={(e) =>
                    onChange({ ...draft, leg_id: e.target.value || null })
                  }
                />
              </label>
            )}
            {draft.scope === 'between_legs' && (
              <>
                <label className="block">
                  Previous leg ID (optional)
                  <input
                    className={fieldClass}
                    value={draft.payload.previous_leg_id ?? ''}
                    onChange={(e) =>
                      payload({ previous_leg_id: e.target.value || null })
                    }
                  />
                </label>
                <label className="block">
                  Next leg ID (optional)
                  <input
                    className={fieldClass}
                    value={draft.payload.next_leg_id ?? ''}
                    onChange={(e) =>
                      payload({ next_leg_id: e.target.value || null })
                    }
                  />
                </label>
              </>
            )}
            <label className="block">
              Notes (optional)
              <textarea
                className={fieldClass}
                maxLength={8000}
                value={draft.payload.note}
                onChange={(e) => payload({ note: e.target.value })}
              />
            </label>
          </div>
        </details>
        <button
          className="min-h-11 rounded-md bg-primary px-4 text-primary-foreground disabled:opacity-50"
          type="submit"
          disabled={saveDisabled}
        >
          Save call
        </button>
      </fieldset>
    </form>
  );
}
