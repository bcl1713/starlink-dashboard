import { useId, useState } from 'react';
// prettier-ignore
import { OVERVIEW_POI_FILTER_OPTIONS, type OverviewPOIFilter } from '../../types/monitoring';
// prettier-ignore
import { OVERVIEW_REFRESH_OPTIONS, validateOverviewClockInput, type OverviewClockPreference, type OverviewPreferences, type OverviewRefreshCadence } from './preferences';

export interface OverviewControlsProps {
  preferences: OverviewPreferences;
  manualRefreshPending: boolean;
  onRefreshCadenceChange(value: OverviewRefreshCadence): void;
  onManualRefresh(): void | Promise<void>;
  onRadarEnabledChange(enabled: boolean): void;
  onPOIFilterChange(value: OverviewPOIFilter): void;
  onControlsExpandedChange(expanded: boolean): void;
  onClockSettingsExpandedChange(expanded: boolean): void;
  onAddClock(input: { timeZone: string; label: string }): void;
  onRelabelClock(id: string, label: string): void;
  onMoveClock(id: string, direction: 'up' | 'down'): void;
  onRemoveClock(id: string): void;
}

function cadenceFromValue(value: string): OverviewRefreshCadence {
  return value === 'paused'
    ? 'paused'
    : (Number(value) as OverviewRefreshCadence);
}

function isPOIFilter(value: string): value is OverviewPOIFilter {
  return OVERVIEW_POI_FILTER_OPTIONS.some((option) => option.value === value);
}

// prettier-ignore
type ClockRowProps = { clock: OverviewClockPreference; index: number; total: number; onRelabelClock(id: string, label: string): void; onMoveClock(id: string, direction: 'up' | 'down'): void; onRemoveClock(id: string): void };

function ClockRow({
  clock,
  index,
  total,
  onRelabelClock,
  onMoveClock,
  onRemoveClock,
}: ClockRowProps) {
  const relabelId = useId();
  const [draft, setDraft] = useState(clock.label);
  const isUtc = clock.id === 'utc';
  const trimmed = draft.trim();
  const canRelabel = trimmed.length >= 1 && trimmed.length <= 64;

  return (
    <div className="grid gap-2 rounded-md border p-3 sm:grid-cols-[1fr_auto]">
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor={relabelId}>
          Relabel {clock.label}
        </label>
        {isUtc ? (
          <p className="text-sm text-muted-foreground">
            UTC is always shown first.
          </p>
        ) : (
          <input
            id={relabelId}
            aria-label={`Relabel ${clock.label}`}
            className="min-h-11 w-full rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => {
              if (canRelabel && trimmed !== clock.label) {
                onRelabelClock(clock.id, trimmed);
              }
            }}
          />
        )}
      </div>
      {!isUtc ? (
        <div className="flex items-end gap-2">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            aria-label={`Move ${clock.label} up`}
            disabled={index <= 1}
            onClick={() => onMoveClock(clock.id, 'up')}
          >
            Up
          </button>
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            aria-label={`Move ${clock.label} down`}
            disabled={index >= total - 1}
            onClick={() => onMoveClock(clock.id, 'down')}
          >
            Down
          </button>
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Remove ${clock.label}`}
            onClick={() => onRemoveClock(clock.id)}
          >
            Remove
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function OverviewControls({
  preferences,
  manualRefreshPending,
  onRefreshCadenceChange,
  onManualRefresh,
  onRadarEnabledChange,
  onPOIFilterChange,
  onControlsExpandedChange,
  onClockSettingsExpandedChange,
  onAddClock,
  onRelabelClock,
  onMoveClock,
  onRemoveClock,
}: OverviewControlsProps) {
  const controlsId = useId();
  const clockSettingsId = useId();
  const zoneId = useId();
  const labelId = useId();
  const [timeZoneDraft, setTimeZoneDraft] = useState('');
  const [labelDraft, setLabelDraft] = useState('');
  const [validation, setValidation] = useState('');
  const addDisabled = preferences.clocks.length >= 8;

  const addClock = () => {
    if (addDisabled) return setValidation('Clock limit reached.');
    const clock = validateOverviewClockInput({
      timeZone: timeZoneDraft,
      label: labelDraft,
    });
    if (!clock) return setValidation('Enter a valid label and time zone.');
    if (preferences.clocks.some((item) => item.id === clock.id)) {
      setValidation('Clock already exists.');
      return;
    }
    setValidation('');
    onAddClock({ timeZone: clock.timeZone, label: clock.label });
  };
  const manualRefresh = () => {
    try {
      void Promise.resolve(onManualRefresh()).catch(() => {});
    } catch {
      return undefined;
    }
  };

  return (
    <section className="space-y-3">
      <button
        type="button"
        className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={preferences.disclosures.controlsExpanded}
        aria-controls={controlsId}
        onClick={() =>
          onControlsExpandedChange(!preferences.disclosures.controlsExpanded)
        }
      >
        Overview controls
      </button>
      <div id={controlsId} hidden={!preferences.disclosures.controlsExpanded}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-sm font-medium">
            Refresh cadence
            <select
              aria-label="Refresh cadence"
              className="min-h-11 w-full rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={String(preferences.refreshCadence)}
              onChange={(event) =>
                onRefreshCadenceChange(cadenceFromValue(event.target.value))
              }
            >
              {OVERVIEW_REFRESH_OPTIONS.map((option) => (
                <option key={String(option.value)} value={String(option.value)}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm font-medium">
            POI category
            <select
              aria-label="POI category"
              className="min-h-11 w-full rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={preferences.poiFilter}
              onChange={(event) => {
                if (isPOIFilter(event.target.value)) {
                  onPOIFilterChange(event.target.value);
                }
              }}
            >
              {OVERVIEW_POI_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              aria-label="Weather radar"
              className="min-h-11 min-w-11 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              checked={preferences.radarEnabled}
              onChange={(event) => onRadarEnabledChange(event.target.checked)}
            />
            <span>{preferences.radarEnabled ? 'Radar on' : 'Radar off'}</span>
          </label>
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            disabled={manualRefreshPending}
            onClick={manualRefresh}
          >
            Refresh overview
          </button>
        </div>
        <div className="mt-3 space-y-3">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-expanded={preferences.disclosures.clockSettingsExpanded}
            aria-controls={clockSettingsId}
            onClick={() =>
              onClockSettingsExpandedChange(
                !preferences.disclosures.clockSettingsExpanded
              )
            }
          >
            Clock settings
          </button>
          <div
            id={clockSettingsId}
            hidden={!preferences.disclosures.clockSettingsExpanded}
            className="space-y-3"
          >
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <label className="space-y-1 text-sm font-medium" htmlFor={zoneId}>
                Clock time zone
                <input
                  id={zoneId}
                  className="min-h-11 w-full rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={timeZoneDraft}
                  onChange={(event) => setTimeZoneDraft(event.target.value)}
                />
              </label>
              <label
                className="space-y-1 text-sm font-medium"
                htmlFor={labelId}
              >
                Clock label
                <input
                  id={labelId}
                  className="min-h-11 w-full rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={labelDraft}
                  onChange={(event) => setLabelDraft(event.target.value)}
                />
              </label>
              <button
                type="button"
                className="min-h-11 min-w-11 self-end rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                disabled={addDisabled}
                onClick={addClock}
              >
                Add clock
              </button>
            </div>
            {validation ? (
              <p className="text-sm text-destructive" role="status">
                {validation}
              </p>
            ) : null}
            <div className="space-y-2">
              {preferences.clocks.map((clock, index) => (
                <ClockRow
                  key={clock.id}
                  clock={clock}
                  index={index}
                  total={preferences.clocks.length}
                  onRelabelClock={onRelabelClock}
                  onMoveClock={onMoveClock}
                  onRemoveClock={onRemoveClock}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
