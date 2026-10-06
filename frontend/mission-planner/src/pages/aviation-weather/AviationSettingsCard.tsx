import { Switch } from '@/components/ui/switch';
import {
  useAviationSettings,
  useSaveAviationSettings,
} from '@/hooks/api/useAviationSettings';
import { ConfigurationSection } from '../ConfigurationSection';
import type { AviationLayer } from '@/services/aviation-weather';
const options: { group: string; layer: AviationLayer; label: string }[] = [
  {
    group: 'Terminal weather',
    layer: 'metar',
    label: 'METAR / SPECI observations',
  },
  { group: 'Terminal weather', layer: 'taf', label: 'TAF terminal forecasts' },
  {
    group: 'Hazards',
    layer: 'sigmet',
    label: 'International SIGMET advisories',
  },
];
export function AviationSettingsCard() {
  const query = useAviationSettings(),
    save = useSaveAviationSettings();
  return (
    <ConfigurationSection
      title="Aviation weather"
      description="Optional station reports, terminal forecasts and advisories on all Overview displays. Missing coverage means unknown weather."
    >
      {['Terminal weather', 'Hazards'].map((group) => (
        <fieldset key={group} className="my-3 space-y-2">
          <legend className="mb-2 text-sm text-muted-foreground">
            {group}
          </legend>
          {options
            .filter((o) => o.group === group)
            .map((o) => (
              <label
                key={o.layer}
                className="flex min-h-11 items-center justify-between gap-4 text-sm font-medium"
              >
                {o.label}
                <Switch
                  aria-label={o.label}
                  checked={query.data?.[o.layer] ?? false}
                  disabled={!query.data || query.isError || save.isPending}
                  onChange={(e) => save.mutate({ [o.layer]: e.target.checked })}
                />
              </label>
            ))}
        </fieldset>
      ))}
      <div aria-live="polite" className="text-sm">
        {query.isLoading && (
          <p role="status">Loading aviation weather settings…</p>
        )}
        {query.isError && (
          <p role="alert">Aviation weather settings unavailable</p>
        )}
        {save.isPending && (
          <p role="status">Saving aviation weather settings…</p>
        )}
        {save.isSuccess && <p role="status">Aviation weather settings saved</p>}
        {save.isError && (
          <p role="alert">Aviation weather settings could not be saved</p>
        )}
      </div>
    </ConfigurationSection>
  );
}
