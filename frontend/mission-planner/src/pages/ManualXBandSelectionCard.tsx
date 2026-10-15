import { useId } from 'react';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { useSatellites } from '@/hooks/api/useSatellites';
import { useUpdateManualXSelection } from '@/hooks/api/useUpdateManualXSelection';
import { Button } from '@/components/ui/button';
import { ConfigurationSection } from './ConfigurationSection';

export function ManualXBandSelectionCard() {
  const id = useId();
  const selection = useActiveXLink();
  const catalog = useSatellites(true);
  const save = useUpdateManualXSelection();
  const data = selection.data;
  const satellites = (catalog.data ?? []).filter(
    (satellite) => satellite.transport === 'X'
  );
  const missionControlled = data?.selection_source === 'mission';
  const unavailable = selection.isError || catalog.isError;
  const ready = Boolean(data?.selection_source && catalog.data && !unavailable);
  const disabled = !ready || missionControlled || save.isPending;
  const selectedId = data?.satellite_id ?? '';
  return (
    <ConfigurationSection
      title="Planned X-band satellite"
      description="Choose the application's planned satellite when no mission is active. This selection does not command radio hardware or indicate measured connectivity."
    >
      <label htmlFor={id} className="mb-2 block text-sm font-medium">
        Planned X-band satellite
      </label>
      <select
        id={id}
        aria-describedby={`${id}-help`}
        className="min-h-11 w-full rounded-lg border border-input bg-background px-3 text-sm disabled:opacity-50 sm:max-w-sm"
        value={selectedId}
        disabled={disabled || satellites.length === 0}
        onChange={(event) => save.mutate(event.target.value || null)}
      >
        <option value="">None</option>
        {selectedId &&
          !satellites.some(
            (satellite) => satellite.satellite_id === selectedId
          ) && (
            <option value={selectedId}>{selectedId} (not configured)</option>
          )}
        {satellites.map((satellite) => (
          <option key={satellite.satellite_id} value={satellite.satellite_id}>
            {satellite.satellite_id}
          </option>
        ))}
      </select>
      <p id={`${id}-help`} className="mt-2 text-sm text-muted-foreground">
        {missionControlled
          ? 'An active mission controls satellite selection. Your previous valid manual selection returns when the mission is deactivated.'
          : 'Saved selections survive reloads and restarts. Open Overview displays update automatically.'}
      </p>
      {selection.isError && <p role="alert">Satellite selection unavailable</p>}
      {catalog.isError && (
        <p role="alert">Satellite configuration unavailable</p>
      )}
      {data?.manual_selection_unavailable && (
        <p role="alert">
          Saved manual selection unavailable. Mission selection remains active.
        </p>
      )}
      {!data && !selection.isError && (
        <p role="status">Loading satellite selection…</p>
      )}
      {!catalog.data && !catalog.isError && (
        <p role="status">Loading satellite configuration…</p>
      )}
      {ready && satellites.length === 0 && (
        <p role="status">
          No X-band satellites configured. Add one in Satellites.
        </p>
      )}
      {data?.manual_selection_invalid && (
        <div className="mt-3 space-y-2">
          <p role="alert">
            The saved satellite is no longer configured for X-band. Choose
            another satellite or clear the saved selection.
          </p>
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => save.mutate(null)}
          >
            Clear saved selection
          </Button>
        </div>
      )}
      {save.isPending && <p role="status">Saving satellite selection…</p>}
      {save.isSuccess && <p role="status">Satellite selection saved</p>}
      {save.isError && (
        <p role="alert">
          Unable to confirm satellite selection. Check the current selection or
          try again; an active mission may have taken control.
        </p>
      )}
    </ConfigurationSection>
  );
}
