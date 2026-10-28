import type { ConferenceInput } from '@/types/operator';
import { UtcDateTime } from './UtcDateTime';
const field = 'min-h-11 w-full rounded border bg-background p-2';
export function ConferenceEditor({
  formId,
  draft,
  disabled,
  onChange,
  onSubmit,
  transportOptions = [],
}: {
  formId?: string;
  draft: ConferenceInput;
  disabled: boolean;
  onChange: (draft: ConferenceInput) => void;
  onSubmit: (draft: ConferenceInput) => void;
  transportOptions?: { id: string; name: string }[];
}) {
  function payload(patch: Partial<ConferenceInput['payload']>) {
    onChange({ ...draft, payload: { ...draft.payload, ...patch } });
  }
  const transports = new Map([
    ['Ka', 'Ka Commercial'],
    ['X', 'X-Band'],
    ['Starshield', 'Starshield'],
    ...transportOptions
      .filter((t) => !['Ka', 'X', 'Starshield'].includes(t.id))
      .map((t) => [t.id, t.name] as [string, string]),
  ]);
  for (const value of [
    draft.payload.intended_transport,
    draft.payload.configured_transport,
  ])
    if (value && !transports.has(value)) transports.set(value, value);
  return (
    <form
      id={formId}
      aria-label="Conference editor"
      className="space-y-3 rounded border p-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(draft);
      }}
    >
      <label className="block">
        Conference name (optional)
        <input
          className={field}
          value={draft.payload.title}
          onChange={(e) => payload({ title: e.target.value })}
        />
      </label>
      {(['intended_transport', 'configured_transport'] as const).map((key) => (
        <label className="block" key={key}>
          {key === 'intended_transport'
            ? 'Intended Transport'
            : 'Operator-reported configuration'}
          <select
            className={field}
            value={draft.payload[key] ?? ''}
            onChange={(e) =>
              payload({
                [key]: e.target.value || null,
                ...(key === 'configured_transport'
                  ? { verified_at: null }
                  : {}),
              })
            }
          >
            <option value="">Unknown</option>
            {[...transports].map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
      ))}
      <details>
        <summary>Conference details and retrospective correction</summary>
        <label className="block">
          Conference state
          <select
            className={field}
            value={draft.payload.status ?? 'unknown'}
            onChange={(e) =>
              payload({
                status: e.target.value as ConferenceInput['payload']['status'],
                verified_at: null,
              })
            }
          >
            {[
              'unknown',
              'preparing',
              'established',
              'interrupted',
              'closed',
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="block">
          Coordinator (optional)
          <input
            className={field}
            value={draft.payload.coordinator ?? ''}
            onChange={(e) => payload({ coordinator: e.target.value || null })}
          />
        </label>
        <UtcDateTime
          label="Two-way check"
          value={draft.payload.verified_at ?? null}
          disabled={disabled}
          onChange={(value) => payload({ verified_at: value })}
        />
        <UtcDateTime
          label="Configuration report"
          value={draft.payload.configuration_reported_at ?? null}
          disabled={disabled}
          onChange={(value) => payload({ configuration_reported_at: value })}
        />
        <UtcDateTime
          label="Action occurrence"
          value={draft.time.occurred_at}
          disabled={disabled}
          onChange={(value) =>
            onChange({
              ...draft,
              time: {
                ...draft.time,
                occurred_at: value,
                ended_at: null,
                precision: value ? 'approximate' : 'unknown',
                end_state: value ? 'instant' : 'unknown',
              },
            })
          }
        />
        <label className="block">
          Conference note (optional)
          <textarea
            className={field}
            value={draft.payload.note}
            onChange={(e) => payload({ note: e.target.value })}
          />
        </label>
      </details>
      <button
        className="min-h-11 rounded border px-3"
        disabled={disabled}
        type="submit"
        hidden={!!formId}
      >
        Save Conference
      </button>
    </form>
  );
}
