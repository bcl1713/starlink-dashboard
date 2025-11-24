import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toISO8601 } from '@/lib/utils';
import type { KaOutage } from '../../types/satellite';

interface KaOutageConfigProps {
  outages: KaOutage[];
  onOutagesChange: (outages: KaOutage[]) => void;
}

// Helper to calculate duration from times
const calculateDuration = (startTime: string, endTime: string): number => {
  const start = new Date(startTime).getTime();
  const end = new Date(endTime).getTime();
  return Math.max(0, (end - start) / 1000); // seconds
};

const validateDuration = (duration: number): string | null => {
  if (duration <= 0) {
    return 'Duration must be greater than 0 seconds';
  }
  if (duration > 86400) {
    // 24 hours
    return 'Duration cannot exceed 24 hours (86400 seconds)';
  }
  return null; // Valid
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
  end_time: string;
}

export function KaOutageConfig({
  outages,
  onOutagesChange,
}: KaOutageConfigProps) {
  const [newOutage, setNewOutage] = useState<Partial<NewOutageInput>>({});
  const [startTimeError, setStartTimeError] = useState<string | null>(null);
  const [endTimeError, setEndTimeError] = useState<string | null>(null);
  const [durationError, setDurationError] = useState<string | null>(null);

  const handleAddOutage = () => {
    // Validate inputs
    const startError = validateDatetime(newOutage.start_time || '');
    const endError = validateDatetime(newOutage.end_time || '');
    const durationSeconds = calculateDuration(
      newOutage.start_time || '',
      newOutage.end_time || ''
    );
    const durError = validateDuration(durationSeconds);

    setStartTimeError(startError);
    setEndTimeError(endError);
    setDurationError(durError);

    // Only proceed if all validations pass
    if (!startError && !endError && !durError) {
      onOutagesChange([
        ...outages,
        {
          id: crypto.randomUUID(),
          start_time: toISO8601(newOutage.start_time!),
          duration_seconds: durationSeconds,
        },
      ]);
      setNewOutage({});
      // Clear errors after successful submission
      setStartTimeError(null);
      setEndTimeError(null);
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
        <Table>
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
                <TableCell>{new Date(outage.start_time).toLocaleString()}</TableCell>
                <TableCell>{(outage.duration_seconds / 3600).toFixed(2)}</TableCell>
                <TableCell>{new Date(new Date(outage.start_time).getTime() + outage.duration_seconds * 1000).toLocaleString()}</TableCell>
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
                  <Input
                    type="datetime-local"
                    value={newOutage.start_time ?? ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setNewOutage({
                        ...newOutage,
                        start_time: value,
                      });
                      setStartTimeError(validateDatetime(value));
                      // Re-validate duration if end time exists
                      if (newOutage.end_time) {
                        const dur = calculateDuration(value, newOutage.end_time);
                        setDurationError(validateDuration(dur));
                      }
                    }}
                    className={startTimeError ? 'border-red-500' : ''}
                  />
                  {startTimeError && (
                    <p className="text-sm text-red-500 mt-1">{startTimeError}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                {newOutage.start_time && newOutage.end_time && (
                  <div>
                    <span>
                      {(calculateDuration(newOutage.start_time, newOutage.end_time) / 3600).toFixed(2)}
                    </span>
                    {durationError && (
                      <p className="text-sm text-red-500 mt-1">{durationError}</p>
                    )}
                  </div>
                )}
              </TableCell>
              <TableCell>
                <div>
                  <Input
                    type="datetime-local"
                    value={newOutage.end_time ?? ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setNewOutage({
                        ...newOutage,
                        end_time: value,
                      });
                      setEndTimeError(validateDatetime(value));
                      // Re-validate duration if start time exists
                      if (newOutage.start_time) {
                        const dur = calculateDuration(newOutage.start_time, value);
                        setDurationError(validateDuration(dur));
                      }
                    }}
                    className={endTimeError ? 'border-red-500' : ''}
                  />
                  {endTimeError && (
                    <p className="text-sm text-red-500 mt-1">{endTimeError}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Button
                  onClick={handleAddOutage}
                  disabled={!!startTimeError || !!endTimeError || !!durationError}
                >
                  Add
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
