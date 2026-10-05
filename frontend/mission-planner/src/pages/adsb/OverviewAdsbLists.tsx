import { Button } from '@/components/ui/button';
import { useId, useState } from 'react';
import type {
  AdsbContact,
  AdsbSettings,
  AdsbSettingsUpdate,
} from '@/services/overview-adsb';
interface Props {
  settings: AdsbSettings;
  contacts?: readonly AdsbContact[];
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
function savedAircraftLabel(
  hex: string,
  contacts: readonly AdsbContact[]
): string {
  const contact = contacts.find((item) => item.hex === hex);
  const identity = contact
    ? [contact.callsign, contact.registration, contact.aircraft_type]
        .map((value) => value?.trim())
        .filter(Boolean)
    : [];
  return [hex, ...identity].join(' · ');
}
function ListEditor({
  settings,
  contacts = [],
  disabled,
  onSave,
  config,
}: {
  settings: AdsbSettings;
  contacts?: readonly AdsbContact[];
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
    <section aria-label={config.region} className="min-w-0 space-y-3">
      <h3 className="text-sm font-semibold">{config.region}</h3>
      {config.field !== 'callsign_substrings' && (
        <ul className="space-y-1">
          {settings[config.field].map((hex) => (
            <li
              key={hex}
              className="flex flex-wrap items-center justify-between gap-2"
            >
              <span className="min-w-0 break-words font-mono text-xs">
                {savedAircraftLabel(hex, contacts)}
              </span>
              {settings.include_hexes.includes(hex) &&
                settings.exclude_hexes.includes(hex) && (
                  <span className="text-sm">
                    Also{' '}
                    {config.field === 'include_hexes' ? 'excluded' : 'included'}
                    ; exclusion wins.
                  </span>
                )}
              <Button
                variant="ghost"
                size="sm"
                type="button"
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
              </Button>
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
          rows={2}
          className="w-full rounded-md border bg-background p-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50"
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
        <Button variant="outline" size="sm" type="submit" disabled={disabled}>
          {config.save}
        </Button>
      </form>
    </section>
  );
}
export function OverviewAdsbLists(props: Props) {
  return (
    <div className="space-y-4 border-t pt-5">
      <p className="text-xs text-muted-foreground">
        Exclusion always wins, including aircraft saved in both lists. Saved
        entries remain when aircraft are unavailable.
      </p>
      <div className="grid gap-6 md:grid-cols-3">
        {fields.map((config) => (
          <ListEditor {...props} key={config.field} config={config} />
        ))}
      </div>
    </div>
  );
}
