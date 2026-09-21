import type {
  OverviewClockSetting,
  OverviewClockSettings,
} from '@/services/overview-clock-settings';
import { useState } from 'react';

export interface OperationalClockSettingsFormProps {
  clocks: readonly OverviewClockSetting[];
  isSaving: boolean;
  onSave: (settings: OverviewClockSettings) => void;
}

export function OperationalClockSettingsForm({
  clocks,
  isSaving,
  onSave,
}: OperationalClockSettingsFormProps) {
  const [editableClocks, setEditableClocks] = useState(() =>
    clocks.map((clock) => ({ ...clock }))
  );

  const updateClock = (
    index: number,
    field: 'label' | 'time_zone',
    value: string
  ) => {
    setEditableClocks((currentClocks) =>
      currentClocks.map((clock, clockIndex) =>
        clockIndex === index ? { ...clock, [field]: value } : clock
      )
    );
  };
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSave({ clocks: editableClocks });
      }}
    >
      {editableClocks.map((clock, index) => {
        const clockNum = index + 1;
        return (
          <fieldset key={clockNum}>
            <legend>Clock {clockNum}</legend>
            <label htmlFor={`clock-${clockNum}-label`}>
              Clock {clockNum} label
            </label>
            <input
              id={`clock-${clockNum}-label`}
              value={clock.label}
              onChange={(event) => {
                updateClock(index, 'label', event.target.value);
              }}
            />
            <label htmlFor={`clock-${clockNum}-timezone`}>
              Clock {clockNum} timezone
            </label>
            <input
              id={`clock-${clockNum}-timezone`}
              value={clock.time_zone}
              onChange={(event) => {
                updateClock(index, 'time_zone', event.target.value);
              }}
            />
          </fieldset>
        );
      })}
      <button type="submit" disabled={isSaving}>
        Save operational clocks
      </button>
    </form>
  );
}
