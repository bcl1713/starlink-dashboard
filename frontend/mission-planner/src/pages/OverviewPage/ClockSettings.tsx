import { useId, useState } from 'react';
import type { OverviewClockPreference } from './preferences';
import { validateOverviewClockInput } from './preferences';
import { ClockRow } from './ClockRow';

export interface ClockSettingsProps {
  readonly clocks: readonly OverviewClockPreference[];
  readonly expanded: boolean;
  readonly onExpandedChange: (expanded: boolean) => void;
  readonly onAddClock: (input: { timeZone: string; label: string }) => void;
  readonly onRelabelClock: (id: string, label: string) => void;
  readonly onMoveClock: (id: string, direction: 'up' | 'down') => void;
  readonly onRemoveClock: (id: string) => void;
}

export function ClockSettings({
  clocks,
  expanded,
  onExpandedChange,
  onAddClock,
  onRelabelClock,
  onMoveClock,
  onRemoveClock,
}: ClockSettingsProps) {
  const clockSettingsId = useId();
  const zoneId = useId();
  const labelId = useId();
  const validationId = useId();
  const [timeZoneDraft, setTimeZoneDraft] = useState('');
  const [labelDraft, setLabelDraft] = useState('');
  const [validation, setValidation] = useState('');
  const addDisabled = clocks.length >= 8;

  const addClock = () => {
    if (addDisabled) return setValidation('Clock limit reached.');
    const clock = validateOverviewClockInput({
      timeZone: timeZoneDraft,
      label: labelDraft,
    });
    if (!clock) return setValidation('Enter a valid label and time zone.');
    if (clocks.some((item) => item.id === clock.id)) {
      setValidation('Clock already exists.');
      return;
    }
    setValidation('');
    onAddClock({ timeZone: clock.timeZone, label: clock.label });
  };

  return (
    <div className="mt-3 min-w-0 space-y-3">
      <button
        type="button"
        className="min-h-11 min-w-11 rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={expanded}
        aria-controls={clockSettingsId}
        onClick={() => onExpandedChange(!expanded)}
      >
        Clock settings
      </button>
      <div id={clockSettingsId} hidden={!expanded} className="space-y-3">
        <div className="grid min-w-0 gap-3 md:grid-cols-[1fr_1fr_auto]">
          <label className="space-y-1 text-sm font-medium" htmlFor={zoneId}>
            Clock time zone
            <input
              id={zoneId}
              aria-describedby={validationId}
              className="min-h-11 w-full min-w-0 rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={timeZoneDraft}
              onChange={(event) => setTimeZoneDraft(event.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm font-medium" htmlFor={labelId}>
            Clock label
            <input
              id={labelId}
              aria-describedby={validationId}
              className="min-h-11 w-full min-w-0 rounded-md border px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={labelDraft}
              onChange={(event) => setLabelDraft(event.target.value)}
            />
          </label>
          <button
            type="button"
            aria-describedby={validationId}
            className="min-h-11 min-w-11 self-end rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            disabled={addDisabled}
            onClick={addClock}
          >
            Add clock
          </button>
        </div>
        <p id={validationId} className="text-sm text-destructive">
          {validation}
        </p>
        <div className="space-y-2">
          {clocks.map((clock, index) => (
            <ClockRow
              key={clock.id}
              clock={clock}
              index={index}
              total={clocks.length}
              onRelabelClock={onRelabelClock}
              onMoveClock={onMoveClock}
              onRemoveClock={onRemoveClock}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
