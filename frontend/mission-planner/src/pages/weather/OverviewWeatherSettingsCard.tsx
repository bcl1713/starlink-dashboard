import { Switch } from '@/components/ui/switch';
import { useOverviewWeatherSettings } from '@/hooks/api/useOverviewWeatherSettings';
import { useUpdateOverviewWeatherSettings } from '@/hooks/api/useUpdateOverviewWeatherSettings';
import { ConfigurationSection } from '../ConfigurationSection';

export function OverviewWeatherSettingsCard() {
  const query = useOverviewWeatherSettings();
  const save = useUpdateOverviewWeatherSettings();
  return (
    <ConfigurationSection
      title="Weather"
      description="Shared across this installation. Show automatically updated precipitation on all Overview displays."
    >
      <label className="flex min-h-11 items-center justify-between gap-4 text-sm font-medium">
        Precipitation radar
        <Switch
          aria-label="Precipitation radar"
          checked={query.data?.settings.enabled ?? false}
          disabled={!query.data || query.isError || save.isPending}
          onChange={(event) => save.mutate({ enabled: event.target.checked })}
        />
      </label>
      <div className="text-sm" aria-live="polite">
        {query.isLoading && <p role="status">Loading weather settings…</p>}
        {query.isError && <p role="alert">Weather settings unavailable</p>}
        {save.isPending && <p role="status">Saving weather settings…</p>}
        {save.isSuccess && <p role="status">Weather settings saved</p>}
        {save.isError && (
          <p role="alert" className="text-destructive">
            Weather settings could not be saved
          </p>
        )}
      </div>
    </ConfigurationSection>
  );
}
