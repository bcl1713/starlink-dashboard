import type { ParticipationInput, SavedRecord } from '@/types/operator';
import { UtcDateTime } from './UtcDateTime';
const field = 'min-h-11 w-full rounded border bg-background p-2';
export function ParticipationEditor({
  formId,
  draft,
  records,
  disabled,
  onChange,
  onSubmit,
}: {
  formId?: string;
  draft: ParticipationInput;
  records: SavedRecord[];
  disabled: boolean;
  onChange: (draft: ParticipationInput) => void;
  onSubmit: (draft: ParticipationInput) => void;
}) {
  function payload(patch: Partial<ParticipationInput['payload']>) {
    onChange({ ...draft, payload: { ...draft.payload, ...patch } });
  }
  return (
    <form
      id={formId}
      aria-label="Customer interval editor"
      className="space-y-3 rounded border p-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(draft);
      }}
    >
      <label className="block">
        Participant (optional)
        <input
          className={field}
          value={draft.payload.participant ?? ''}
          onChange={(e) => payload({ participant: e.target.value || null })}
        />
      </label>
      {(['call', 'conference'] as const).map((type) => {
        const key = type === 'call' ? 'call_id' : 'conference_id';
        return (
          <label className="block" key={key}>
            {type === 'call' ? 'Customer call' : 'Customer conference'}
            <select
              className={field}
              value={draft.payload[key] ?? ''}
              onChange={(e) => payload({ [key]: e.target.value || null })}
            >
              <option value="">Unknown / unassigned</option>
              {records
                .filter((r) => r.record_type === type && !r.deleted)
                .map((r) => (
                  <option key={r.record_id} value={r.record_id}>
                    {r.payload.title}
                  </option>
                ))}
            </select>
          </label>
        );
      })}
      <p className="text-sm">
        Choose a call, a conference, or both. Identity, schedule and duration
        may be unknown.
      </p>
      <details>
        <summary>Retrospective timing and correction</summary>
        {draft.payload.resumes_participation_id && (
          <label className="block">
            <input
              type="checkbox"
              checked
              onChange={() => payload({ resumes_participation_id: null })}
            />
            Keep earlier interruption link (clear before correcting its
            association)
          </label>
        )}
        <label className="block">
          Customer state
          <select
            className={field}
            value={draft.payload.state ?? 'unknown'}
            onChange={(e) =>
              payload({
                state: e.target.value as ParticipationInput['payload']['state'],
              })
            }
          >
            {['unknown', 'connected', 'interrupted', 'left'].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <UtcDateTime
          label="Reported join"
          value={draft.time.occurred_at}
          disabled={disabled}
          onChange={(value) =>
            onChange({
              ...draft,
              time: {
                ...draft.time,
                occurred_at: value,
                precision: value ? 'approximate' : 'unknown',
                end_state: value
                  ? draft.time.ended_at
                    ? 'known'
                    : draft.payload.state === 'connected'
                      ? 'ongoing'
                      : 'unknown'
                  : 'unknown',
                ended_at: value ? draft.time.ended_at : null,
              },
            })
          }
        />
        <UtcDateTime
          label="Reported leave / interruption"
          value={draft.time.ended_at}
          disabled={disabled}
          onChange={(value) =>
            onChange({
              ...draft,
              time: {
                ...draft.time,
                ended_at: value,
                end_state: value
                  ? 'known'
                  : draft.time.occurred_at &&
                      draft.payload.state === 'connected'
                    ? 'ongoing'
                    : 'unknown',
              },
            })
          }
        />
        <label className="block">
          Customer note (optional)
          <textarea
            className={field}
            value={draft.payload.note}
            onChange={(e) => payload({ note: e.target.value })}
          />
        </label>
      </details>
      <button
        className="min-h-11 rounded border px-3"
        type="submit"
        hidden={!!formId}
        disabled={disabled}
      >
        Save Customer Interval
      </button>
    </form>
  );
}
