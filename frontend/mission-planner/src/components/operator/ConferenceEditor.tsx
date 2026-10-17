import type { ConferenceInput, Transport } from '@/types/operator';
const field = 'min-h-11 w-full rounded border bg-background p-2';
export function ConferenceEditor({
  draft,
  disabled,
  onChange,
  onSubmit,
}: {
  draft: ConferenceInput;
  disabled: boolean;
  onChange: (draft: ConferenceInput) => void;
  onSubmit: (draft: ConferenceInput) => void;
}) {
  function payload(patch: Partial<ConferenceInput['payload']>) {
    onChange({ ...draft, payload: { ...draft.payload, ...patch } });
  }
  return (
    <form
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
        {(['intended_transport', 'configured_transport'] as const).map(
          (key) => (
            <label className="block" key={key}>
              {key === 'intended_transport'
                ? 'Intended transport'
                : 'Operator-reported configuration'}
              <select
                className={field}
                value={draft.payload[key] ?? ''}
                onChange={(e) =>
                  payload({
                    [key]: (e.target.value || null) as Transport | null,
                    ...(key === 'configured_transport'
                      ? { verified_at: null }
                      : {}),
                  })
                }
              >
                <option value="">Unknown</option>
                {['Starshield', 'Ka', 'X'].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
          )
        )}
        {(['verified_at', 'configuration_reported_at'] as const).map((key) => (
          <label className="block" key={key}>
            {key === 'verified_at'
              ? 'Operator verification UTC'
              : 'Configuration report UTC'}
            <input
              className={field}
              placeholder="YYYY-MM-DDTHH:MM:SSZ or unknown"
              value={draft.payload[key] ?? ''}
              onChange={(e) => payload({ [key]: e.target.value || null })}
            />
          </label>
        ))}
        <label className="block">
          Action occurrence UTC (optional)
          <input
            className={field}
            value={draft.time.occurred_at ?? ''}
            onChange={(e) =>
              onChange({
                ...draft,
                time: {
                  ...draft.time,
                  occurred_at: e.target.value || null,
                  ended_at: null,
                  precision: e.target.value ? 'approximate' : 'unknown',
                  end_state: e.target.value ? 'instant' : 'unknown',
                },
              })
            }
          />
        </label>
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
      >
        Save conference
      </button>
    </form>
  );
}
