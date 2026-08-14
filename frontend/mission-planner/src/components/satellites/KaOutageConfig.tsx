import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { createClientId } from '@/lib/clientId';
import { toISO8601, formatTime24Hour } from '@/lib/utils';
import type { KaOutage } from '../../types/satellite';

/**
 * Props for KaOutageConfig component
 */
interface KaOutageConfigProps {
  outages: KaOutage[];
  onOutagesChange: (outages: KaOutage[]) => void;
}

/**
 * Formats a local Date for the datetime-local input used by this form.
 */
const toDatetimeLocalValue = (date: Date): string => {
  const pad = (value: number) => value.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

// Signed decimal input reaches range validation so negative values receive
// the actionable minimum-duration feedback instead of a generic format error.
const durationHoursPattern = /^[+-]?(?:\d+\.?\d*|\.\d+)$/;

const validateDurationHours = (durationHours: string): string | null => {
  if (!durationHours.trim()) {
    return 'Duration is required.';
  }
  if (!durationHoursPattern.test(durationHours)) {
    return 'Enter a valid number of hours.';
  }
  const duration = Number(durationHours);
  if (!Number.isFinite(duration)) {
    return 'Enter a valid number of hours.';
  }
  if (duration <= 0) {
    return 'Duration must be greater than 0 hours.';
  }
  if (duration > 24) {
    return 'Duration cannot exceed 24 hours.';
  }
  return null;
};

const validateDatetime = (datetime: string): string | null => {
  if (!datetime || datetime.trim() === '') {
    return 'Datetime is required';
  }
  try {
    const date = new Date(datetime);
    if (isNaN(date.getTime())) {
      return 'Please enter a valid datetime';
    }
  } catch {
    return 'Please enter a valid datetime';
  }
  return null; // Valid
};

interface NewOutageInput {
  start_time: string;
  duration_hours: string;
}

/**
 * Ka-Band Outage Configuration Component
 *
 * Allows users to configure Ka-band communication outage windows for a mission leg.
 * All times are displayed and entered in 24-hour format for consistency with
 * professional aviation/maritime standards.
 *
 * Features:
 * - Display existing outage windows with start time, duration, and end time
 * - Add new outage windows using a start time and duration in hours
 * - Automatic calculated end time using the local datetime input semantics
 * - Validation for required fields and duration limits (0-24 hours)
 * - Helper text indicating 24-hour format requirement
 *
 * @param outages - Array of existing Ka outage configurations
 * @param onOutagesChange - Callback to update outages when user adds/removes entries
 */
export function KaOutageConfig({
  outages,
  onOutagesChange,
}: KaOutageConfigProps) {
  const [newOutage, setNewOutage] = useState<Partial<NewOutageInput>>({});
  const [startTimeError, setStartTimeError] = useState<string | null>(null);
  const [durationError, setDurationError] = useState<string | null>(null);

  const durationHours = newOutage.duration_hours ?? '';
  const startDate = new Date(newOutage.start_time ?? '');
  const duration = Number(durationHours);
  const calculatedEndTime =
    !Number.isNaN(startDate.getTime()) &&
    durationHoursPattern.test(durationHours) &&
    Number.isFinite(duration) &&
    duration > 0
      ? toDatetimeLocalValue(new Date(startDate.getTime() + duration * 3600000))
      : '';

  const handleAddOutage = () => {
    const startError = validateDatetime(newOutage.start_time || '');
    const durError = validateDurationHours(durationHours);

    setStartTimeError(startError);
    setDurationError(durError);

    if (!startError && !durError) {
      onOutagesChange([
        ...outages,
        {
          id: createClientId(),
          start_time: toISO8601(newOutage.start_time!),
          duration_seconds: duration * 3600,
        },
      ]);
      setNewOutage({});
      setStartTimeError(null);
      setDurationError(null);
    }
  };

  const handleRemoveOutage = (index: number) => {
    onOutagesChange(outages.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">Ka Outage Windows</h3>
        <p className="mb-2 text-xs text-muted-foreground">
          Scroll horizontally to access all outage columns on narrow screens.
        </p>
        <Table className="min-w-[42rem]">
          <TableHeader>
            <TableRow>
              <TableHead>Start Time</TableHead>
              <TableHead>Duration (hours)</TableHead>
              <TableHead>End Time</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {outages.map((outage, index) => (
              <TableRow key={outage.id}>
                <TableCell>{formatTime24Hour(outage.start_time)}</TableCell>
                <TableCell>
                  {(outage.duration_seconds / 3600).toFixed(2)}
                </TableCell>
                <TableCell>
                  {formatTime24Hour(
                    new Date(
                      new Date(outage.start_time).getTime() +
                        outage.duration_seconds * 1000
                    ).toISOString()
                  )}
                </TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleRemoveOutage(index)}
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>
                <div>
                  <Label htmlFor="ka-outage-start-time" className="sr-only">
                    Ka outage start time
                  </Label>
                  <Input
                    id="ka-outage-start-time"
                    type="datetime-local"
                    step="60"
                    value={newOutage.start_time ?? ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setNewOutage({
                        ...newOutage,
                        start_time: value,
                      });
                      setStartTimeError(validateDatetime(value));
                    }}
                    aria-describedby={
                      startTimeError ? 'ka-outage-start-time-error' : undefined
                    }
                    aria-invalid={Boolean(startTimeError)}
                    className={startTimeError ? 'border-red-500' : ''}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    24-hour format (HH:mm)
                  </p>
                  {startTimeError && (
                    <p
                      id="ka-outage-start-time-error"
                      className="text-sm text-red-500 mt-1"
                      role="alert"
                    >
                      {startTimeError}
                    </p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Label htmlFor="ka-outage-duration-hours" className="sr-only">
                  Duration (hours)
                </Label>
                <Input
                  id="ka-outage-duration-hours"
                  type="text"
                  inputMode="decimal"
                  pattern="[+-]?[0-9]*\.?[0-9]*"
                  min="0.01"
                  max="24"
                  step="0.01"
                  required
                  value={durationHours}
                  onChange={(e) => {
                    const value = e.target.value;
                    setNewOutage({ ...newOutage, duration_hours: value });
                    setDurationError(validateDurationHours(value));
                  }}
                  aria-describedby={
                    durationError ? 'ka-outage-duration-error' : undefined
                  }
                  aria-invalid={Boolean(durationError)}
                  className={durationError ? 'border-red-500' : ''}
                />
                {durationError && (
                  <p
                    id="ka-outage-duration-error"
                    className="text-sm text-red-500 mt-1"
                    role="alert"
                  >
                    {durationError}
                  </p>
                )}
              </TableCell>
              <TableCell>
                <div>
                  <Label htmlFor="ka-outage-end-time" className="sr-only">
                    Calculated Ka outage end time
                  </Label>
                  <Input
                    id="ka-outage-end-time"
                    type="datetime-local"
                    step="60"
                    value={calculatedEndTime}
                    readOnly
                    aria-live="polite"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Calculated from the local start time and duration.
                  </p>
                </div>
              </TableCell>
              <TableCell>
                <Button onClick={handleAddOutage}>Add</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
