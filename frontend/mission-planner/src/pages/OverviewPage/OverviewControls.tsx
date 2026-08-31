import { useId, useLayoutEffect, useRef } from 'react';
import {
  OVERVIEW_POI_FILTER_OPTIONS,
  type OverviewPOIFilter,
} from '../../types/monitoring';
import {
  OVERVIEW_REFRESH_OPTIONS,
  type OverviewPreferences,
  type OverviewRefreshCadence,
} from './preferences';
import { ClockSettings } from './ClockSettings';

export interface OverviewControlsProps {
  readonly preferences: OverviewPreferences;
  readonly manualRefreshPending: boolean;
  readonly onRefreshCadenceChange: (value: OverviewRefreshCadence) => void;
  readonly onManualRefresh: () => void | Promise<void>;
  readonly onPOIFilterChange: (value: OverviewPOIFilter) => void;
  readonly onControlsExpandedChange: (expanded: boolean) => void;
  readonly onClockSettingsExpandedChange: (expanded: boolean) => void;
  readonly onAddClock: (input: { timeZone: string; label: string }) => void;
  readonly onRelabelClock: (id: string, label: string) => void;
  readonly onMoveClock: (id: string, direction: 'up' | 'down') => void;
  readonly onRemoveClock: (id: string) => void;
}

function cadenceFromValue(value: string): OverviewRefreshCadence {
  return value === 'paused'
    ? 'paused'
    : (Number(value) as OverviewRefreshCadence);
}

function isPOIFilter(value: string): value is OverviewPOIFilter {
  return OVERVIEW_POI_FILTER_OPTIONS.some((option) => option.value === value);
}

export function OverviewControls({
  preferences,
  manualRefreshPending,
  onRefreshCadenceChange,
  onManualRefresh,
  onPOIFilterChange,
  onControlsExpandedChange,
  onClockSettingsExpandedChange,
  onAddClock,
  onRelabelClock,
  onMoveClock,
  onRemoveClock,
}: OverviewControlsProps) {
  const controlsId = useId();
  const manualButtonRef = useRef<HTMLButtonElement>(null);
  const retainManualFocusRef = useRef(false);

  useLayoutEffect(() => {
    if (manualRefreshPending && retainManualFocusRef.current) {
      manualButtonRef.current?.focus();
    }
    if (!manualRefreshPending) retainManualFocusRef.current = false;
  }, [manualRefreshPending]);

  const manualRefresh = () => {
    if (manualRefreshPending) return;
    retainManualFocusRef.current = true;
    try {
      void Promise.resolve(onManualRefresh()).catch(() => {});
    } catch {
      return undefined;
    }
  };

  return (
    <section className="min-w-0 space-y-3">
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
      <div
        id={controlsId}
        hidden={!preferences.disclosures.controlsExpanded}
        className="min-w-0"
      >
        <div className="grid min-w-0 gap-3 md:grid-cols-2">
          <label className="space-y-1 text-sm font-medium">
            Refresh cadence
            <select
              aria-label="Refresh cadence"
              className="min-h-11 w-full min-w-0 rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
              className="min-h-11 w-full min-w-0 rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
          <button
            ref={manualButtonRef}
            type="button"
            className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-disabled:opacity-50"
            aria-disabled={manualRefreshPending}
            onClick={manualRefresh}
          >
            Refresh overview
          </button>
        </div>
        <ClockSettings
          clocks={preferences.clocks}
          expanded={preferences.disclosures.clockSettingsExpanded}
          onExpandedChange={onClockSettingsExpandedChange}
          onAddClock={onAddClock}
          onRelabelClock={onRelabelClock}
          onMoveClock={onMoveClock}
          onRemoveClock={onRemoveClock}
        />
      </div>
    </section>
  );
}
