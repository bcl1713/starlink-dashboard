import { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import type { MissionLeg } from '../../types/mission';
import type { Timeline } from '../../services/timeline';

/**
 * Props for TimingSection component
 */
interface TimingSectionProps {
  leg: MissionLeg;
  timeline: Timeline | null;
  onTimingUpdate: (
    adjustedDepartureTime: string | null,
    warnings?: string[]
  ) => void;
  isUpdating: boolean;
}

/**
 * Timing Section Component
 *
 * Displays and allows editing of mission leg departure times. Users can adjust the
 * departure time without regenerating the route, providing operational flexibility
 * for schedule changes.
 *
 * All times are displayed and entered in 24-hour format (UTC timezone) for consistency
 * with professional aviation/maritime standards.
 *
 * Features:
 * - Display original departure time from route timeline (read-only)
 * - Edit current/adjusted departure time using datetime-local input (24-hour format)
 * - Calculate and display arrival time based on route duration
 * - Show offset indicator when departure time is adjusted
 * - Warning for large time shifts (>8 hours)
 * - Reset to original time functionality
 * - Helper text indicating 24-hour format and UTC timezone
 *
 * @param leg - Mission leg data including adjusted departure time
 * @param timeline - Route timeline data with segment times
 * @param onTimingUpdate - Callback to update departure time adjustment
 * @param isUpdating - Flag indicating if update is in progress
 */
export function TimingSection({
  leg,
  timeline,
  onTimingUpdate,
  isUpdating,
}: TimingSectionProps) {
  const [editedDepartureTime, setEditedDepartureTime] = useState<string>('');
  const [hasLocalChanges, setHasLocalChanges] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [timeFormatError, setTimeFormatError] = useState<string | null>(null);

  // Extract original departure time from timeline (first segment start_time)
  const originalDepartureTime = timeline?.segments?.[0]?.start_time || null;

  // Calculate effective departure time (adjusted if set, otherwise original)
  const effectiveDepartureTime =
    leg.adjusted_departure_time || originalDepartureTime;

  // Calculate arrival time from timeline (last segment end_time)
  const arrivalTime =
    timeline?.segments?.[timeline.segments.length - 1]?.end_time || null;

  // Convert UTC ISO string to local datetime-local format
  const convertUTCToLocal = (utcISO: string): string => {
    // Ensure the string is treated as UTC by appending Z if missing
    const utcString =
      utcISO.endsWith('Z') || utcISO.includes('+') ? utcISO : utcISO + 'Z';
    const date = new Date(utcString);
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    const hours = String(date.getUTCHours()).padStart(2, '0');
    const minutes = String(date.getUTCMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  // Convert local datetime-local format to UTC ISO string
  const convertLocalToUTC = (localDateTime: string): string => {
    // Treat input as UTC (not local timezone)
    const date = new Date(localDateTime + ':00.000Z');
    return date.toISOString();
  };

  // Initialize edited time when leg or timeline changes
  useEffect(() => {
    if (effectiveDepartureTime && !hasLocalChanges) {
      // Convert ISO string to datetime-local format (YYYY-MM-DDTHH:mm)
      const localDateTime = convertUTCToLocal(effectiveDepartureTime);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Syncing controlled input with external data
      setEditedDepartureTime(localDateTime);
    }
  }, [effectiveDepartureTime, hasLocalChanges]);

  // Calculate offset between adjusted and original
  const calculateOffset = (): { minutes: number; display: string } | null => {
    if (!leg.adjusted_departure_time || !originalDepartureTime) {
      return null;
    }

    // Ensure datetime strings are treated as UTC
    const ensureUTC = (dt: string) =>
      dt.endsWith('Z') || dt.includes('+') ? dt : dt + 'Z';
    const adjusted = new Date(ensureUTC(leg.adjusted_departure_time));
    const original = new Date(ensureUTC(originalDepartureTime));
    const diffMs = adjusted.getTime() - original.getTime();
    const diffMinutes = Math.round(diffMs / 60000);

    if (diffMinutes === 0) {
      return null;
    }

    const absMinutes = Math.abs(diffMinutes);
    const hours = Math.floor(absMinutes / 60);
    const minutes = absMinutes % 60;

    let display = '';
    if (hours > 0) {
      display += `${hours} hr`;
      if (minutes > 0) {
        display += ` ${minutes} min`;
      }
    } else {
      display += `${minutes} min`;
    }
    display += diffMinutes > 0 ? ' later' : ' earlier';

    return { minutes: diffMinutes, display };
  };

  const offset = calculateOffset();

  const handleDepartureTimeChange = (value: string) => {
    setEditedDepartureTime(value);
    setHasLocalChanges(true);

    // Validate time format (HH:mm in 24-hour format)
    const timePart = value.slice(11, 16);
    const timePattern = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;

    if (timePart && !timePattern.test(timePart)) {
      setTimeFormatError('Time must be in 24-hour format (HH:mm, e.g., 14:30)');
    } else {
      setTimeFormatError(null);
    }

    // Calculate offset and show warning if > 8 hours
    if (originalDepartureTime && value && timePattern.test(timePart)) {
      const adjustedUTC = convertLocalToUTC(value);
      const adjustedDate = new Date(adjustedUTC);
      const originalUTC =
        originalDepartureTime.endsWith('Z') ||
        originalDepartureTime.includes('+')
          ? originalDepartureTime
          : originalDepartureTime + 'Z';
      const originalDate = new Date(originalUTC);
      const offsetMinutes = Math.abs(
        (adjustedDate.getTime() - originalDate.getTime()) / 60000
      );

      if (offsetMinutes > 480) {
        setWarnings([
          'Large time shift detected (>8 hours). Consider requesting new route from flight planners.',
        ]);
      } else {
        setWarnings([]);
      }
    }
  };

  const handleApply = () => {
    if (!editedDepartureTime || timeFormatError) return;

    // Convert local datetime to UTC ISO string
    const adjustedUTC = convertLocalToUTC(editedDepartureTime);

    // Check if it's different from original
    if (adjustedUTC === originalDepartureTime) {
      // If same as original, clear the adjustment
      handleReset();
      return;
    }

    onTimingUpdate(adjustedUTC, warnings);
    setHasLocalChanges(false);
  };

  const handleReset = () => {
    onTimingUpdate(null);
    setHasLocalChanges(false);
    setWarnings([]);
    setTimeFormatError(null);
  };

  const handleCancel = () => {
    // Reset to current effective time
    if (effectiveDepartureTime) {
      const localDateTime = convertUTCToLocal(effectiveDepartureTime);
      setEditedDepartureTime(localDateTime);
    }
    setHasLocalChanges(false);
    setWarnings([]);
    setTimeFormatError(null);
  };

  // Format ISO datetime for display
  const formatDisplayTime = (isoString: string | null): string => {
    if (!isoString) return 'N/A';
    // Ensure the string is treated as UTC by appending Z if missing
    const utcString =
      isoString.endsWith('Z') || isoString.includes('+')
        ? isoString
        : isoString + 'Z';
    const date = new Date(utcString);
    return date
      .toISOString()
      .replace('T', ' ')
      .replace(/\.\d+Z$/, 'Z');
  };

  if (!originalDepartureTime) {
    return (
      <div className="border rounded-lg p-6 bg-muted/20">
        <h2 className="text-xl font-semibold mb-4">Timing</h2>
        <p className="text-sm text-muted-foreground">
          Timing information not available. Please ensure the route has been
          uploaded and timeline generated.
        </p>
      </div>
    );
  }

  return (
    <div className="border rounded-lg p-6 bg-card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Timing</h2>
        {offset && (
          <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
            Adjusted ({offset.display})
          </span>
        )}
      </div>

      <div className="space-y-4">
        {/* Original Departure Time (Read-only) */}
        <div>
          <label className="text-sm font-medium text-muted-foreground">
            Original Departure (UTC)
          </label>
          <div className="text-sm font-mono mt-1">
            {formatDisplayTime(originalDepartureTime)}
          </div>
        </div>

        {/* Current/Adjusted Departure Time (Editable) */}
        <div>
          <label className="text-sm font-medium block mb-1">
            Current Departure (UTC)
          </label>
          <div className="flex gap-2">
            <div className="flex-1">
              <input
                id="departure-date"
                type="date"
                value={editedDepartureTime.slice(0, 10)}
                onChange={(e) =>
                  handleDepartureTimeChange(
                    e.target.value + editedDepartureTime.slice(10)
                  )
                }
                className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                disabled={isUpdating}
              />
            </div>
            <div className="flex-1">
              {/* Text input with pattern ensures 24-hour format (HH:mm) across all browsers */}
              <input
                id="departure-time"
                type="text"
                pattern="([01][0-9]|2[0-3]):[0-5][0-9]"
                placeholder="HH:mm (e.g., 14:30)"
                value={editedDepartureTime.slice(11, 16)}
                onChange={(e) =>
                  handleDepartureTimeChange(
                    editedDepartureTime.slice(0, 11) + e.target.value
                  )
                }
                className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                  timeFormatError ? 'border-red-500' : ''
                }`}
                disabled={isUpdating}
              />
            </div>
          </div>
          {timeFormatError && (
            <p className="text-sm text-red-500 mt-1">{timeFormatError}</p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            Enter time in UTC timezone (24-hour format: HH:mm)
          </p>
        </div>

        {/* Calculated Arrival Time */}
        {arrivalTime && (
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Calculated Arrival (UTC)
            </label>
            <div className="text-sm font-mono mt-1">
              {formatDisplayTime(arrivalTime)}
            </div>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
            <p className="text-sm text-yellow-800">
              {warnings.map((warning, idx) => (
                <span key={idx} className="block">
                  ⚠️ {warning}
                </span>
              ))}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex space-x-2 pt-2">
          {hasLocalChanges ? (
            <>
              <Button
                onClick={handleApply}
                disabled={
                  isUpdating || !editedDepartureTime || !!timeFormatError
                }
                size="sm"
              >
                {isUpdating ? 'Applying...' : 'Apply'}
              </Button>
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={isUpdating}
                size="sm"
              >
                Cancel
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={isUpdating || !leg.adjusted_departure_time}
              size="sm"
            >
              Reset to Original
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
