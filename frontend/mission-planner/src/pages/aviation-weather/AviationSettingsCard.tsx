import { Switch } from '@/components/ui/switch';
import {
  useAviationSettings,
  useSaveAviationSettings,
} from '@/hooks/api/useAviationSettings';
import { ConfigurationSection } from '../ConfigurationSection';
import type { AviationLayer, GfsSelection } from '@/services/aviation-weather';
const levels = [85000, 50000, 30000, 25000, 20000] as const;
const flightLevels = [50, 100, 180, 240, 300, 340, 390, 450] as const;
const horizons = [0, 3, 6, 9, 12, 18, 24, 36, 48] as const;
const options: {
  group: string;
  layer: AviationLayer | 'winds' | 'temperature';
  label: string;
}[] = [
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
  { group: 'Flight-level atmosphere', layer: 'winds', label: 'GFS winds' },
  {
    group: 'Flight-level atmosphere',
    layer: 'temperature',
    label: 'GFS air temperature',
  },
];
export function AviationSettingsCard() {
  const query = useAviationSettings(),
    save = useSaveAviationSettings();
  const selected = query.data?.gfs_selection;
  const selection: GfsSelection =
    selected && 'vertical' in selected
      ? selected
      : {
          vertical: { kind: 'pressure', pressure_pa: 50000 },
          horizon_hours: 0,
        };
  const disabled = !query.data || query.isError || save.isPending;
  return (
    <ConfigurationSection
      title="Aviation weather"
      description="Optional station reports, terminal forecasts and advisories on all Overview displays. Missing coverage means unknown weather."
    >
      {['Terminal weather', 'Hazards', 'Flight-level atmosphere'].map(
        (group) => (
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
                    onChange={(e) =>
                      save.mutate({ [o.layer]: e.target.checked })
                    }
                  />
                </label>
              ))}
          </fieldset>
        )
      )}
      <fieldset disabled={disabled} className="my-3 space-y-3">
        <legend className="text-sm text-muted-foreground">
          Shared atmosphere selection
        </legend>
        <label className="flex items-center justify-between gap-4 text-sm">
          Atmosphere level
          <select
            aria-label="Atmosphere level"
            value={
              selection.vertical.kind === 'pressure'
                ? `pressure:${selection.vertical.pressure_pa}`
                : `fl:${selection.vertical.flight_level}`
            }
            onChange={(event) => {
              const [kind, value] = event.target.value.split(':');
              const vertical =
                kind === 'pressure'
                  ? {
                      kind: 'pressure' as const,
                      pressure_pa: Number(value) as (typeof levels)[number],
                    }
                  : {
                      kind: 'flight-level' as const,
                      flight_level: Number(
                        value
                      ) as (typeof flightLevels)[number],
                    };
              save.mutate({ gfs_selection: { ...selection, vertical } });
            }}
          >
            <option disabled>Surface · unsupported</option>
            <optgroup label="Native pressure">
              {levels.map((p) => (
                <option key={p} value={`pressure:${p}`}>
                  {p / 100} hPa
                </option>
              ))}
            </optgroup>
            <optgroup label="ISA / log-pressure interpolation">
              {flightLevels.map((fl) => (
                <option key={fl} value={`fl:${fl}`}>
                  FL{String(fl).padStart(3, '0')}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        <label className="flex items-center justify-between gap-4 text-sm">
          Forecast horizon
          <select
            aria-label="Forecast horizon"
            value={selection.horizon_hours}
            onChange={(event) =>
              save.mutate({
                gfs_selection: {
                  ...selection,
                  horizon_hours: Number(
                    event.target.value
                  ) as (typeof horizons)[number],
                },
              })
            }
          >
            {horizons.map((h) => (
              <option key={h} value={h}>
                UTC now + {h} h
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-muted-foreground">
          One level and horizon for both model layers on all Overview displays.
          Flight levels use the standard atmosphere and interpolate
          U/V/temperature in log pressure; masked terrain is unknown.
        </p>
      </fieldset>
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
