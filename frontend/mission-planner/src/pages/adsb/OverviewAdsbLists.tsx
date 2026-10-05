import { useId, useState } from 'react';
import type {
  AdsbSettings,
  AdsbSettingsUpdate,
} from '@/services/overview-adsb';
interface Props {
  settings: AdsbSettings;
  disabled: boolean;
  onSave: (changes: AdsbSettingsUpdate) => void;
}
const fields = [
  {
    field: 'include_hexes',
    region: 'Saved included aircraft',
    label: 'Included ICAO hexes',
    save: 'Save included aircraft',
    kind: 'included',
  },
  {
    field: 'exclude_hexes',
    region: 'Saved excluded aircraft',
    label: 'Excluded ICAO hexes',
    save: 'Save excluded aircraft',
    kind: 'excluded',
  },
  {
    field: 'callsign_substrings',
    region: 'Background military callsign filter',
    label: 'Background military callsign substrings',
    save: 'Save callsign filter',
    kind: 'callsign',
  },
] as const;
function ListEditor({
  settings,
  disabled,
  onSave,
  config,
}: {
  settings: AdsbSettings;
  disabled: boolean;
  onSave: Props['onSave'];
  config: (typeof fields)[number];
}) {
  const current = settings[config.field].join('\n');
  const [draft, setDraft] = useState(() => ({
    confirmed: current,
    text: current,
  }));
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  if (draft.confirmed !== current)
    setDraft({
      confirmed: current,
      text:
        draft.text === draft.confirmed ||
        [
          ...new Set(
            draft.text
              .split(/[,\n]/)
              .map((s) => s.trim().toUpperCase())
              .filter(Boolean)
          ),
        ].join('\n') === current
          ? current
          : draft.text,
    });
  const save = () => {
    const entries = [
      ...new Set(
        draft.text
          .split(/[,\n]/)
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean)
      ),
    ];
    if (
      config.field !== 'callsign_substrings' &&
      entries.some((s) => !/^[0-9A-F]{6}$/.test(s))
    ) {
      setError('Each ICAO hex must contain exactly six hexadecimal digits.');
      return;
    }
    setError(null);
    if (entries.join('\n') !== current) onSave({ [config.field]: entries });
    else setDraft({ confirmed: current, text: current });
  };
  return (
    <section aria-label={config.region} className="mt-4 rounded border p-3">
      <h3 className="font-semibold">{config.region}</h3>
      {config.field !== 'callsign_substrings' && (
        <ul className="space-y-1">
          {settings[config.field].map((hex) => (
            <li
              key={hex}
              className="flex flex-wrap items-center justify-between gap-2"
            >
              <span className="font-mono">{hex}</span>
              {settings.include_hexes.includes(hex) &&
                settings.exclude_hexes.includes(hex) && (
                  <span className="text-sm">
                    Also{' '}
                    {config.field === 'include_hexes' ? 'excluded' : 'included'}
                    ; exclusion wins.
                  </span>
                )}
              <button
                type="button"
                className="min-h-11 rounded border px-2 disabled:opacity-50"
                disabled={disabled}
                aria-label={`Remove ${config.kind} ${hex}`}
                onClick={() =>
                  onSave({
                    [config.field]: settings[config.field].filter(
                      (h) => h !== hex
                    ),
                  })
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
        className="mt-2 space-y-2"
      >
        <label htmlFor={id} className="block text-sm">
          {config.label}
        </label>
        <textarea
          id={id}
          value={draft.text}
          disabled={disabled}
          rows={3}
          className="w-full rounded border bg-background p-2 disabled:opacity-50"
          onChange={(e) => {
            setDraft({ ...draft, text: e.target.value });
            setError(null);
          }}
          aria-describedby={`${id}-help`}
          aria-invalid={Boolean(error)}
        />
        <p id={`${id}-help`} className="text-sm text-muted-foreground">
          {config.field === 'callsign_substrings'
            ? 'Matches any substring (OR), ignoring case. Empty accepts all military background traffic.'
            : 'Separate exact six-digit hexes with commas or new lines; leading zeroes are preserved.'}
        </p>
        {error && <p role="alert">{error}</p>}
        <button
          type="submit"
          disabled={disabled}
          className="min-h-11 rounded border px-3 disabled:opacity-50"
        >
          {config.save}
        </button>
      </form>
    </section>
  );
}
export function OverviewAdsbLists(props: Props) {
  return (
    <div>
      <p className="mt-3 text-sm">
        Exclusion always wins, including aircraft saved in both lists. Saved
        entries remain when aircraft are unavailable.
      </p>
      {fields.map((config) => (
        <ListEditor {...props} key={config.field} config={config} />
      ))}
    </div>
  );
}
