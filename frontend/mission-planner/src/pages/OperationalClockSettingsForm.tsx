import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import type {
  OverviewClockSetting,
  OverviewClockSettings,
} from '@/services/overview-clock-settings';
import { Clock3 } from 'lucide-react';
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
      <Card>
        <CardHeader className="pb-3">
          <h2 className="flex items-center gap-2 text-base font-semibold leading-6 tracking-tight">
            <Clock3 className="size-4" aria-hidden="true" />
            Operational clocks
          </h2>
          <CardDescription>
            Set the labels and IANA time zones displayed on Overview.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {editableClocks.map((clock, index) => {
            const clockNum = index + 1;
            return (
              <fieldset
                className="space-y-4 rounded-lg border p-4"
                key={clockNum}
              >
                <legend className="col-span-2">Clock {clockNum}</legend>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium"
                      htmlFor={`clock-${clockNum}-label`}
                    >
                      Clock {clockNum} label
                    </label>
                    <Input
                      className="space-y-2"
                      id={`clock-${clockNum}-label`}
                      value={clock.label}
                      onChange={(event) => {
                        updateClock(index, 'label', event.target.value);
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium"
                      htmlFor={`clock-${clockNum}-timezone`}
                    >
                      Clock {clockNum} timezone
                    </label>
                    <Input
                      className="space-y-2"
                      id={`clock-${clockNum}-timezone`}
                      value={clock.time_zone}
                      onChange={(event) => {
                        updateClock(index, 'time_zone', event.target.value);
                      }}
                    />
                  </div>
                </div>
              </fieldset>
            );
          })}
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save operational clocks'}
          </Button>
        </CardFooter>
      </Card>
    </form>
  );
}
